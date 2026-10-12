"""
collectors/page_faults.py
─────────────────────────────────────────────────────────────────────────────
Page-fault counter collection and interpretation helpers.

Windows Page-Fault Semantics
─────────────────────────────
The PROCESS_MEMORY_COUNTERS.PageFaultCount is a *cumulative* DWORD that
counts all page faults incurred by the process since it started.

A page fault occurs when the CPU tries to access a virtual page that is
not currently mapped into the process's working set.  On Windows, the
Memory Manager resolves the fault in one of several ways:

  1. Soft fault (from standby list)  – The page exists in physical memory
     on the standby list (recently evicted); re-mapped without disk I/O.
  2. Zero-demand fault               – A new private page is allocated and
     zero-filled; no disk I/O.
  3. Copy-on-write fault             – A private copy of a shared page is
     created.
  4. Hard fault (page-in from disk)  – The page must be read from the
     pagefile or a memory-mapped file; causes disk I/O.

PageFaultCount on Windows does NOT distinguish between these categories.
Hard faults are exposed separately via Performance Counters
("Process\Page Faults/sec" distinguishes "Hard Faults/sec") but that
API is heavier weight.  This module uses PageFaultCount and notes the
limitation clearly.

Units
─────
• PageFaultCount     – dimensionless cumulative count (DWORD, wraps at 2^32)
• delta              – faults accumulated during an interval
• rate               – delta / elapsed_seconds (faults per second)
"""

import datetime
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from collectors.process_memory import get_process_memory_counters


@dataclass
class PageFaultSample:
    """A single page-fault observation for one process."""
    pid:         int
    timestamp:   str
    elapsed_s:   float           # seconds since experiment start
    fault_count: Optional[int]   # cumulative PageFaultCount (None = unavailable)
    working_set_mb:   Optional[float] = None
    private_mb:       Optional[float] = None


@dataclass
class PageFaultSeries:
    """Collection of samples for one experiment run."""
    pid:        int
    experiment: str
    samples:    List[PageFaultSample] = field(default_factory=list)

    # set once experiment finishes
    initial_count: Optional[int] = None
    final_count:   Optional[int] = None
    duration_s:    Optional[float] = None

    @property
    def delta(self) -> Optional[int]:
        if self.initial_count is None or self.final_count is None:
            return None
        # handle DWORD wrap-around (unlikely in short experiments)
        d = self.final_count - self.initial_count
        if d < 0:
            d += 2 ** 32
        return d

    @property
    def rate_per_second(self) -> Optional[float]:
        if self.delta is None or not self.duration_s:
            return None
        return round(self.delta / self.duration_s, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid":             self.pid,
            "experiment":      self.experiment,
            "initial_count":   self.initial_count,
            "final_count":     self.final_count,
            "delta":           self.delta,
            "duration_s":      self.duration_s,
            "rate_per_second": self.rate_per_second,
            "sample_count":    len(self.samples),
        }


class PageFaultMonitor:
    """
    Lightweight monitor that samples PageFaultCount for a PID at a
    caller-defined interval.

    Usage
    ─────
        monitor = PageFaultMonitor(pid=1234, experiment="sequential")
        monitor.start()
        ...do work...
        monitor.stop()
        series = monitor.series
    """

    def __init__(self, pid: int, experiment: str):
        self.pid        = pid
        self.experiment = experiment
        self._series    = PageFaultSeries(pid=pid, experiment=experiment)
        self._t0: Optional[float] = None

    def start(self) -> None:
        self._t0 = time.monotonic()
        count = self._read_count()
        self._series.initial_count = count
        self._record(count)

    def sample(self) -> Optional[PageFaultSample]:
        """Take one sample and append it; return the sample."""
        if self._t0 is None:
            raise RuntimeError("Call start() first.")
        count = self._read_count()
        return self._record(count)

    def stop(self) -> "PageFaultSeries":
        count = self._read_count()
        self._record(count)
        self._series.final_count = count
        if self._t0 is not None:
            self._series.duration_s = round(time.monotonic() - self._t0, 3)
        return self._series

    @property
    def series(self) -> PageFaultSeries:
        return self._series

    # ── private ────────────────────────────────────────────────────────────

    def _read_count(self) -> Optional[int]:
        wm = get_process_memory_counters(self.pid)
        if wm is None:
            return None
        return wm["page_fault_count"]

    def _record(self, count: Optional[int]) -> PageFaultSample:
        elapsed = round(time.monotonic() - self._t0, 3) if self._t0 else 0.0
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

        # try to get working-set size too
        wm = get_process_memory_counters(self.pid)
        ws_mb   = round(wm["working_set_bytes"] / (1024 ** 2), 2) if wm else None
        priv_mb = round(wm["private_usage_bytes"] / (1024 ** 2), 2) if wm else None

        sample = PageFaultSample(
            pid=self.pid,
            timestamp=ts,
            elapsed_s=elapsed,
            fault_count=count,
            working_set_mb=ws_mb,
            private_mb=priv_mb,
        )
        self._series.samples.append(sample)
        return sample


def interpret_page_fault_delta(delta: Optional[int], workload: str) -> str:
    """
    Return a plain-English interpretation of a page-fault delta.
    Avoids over-claiming what the counter means.
    """
    if delta is None:
        return "Page-fault count unavailable for this process."
    if delta == 0:
        return (
            "No additional page faults were recorded.  All accessed pages "
            "were already resident in the working set."
        )
    if workload == "allocation":
        return (
            f"{delta:,} page faults were recorded.  Because virtual memory was "
            "allocated but pages may not have been deliberately accessed, many "
            "of these are likely zero-demand faults from the OS initialising "
            "private pages, or faults from the allocator metadata."
        )
    if workload == "sequential":
        return (
            f"{delta:,} page faults were recorded during sequential access.  "
            "Each page was accessed in order; the first touch of each 4 KiB "
            "page triggered a fault.  Subsequent accesses to the same page did "
            "not fault (page already resident).  Most faults are expected to be "
            "soft (no disk I/O) on a machine with sufficient free RAM."
        )
    if workload == "repeated":
        return (
            f"{delta:,} page faults were recorded.  The initial pass faulted in "
            "every page; repeated passes over the same already-resident pages "
            "should produce far fewer additional faults unless the OS evicted "
            "pages under memory pressure."
        )
    if workload == "random":
        return (
            f"{delta:,} page faults were recorded during random access.  Random "
            "patterns may increase faults if the working set is large enough to "
            "be partially evicted, but on a machine with ample free RAM the total "
            "fault count is often similar to sequential access."
        )
    if workload == "release":
        return (
            f"{delta:,} page faults were recorded before the allocation was "
            "freed.  After release, process working-set size should decrease, "
            "though system-wide physical memory usage may not drop immediately "
            "because Windows keeps freed pages on the standby list."
        )
    return (
        f"{delta:,} page faults were recorded.  Windows PageFaultCount is a "
        "cumulative counter that includes soft faults (no disk I/O) and hard "
        "faults (disk I/O).  It does not reveal which type occurred."
    )
