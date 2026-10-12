"""
experiments/memory_workloads.py
─────────────────────────────────────────────────────────────────────────────
Actual memory workload implementations that run inside a worker process.

Each workload function is designed to:
  1. Accept a configuration dict and a multiprocessing.Queue.
  2. Run the workload.
  3. Emit progress dicts (samples) via the queue.
  4. Return a final summary dict via the queue as the last message.

Queue message schema
────────────────────
  {"type": "sample",  "data": {...}}   – periodic measurement
  {"type": "summary", "data": {...}}   – final result
  {"type": "error",   "message": str}  – unrecoverable failure
  {"type": "done"}                     – sentinel (always last)
"""

import os
import time
import random
import multiprocessing
import datetime
import ctypes
from typing import Dict, Any, Optional

from collectors.process_memory import get_process_memory_counters
from collectors.system_memory  import collect_system_memory


# ─── Helper ────────────────────────────────────────────────────────────────────

def _mb(b: int) -> float:
    return round(b / (1024 ** 2), 2)


def _snapshot(pid: int) -> Dict[str, Any]:
    """Collect a lightweight process+system snapshot."""
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    wm = get_process_memory_counters(pid)
    vm = collect_system_memory()
    return {
        "timestamp":          ts,
        "pid":                pid,
        "page_fault_count":   wm["page_fault_count"]       if wm else None,
        "working_set_mb":     _mb(wm["working_set_bytes"]) if wm else None,
        "virtual_mem_mb":     _mb(wm["private_usage_bytes"]) if wm else None,
        "available_ram_mb":   vm["available_physical_mb"],
        "system_memory_pct":  vm["memory_percent"],
    }


def _page_size() -> int:
    try:
        si = ctypes.wintypes.SYSTEM_INFO()
        ctypes.windll.kernel32.GetSystemInfo(ctypes.byref(si))
        return si.dwPageSize
    except Exception:
        return 4096


def _emit_sample(q: multiprocessing.Queue, snap: Dict[str, Any], elapsed: float) -> None:
    snap["elapsed_s"] = round(elapsed, 3)
    q.put({"type": "sample", "data": snap})


# ─── Workload A: Allocation ────────────────────────────────────────────────────

def workload_allocation(cfg: Dict[str, Any], q: multiprocessing.Queue) -> None:
    """
    Allocate a block of memory using bytearray (backed by private anonymous
    memory on Windows) without deliberately touching every page.

    Python's memory allocator may or may not touch all pages immediately
    depending on the allocator and OS demand-zero strategy.
    """
    alloc_bytes = int(cfg["alloc_mb"] * 1024 * 1024)
    duration    = float(cfg["duration_s"])
    interval    = float(cfg["interval_s"])
    pid         = os.getpid()

    t0 = time.monotonic()
    snap0 = _snapshot(pid)
    initial_faults = snap0["page_fault_count"]

    try:
        # Allocate – intentionally no full touch
        buf = bytearray(alloc_bytes)
        # Touch just the first byte so Python doesn't optimise the allocation away
        buf[0] = 1

        snap_alloc = _snapshot(pid)
        _emit_sample(q, snap_alloc, time.monotonic() - t0)

        while time.monotonic() - t0 < duration:
            time.sleep(interval)
            _emit_sample(q, _snapshot(pid), time.monotonic() - t0)

        snap_final = _snapshot(pid)
        final_faults = snap_final["page_fault_count"]

        summary = {
            "workload":           "allocation",
            "alloc_mb":           cfg["alloc_mb"],
            "duration_s":         round(time.monotonic() - t0, 2),
            "initial_page_faults": initial_faults,
            "final_page_faults":  final_faults,
            "fault_delta":        (final_faults - initial_faults) if (initial_faults is not None and final_faults is not None) else None,
            "peak_working_set_mb": snap_final["working_set_mb"],
            "final_available_ram_mb": snap_final["available_ram_mb"],
        }
        q.put({"type": "summary", "data": summary})

    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        try:
            del buf
        except Exception:
            pass
        q.put({"type": "done"})


# ─── Workload B: Sequential Access ────────────────────────────────────────────

