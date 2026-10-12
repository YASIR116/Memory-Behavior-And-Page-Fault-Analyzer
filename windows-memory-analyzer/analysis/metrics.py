"""
analysis/metrics.py
─────────────────────────────────────────────────────────────────────────────
Pure-Python metric helpers: unit conversion, delta calculation, rate
calculation, and descriptive metadata for every counter used by the app.
These functions have no Windows or psutil dependencies so they are fully
unit-testable.
"""

from typing import Optional, List, Dict, Any


# ─── Unit conversion ──────────────────────────────────────────────────────────

def bytes_to_mb(b: Optional[int]) -> Optional[float]:
    """Convert bytes to MiB (2^20).  Returns None if input is None."""
    if b is None:
        return None
    return round(b / (1024 ** 2), 2)


def bytes_to_gb(b: Optional[int]) -> Optional[float]:
    """Convert bytes to GiB (2^30).  Returns None if input is None."""
    if b is None:
        return None
    return round(b / (1024 ** 3), 3)


def mb_to_gb(mb: Optional[float]) -> Optional[float]:
    if mb is None:
        return None
    return round(mb / 1024, 3)


def format_bytes(b: Optional[int]) -> str:
    """Return a human-readable string for a byte count."""
    if b is None:
        return "N/A"
    if b >= 1024 ** 3:
        return f"{b / (1024 ** 3):.2f} GiB"
    if b >= 1024 ** 2:
        return f"{b / (1024 ** 2):.1f} MiB"
    if b >= 1024:
        return f"{b / 1024:.1f} KiB"
    return f"{b} B"


def format_mb(mb: Optional[float]) -> str:
    """Return a human-readable string for a MiB value."""
    if mb is None:
        return "N/A"
    if mb >= 1024:
        return f"{mb / 1024:.2f} GiB"
    return f"{mb:.1f} MiB"


# ─── Counter arithmetic ───────────────────────────────────────────────────────

def counter_delta(initial: Optional[int], final: Optional[int],
                  bits: int = 32) -> Optional[int]:
    """
    Calculate the delta between two cumulative counter readings.

    Handles wrap-around for counters that overflow at 2^bits.
    Returns None if either reading is unavailable.
    """
    if initial is None or final is None:
        return None
    d = final - initial
    if d < 0:
        d += 2 ** bits
    return d


def counter_rate(delta: Optional[int], duration_s: Optional[float]) -> Optional[float]:
    """
    Calculate a per-second rate from a delta and elapsed time.
    Returns None if inputs are invalid.
    """
    if delta is None or not duration_s or duration_s <= 0:
        return None
    return round(delta / duration_s, 2)


def percentage(part: Optional[float], total: Optional[float]) -> Optional[float]:
    """Return part/total × 100, or None if inputs are invalid."""
    if part is None or total is None or total == 0:
        return None
    return round(part / total * 100, 2)


# ─── Sample list helpers ──────────────────────────────────────────────────────

def extract_series(samples: List[Dict[str, Any]],
                   key: str) -> List[Optional[float]]:
    """Extract a list of values for `key` from a list of sample dicts."""
    return [s.get(key) for s in samples]


def peak_value(values: List[Optional[float]]) -> Optional[float]:
    """Return the maximum non-None value, or None."""
    non_null = [v for v in values if v is not None]
    return max(non_null) if non_null else None


def min_value(values: List[Optional[float]]) -> Optional[float]:
    non_null = [v for v in values if v is not None]
    return min(non_null) if non_null else None


def fault_deltas_from_samples(
    samples: List[Dict[str, Any]]
) -> List[Optional[int]]:
    """
    Compute per-interval fault deltas from a series of cumulative
    page_fault_count values.

    The first element is always None (no prior reading to compare with).
    Returns [] for an empty samples list.
    """
    if not samples:
        return []
    counts = [s.get("page_fault_count") for s in samples]
    deltas: List[Optional[int]] = [None]
    for i in range(1, len(counts)):
        deltas.append(counter_delta(counts[i - 1], counts[i]))
    return deltas


