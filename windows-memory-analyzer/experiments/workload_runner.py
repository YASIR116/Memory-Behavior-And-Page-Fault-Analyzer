"""
experiments/workload_runner.py
─────────────────────────────────────────────────────────────────────────────
Manages the lifecycle of a workload subprocess:
  - spawns a fresh process with the correct workload function
  - collects samples from the queue in a background thread
  - provides a stop() / cancel() mechanism
  - aggregates results once the process exits

Thread safety: the public API is called from the Streamlit main thread; the
reader thread is an internal detail.
"""

import multiprocessing
import threading
import time
import queue as stdlib_queue
from typing import Dict, Any, List, Optional, Callable

from experiments.memory_workloads import WORKLOAD_FUNCTIONS
from config import MAX_ALLOC_MB, DEFAULT_DURATION_S, DEFAULT_SAMPLE_INTERVAL_S


# ─── Validation ────────────────────────────────────────────────────────────────

def validate_config(cfg: Dict[str, Any]) -> Optional[str]:
    """
    Validate experiment configuration.
    Returns an error message string, or None if valid.
    """
    try:
        alloc_mb = float(cfg.get("alloc_mb", 0))
        duration = float(cfg.get("duration_s", 0))
        interval = float(cfg.get("interval_s", 0))
    except (TypeError, ValueError):
        return "Configuration values must be numbers."

    if alloc_mb <= 0:
        return "Allocation size must be greater than 0 MiB."
    if alloc_mb > MAX_ALLOC_MB:
        return f"Allocation size must not exceed {MAX_ALLOC_MB} MiB."
    if duration < 3:
        return "Duration must be at least 3 seconds."
    if duration > 300:
        return "Duration must not exceed 300 seconds."
    if interval < 0.1:
        return "Sampling interval must be at least 0.1 seconds."
    if interval > 60:
        return "Sampling interval must not exceed 60 seconds."
    if cfg.get("workload") not in WORKLOAD_FUNCTIONS:
        return f"Unknown workload type: {cfg.get('workload')!r}"

    return None


# ─── Runner ────────────────────────────────────────────────────────────────────

def _worker_entry(workload_name: str, cfg: Dict[str, Any],
                  q: multiprocessing.Queue) -> None:
    """Top-level function executed in the worker process."""
    fn = WORKLOAD_FUNCTIONS[workload_name]
    fn(cfg, q)


class WorkloadRunner:
    """
    Manages one experiment run in a separate process.

    Usage
    ─────
        runner = WorkloadRunner()
        runner.start(workload="sequential", cfg={...})
        # poll runner.samples / runner.is_running
        runner.stop()
        summary = runner.summary
    """

    def __init__(self):
        self._process:  Optional[multiprocessing.Process] = None
        self._queue:    Optional[multiprocessing.Queue]   = None
        self._reader:   Optional[threading.Thread]        = None
        self._samples:  List[Dict[str, Any]] = []
        self._summary:  Optional[Dict[str, Any]] = None
        self._errors:   List[str] = []
        self._lock      = threading.Lock()
        self._done_evt  = threading.Event()
        self._cancelled = False

    # ── public API ─────────────────────────────────────────────────────────

    def start(self, workload: str, cfg: Dict[str, Any]) -> None:
        """Validate, then start the workload in a subprocess."""
        err = validate_config({**cfg, "workload": workload})
        if err:
            raise ValueError(err)

        self._reset()
        self._queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(
            target=_worker_entry,
            args=(workload, cfg, self._queue),
            daemon=True,
        )
        self._process.start()
        self._reader = threading.Thread(
            target=self._read_queue, daemon=True
        )
        self._reader.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Request cancellation and wait for the process to exit."""
        self._cancelled = True
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=timeout)
            if self._process.is_alive():
                self._process.kill()
        self._done_evt.wait(timeout=timeout + 1)

    def wait(self, timeout: float = 120.0) -> bool:
        """Block until the experiment finishes or timeout. Returns True if finished."""
        return self._done_evt.wait(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.is_alive()
            and not self._done_evt.is_set()
        )

    @property
    def samples(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._samples)

    @property
    def summary(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._summary

    @property
    def errors(self) -> List[str]:
        with self._lock:
            return list(self._errors)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    # ── internal ────────────────────────────────────────────────────────────

    def _reset(self) -> None:
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=3)
        self._samples  = []
        self._summary  = None
        self._errors   = []
        self._done_evt.clear()
        self._cancelled = False

    def _read_queue(self) -> None:
        """Background thread: drain the queue until 'done' sentinel."""
        while True:
            try:
                msg = self._queue.get(timeout=1.0)
            except Exception:
                # Check if process died without sending done
                if self._process and not self._process.is_alive():
                    break
                continue

            if msg["type"] == "sample":
                with self._lock:
                    self._samples.append(msg["data"])
            elif msg["type"] == "summary":
                with self._lock:
                    self._summary = msg["data"]
            elif msg["type"] == "error":
                with self._lock:
                    self._errors.append(msg["message"])
            elif msg["type"] == "done":
                break

        self._done_evt.set()


# ─── Singleton runner used by the Streamlit session ───────────────────────────
# Streamlit re-imports modules each rerun; store runner in st.session_state
# outside this module to persist across reruns.