def workload_sequential(cfg: Dict[str, Any], q: multiprocessing.Queue) -> None:
    """
    Allocate a block and touch every page sequentially.
    Each first-touch of a page causes a page fault on Windows.
    """
    alloc_bytes = int(cfg["alloc_mb"] * 1024 * 1024)
    duration    = float(cfg["duration_s"])
    interval    = float(cfg["interval_s"])
    pid         = os.getpid()
    page_size   = _page_size()

    t0 = time.monotonic()
    snap0 = _snapshot(pid)
    initial_faults = snap0["page_fault_count"]

    try:
        buf = bytearray(alloc_bytes)
        last_sample_t = t0
        peak_ws = 0.0

        # Touch every page sequentially
        for i in range(0, alloc_bytes, page_size):
            buf[i] = 0xAB  # write triggers demand-zero fault on first access

            now = time.monotonic()
            if now - last_sample_t >= interval:
                snap = _snapshot(pid)
                _emit_sample(q, snap, now - t0)
                last_sample_t = now
                if snap["working_set_mb"]:
                    peak_ws = max(peak_ws, snap["working_set_mb"])

            # Respect the configured duration
            if now - t0 >= duration:
                break

        # Hold briefly then finish
        while time.monotonic() - t0 < duration:
            now = time.monotonic()
            if now - last_sample_t >= interval:
                snap = _snapshot(pid)
                _emit_sample(q, snap, now - t0)
                last_sample_t = now
            time.sleep(0.05)

        snap_final = _snapshot(pid)
        final_faults = snap_final["page_fault_count"]

        summary = {
            "workload":            "sequential",
            "alloc_mb":            cfg["alloc_mb"],
            "duration_s":          round(time.monotonic() - t0, 2),
            "page_size_bytes":     page_size,
            "initial_page_faults": initial_faults,
            "final_page_faults":   final_faults,
            "fault_delta":         (final_faults - initial_faults) if (initial_faults is not None and final_faults is not None) else None,
            "peak_working_set_mb": peak_ws or snap_final["working_set_mb"],
            "final_available_ram_mb": snap_final["available_ram_mb"],
        }
        q.put({"type": "summary", "data": summary})

    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        try:
            del buf
        except Exception:
            pass
        q.put({"type": "done"})


# ─── Workload C: Repeated Access ──────────────────────────────────────────────

def workload_repeated(cfg: Dict[str, Any], q: multiprocessing.Queue) -> None:
    """
    Allocate, touch all pages once, then re-traverse multiple times.
    After the first pass, pages are resident; subsequent passes should
    produce far fewer additional faults (only if Windows evicts pages).
    """
    alloc_bytes = int(cfg["alloc_mb"] * 1024 * 1024)
    duration    = float(cfg["duration_s"])
    interval    = float(cfg["interval_s"])
    pid         = os.getpid()
    page_size   = _page_size()

    t0 = time.monotonic()
    snap0 = _snapshot(pid)
    initial_faults = snap0["page_fault_count"]
    peak_ws = 0.0

    try:
        buf = bytearray(alloc_bytes)
        last_sample_t = t0
        pass_num = 0

        while time.monotonic() - t0 < duration:
            pass_num += 1
            for i in range(0, alloc_bytes, page_size):
                buf[i] ^= 0x55  # XOR to prevent compiler elision

                now = time.monotonic()
                if now - last_sample_t >= interval:
                    snap = _snapshot(pid)
                    snap["pass_number"] = pass_num
                    _emit_sample(q, snap, now - t0)
                    last_sample_t = now
                    if snap["working_set_mb"]:
                        peak_ws = max(peak_ws, snap["working_set_mb"])

                if now - t0 >= duration:
                    break

        snap_final = _snapshot(pid)
        final_faults = snap_final["page_fault_count"]

        summary = {
            "workload":            "repeated",
            "alloc_mb":            cfg["alloc_mb"],
            "duration_s":          round(time.monotonic() - t0, 2),
            "passes_completed":    pass_num,
            "initial_page_faults": initial_faults,
            "final_page_faults":   final_faults,
            "fault_delta":         (final_faults - initial_faults) if (initial_faults is not None and final_faults is not None) else None,
            "peak_working_set_mb": peak_ws or snap_final["working_set_mb"],
            "final_available_ram_mb": snap_final["available_ram_mb"],
        }
        q.put({"type": "summary", "data": summary})

    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        try:
            del buf
        except Exception:
            pass
        q.put({"type": "done"})


# ─── Workload D: Random Access ─────────────────────────────────────────────────