# ─── Counter catalogue ────────────────────────────────────────────────────────

COUNTER_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "page_fault_count": {
        "name":    "Page Fault Count (cumulative)",
        "units":   "count",
        "scope":   "process",
        "kind":    "cumulative",
        "source":  "PROCESS_MEMORY_COUNTERS_EX.PageFaultCount (GetProcessMemoryInfo)",
        "note": (
            "Counts all page faults since the process started, including soft "
            "faults (resolved without disk I/O) and hard faults (disk read "
            "required). Windows does not split this counter by fault type.  "
            "A large value does not imply disk I/O."
        ),
    },
    "working_set_mb": {
        "name":    "Working Set Size",
        "units":   "MiB",
        "scope":   "process",
        "kind":    "instantaneous",
        "source":  "PROCESS_MEMORY_COUNTERS_EX.WorkingSetSize",
        "note": (
            "The number of physical-memory pages currently mapped into the "
            "process's virtual address space.  Pages that have been evicted "
            "by the OS are not counted.  This is the main indicator of "
            "physical RAM use for a process."
        ),
    },
    "peak_working_set_mb": {
        "name":    "Peak Working Set Size",
        "units":   "MiB",
        "scope":   "process",
        "kind":    "cumulative",
        "source":  "PROCESS_MEMORY_COUNTERS_EX.PeakWorkingSetSize",
        "note":    "Maximum working-set size recorded at any point during the process lifetime.",
    },
    "pagefile_usage_mb": {
        "name":    "Pagefile Usage (Private Bytes)",
        "units":   "MiB",
        "scope":   "process",
        "kind":    "instantaneous",
        "source":  "PROCESS_MEMORY_COUNTERS_EX.PagefileUsage",
        "note": (
            "Private committed virtual memory that is backed by the pagefile "
            "(or physical RAM if not yet paged out).  This is the 'Private "
            "Bytes' counter in Task Manager and Process Monitor."
        ),
    },
    "available_physical_mb": {
        "name":    "Available Physical RAM",
        "units":   "MiB",
        "scope":   "system",
        "kind":    "instantaneous",
        "source":  "GlobalMemoryStatusEx.ullAvailPhys",
        "note": (
            "Memory immediately available for use: free pages + standby-list "
            "pages.  This can be non-zero even when the system is under "
            "moderate load because Windows keeps recently freed pages on the "
            "standby list."
        ),
    },
    "total_physical_mb": {
        "name":    "Total Physical RAM",
        "units":   "MiB",
        "scope":   "system",
        "kind":    "fixed",
        "source":  "GlobalMemoryStatusEx.ullTotalPhys",
        "note":    "Total installed physical RAM.  Does not change while the system is running.",
    },
    "memory_percent": {
        "name":    "Memory Utilisation",
        "units":   "%",
        "scope":   "system",
        "kind":    "instantaneous",
        "source":  "GlobalMemoryStatusEx.dwMemoryLoad",
        "note":    "Percentage of physical RAM in use.  Reported directly by Windows.",
    },
    "system_cache_mb": {
        "name":    "System File Cache",
        "units":   "MiB",
        "scope":   "system",
        "kind":    "instantaneous",
        "source":  "PERFORMANCE_INFORMATION.SystemCache × PageSize",
        "note": (
            "Memory used as a file-system cache (standby + modified lists).  "
            "Windows can repurpose this for processes on demand."
        ),
    },
    "commit_total_mb": {
        "name":    "Committed Memory (System)",
        "units":   "MiB",
        "scope":   "system",
        "kind":    "instantaneous",
        "source":  "PERFORMANCE_INFORMATION.CommitTotal × PageSize",
        "note": (
            "Total virtual memory committed system-wide (all processes + OS).  "
            "Committed memory is guaranteed to be provided physical backing "
            "on demand."
        ),
    },
}