def workload_random(cfg: Dict[str, Any], q: multiprocessing.Queue) -> None:
    """
    Allocate and access pages in pseudorandom order.
    The random seed is configurable so experiments are reproducible.
    """
    alloc_bytes = int(cfg["alloc_mb"] * 1024 * 1024)
    duration    = float(cfg["duration_s"])
    interval    = float(cfg["interval_s"])
    seed        = int(cfg.get("random_seed", 42))
    pid         = os.getpid()
    page_size   = _page_size()

    t0 = time.monotonic()
    snap0 = _snapshot(pid)
    initial_faults = snap0["page_fault_count"]
    peak_ws = 0.0

    rng = random.Random(seed)
    n_pages = alloc_bytes // page_size

    try:
        buf = bytearray(alloc_bytes)
        page_indices = list(range(n_pages))
        rng.shuffle(page_indices)

        last_sample_t = t0

        for idx in page_indices:
            buf[idx * page_size] ^= 0xCC

            now = time.monotonic()
            if now - last_sample_t >= interval:
                snap = _snapshot(pid)
                _emit_sample(q, snap, now - t0)
                last_sample_t = now
                if snap["working_set_mb"]:
                    peak_ws = max(peak_ws, snap["working_set_mb"])

            if now - t0 >= duration:
                break

        # Hold until duration
        while time.monotonic() - t0 < duration:
            now = time.monotonic()
            if now - last_sample_t >= interval:
                snap = _snapshot(pid)
                _emit_sample(q, snap, now - t0)
                last_sample_t = now
            time.sleep(0.05)

        snap_final = _snapshot(pid)
        final_faults = snap_final["page_fault_count"]

        summary = {
            "workload":            "random",
            "alloc_mb":            cfg["alloc_mb"],
            "duration_s":          round(time.monotonic() - t0, 2),
            "random_seed":         seed,
            "initial_page_faults": initial_faults,
            "final_page_faults":   final_faults,
            "fault_delta":         (final_faults - initial_faults) if (initial_faults is not None and final_faults is not None) else None,
            "peak_working_set_mb": peak_ws or snap_final["working_set_mb"],
            "final_available_ram_mb": snap_final["available_ram_mb"],
        }
        q.put({"type": "summary", "data": summary})

    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        try:
            del buf
        except Exception:
            pass
        q.put({"type": "done"})


# ─── Workload E: Memory Release ────────────────────────────────────────────────

def workload_release(cfg: Dict[str, Any], q: multiprocessing.Queue) -> None:
    """
    Allocate, touch all pages, hold briefly, then release.
    Demonstrates that process working-set shrinks on release but system-
    wide physical RAM usage may not drop immediately (standby list).
    """
    alloc_bytes = int(cfg["alloc_mb"] * 1024 * 1024)
    duration    = float(cfg["duration_s"])
    interval    = float(cfg["interval_s"])
    pid         = os.getpid()
    page_size   = _page_size()

    hold_frac   = 0.5   # spend first half allocating/touching, second half released

    t0 = time.monotonic()
    snap0 = _snapshot(pid)
    initial_faults = snap0["page_fault_count"]

    try:
        buf = bytearray(alloc_bytes)
        last_sample_t = t0
        peak_ws = 0.0

        # Phase 1: touch all pages
        for i in range(0, alloc_bytes, page_size):
            buf[i] = 0xBE
            now = time.monotonic()
            if now - last_sample_t >= interval:
                snap = _snapshot(pid)
                snap["phase"] = "touching"
                _emit_sample(q, snap, now - t0)
                last_sample_t = now
                if snap["working_set_mb"]:
                    peak_ws = max(peak_ws, snap["working_set_mb"])
            if now - t0 >= duration * hold_frac:
                break

        # Phase 2: hold
        while time.monotonic() - t0 < duration * hold_frac:
            now = time.monotonic()
            if now - last_sample_t >= interval:
                snap = _snapshot(pid)
                snap["phase"] = "holding"
                _emit_sample(q, snap, now - t0)
                last_sample_t = now
            time.sleep(0.05)

        snap_pre_release = _snapshot(pid)

        # Phase 3: release
        del buf

        # Monitor post-release
        while time.monotonic() - t0 < duration:
            now = time.monotonic()
            if now - last_sample_t >= interval:
                snap = _snapshot(pid)
                snap["phase"] = "released"
                _emit_sample(q, snap, now - t0)
                last_sample_t = now
            time.sleep(0.05)

        snap_final = _snapshot(pid)
        final_faults = snap_final["page_fault_count"]

        summary = {
            "workload":              "release",
            "alloc_mb":              cfg["alloc_mb"],
            "duration_s":            round(time.monotonic() - t0, 2),
            "initial_page_faults":   initial_faults,
            "final_page_faults":     final_faults,
            "fault_delta":           (final_faults - initial_faults) if (initial_faults is not None and final_faults is not None) else None,
            "peak_working_set_mb":   peak_ws,
            "pre_release_ws_mb":     snap_pre_release["working_set_mb"],
            "post_release_ws_mb":    snap_final["working_set_mb"],
            "final_available_ram_mb": snap_final["available_ram_mb"],
        }
        q.put({"type": "summary", "data": summary})

    except Exception as exc:
        q.put({"type": "error", "message": str(exc)})
    finally:
        try:
            del buf
        except Exception:
            pass
        q.put({"type": "done"})


# ─── Dispatch table ────────────────────────────────────────────────────────────

WORKLOAD_FUNCTIONS = {
    "allocation": workload_allocation,
    "sequential": workload_sequential,
    "repeated":   workload_repeated,
    "random":     workload_random,
    "release":    workload_release,
}
