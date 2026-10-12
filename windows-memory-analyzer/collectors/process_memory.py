"""
collectors/process_memory.py
─────────────────────────────────────────────────────────────────────────────
Collects per-process memory information using psutil and the Windows
GetProcessMemoryInfo API (PROCESS_MEMORY_COUNTERS_EX).

Counter definitions (PROCESS_MEMORY_COUNTERS_EX)
─────────────────────────────────────────────────
• PageFaultCount       – Cumulative count of page faults incurred by the process
                         since it started.  A page fault does NOT necessarily mean
                         a disk read; most faults on modern Windows are soft faults
                         resolved from the standby list or zero-page list without
                         any I/O.
• PeakWorkingSetSize   – Peak resident (physical) memory used at any moment.
• WorkingSetSize       – Current resident memory: pages that are physically in RAM
                         right now.  Evicted pages are NOT counted.
• QuotaPeakPagedPoolUsage / QuotaPagedPoolUsage – Paged kernel pool quota.
• QuotaPeakNonPagedPoolUsage / QuotaNonPagedPoolUsage – Non-paged pool quota.
• PagefileUsage        – Current private bytes committed to the pagefile
                         (i.e., private committed virtual memory).
• PeakPagefileUsage    – Peak private committed bytes.
• PrivateUsage         – Same as PagefileUsage on Windows Vista+.
"""

import ctypes
import ctypes.wintypes as wt
import datetime
import psutil
from typing import Dict, Any, List, Optional

# ─── Windows structures ────────────────────────────────────────────────────────

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb",                         wt.DWORD),
        ("PageFaultCount",             wt.DWORD),
        ("PeakWorkingSetSize",         ctypes.c_size_t),
        ("WorkingSetSize",             ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage",    ctypes.c_size_t),
        ("QuotaPagedPoolUsage",        ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage",     ctypes.c_size_t),
        ("PagefileUsage",              ctypes.c_size_t),
        ("PeakPagefileUsage",          ctypes.c_size_t),
        ("PrivateUsage",               ctypes.c_size_t),
    ]
    def __init__(self):
        super().__init__()
        self.cb = ctypes.sizeof(self)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

def _mb(b: int) -> float:
    return round(b / (1024 ** 2), 2)


def get_process_memory_counters(pid: int) -> Optional[Dict[str, Any]]:
    """
    Call GetProcessMemoryInfo for the given PID.
    Returns a dict with raw counter values (bytes where applicable) or None
    if the process cannot be accessed.
    """
    pmc = PROCESS_MEMORY_COUNTERS_EX()
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid
    )
    if not handle:
        return None
    try:
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(pmc), ctypes.sizeof(pmc)
        )
        if not ok:
            return None
        return {
            "page_fault_count":               pmc.PageFaultCount,
            "peak_working_set_bytes":         pmc.PeakWorkingSetSize,
            "working_set_bytes":              pmc.WorkingSetSize,
            "quota_peak_paged_pool_bytes":    pmc.QuotaPeakPagedPoolUsage,
            "quota_paged_pool_bytes":         pmc.QuotaPagedPoolUsage,
            "quota_peak_nonpaged_pool_bytes": pmc.QuotaPeakNonPagedPoolUsage,
            "quota_nonpaged_pool_bytes":      pmc.QuotaNonPagedPoolUsage,
            "pagefile_usage_bytes":           pmc.PagefileUsage,
            "peak_pagefile_usage_bytes":      pmc.PeakPagefileUsage,
            "private_usage_bytes":            pmc.PrivateUsage,
        }
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def collect_process_memory(pid: int) -> Dict[str, Any]:
    """
    Return a comprehensive memory snapshot for the given process.

    Combines psutil (portable fields) with GetProcessMemoryInfo (Windows-
    specific counters including the authoritative PageFaultCount).
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    result: Dict[str, Any] = {
        "timestamp":        ts,
        "pid":              pid,
        "name":             None,
        "ppid":             None,
        "exe":              None,
        "create_time":      None,
        "status":           None,
        "num_threads":      None,
        # psutil memory_info
        "rss_mb":           None,   # Resident Set Size (psutil alias for working set)
        "vms_mb":           None,   # Virtual Memory Size
        "private_mb":       None,   # private bytes (psutil)
        # WinAPI counters
        "page_fault_count":          None,
        "working_set_mb":            None,
        "peak_working_set_mb":       None,
        "pagefile_usage_mb":         None,
        "peak_pagefile_usage_mb":    None,
        "private_usage_mb":          None,
        "quota_paged_pool_mb":       None,
        "quota_nonpaged_pool_mb":    None,
        "cpu_percent":               None,
        "memory_percent":            None,
        "error":                     None,
    }

    # ── psutil ────────────────────────────────────────────────────────────
    try:
        p = psutil.Process(pid)
        result["name"]        = p.name()
        result["ppid"]        = p.ppid()
        result["status"]      = p.status()
        result["num_threads"] = p.num_threads()
        try:
            result["exe"] = p.exe()
        except (psutil.AccessDenied, PermissionError):
            result["exe"] = "<access denied>"
        try:
            result["create_time"] = datetime.datetime.fromtimestamp(
                p.create_time(), tz=datetime.timezone.utc).isoformat(timespec="seconds")
        except Exception:
            pass
        try:
            mi = p.memory_info()
            result["rss_mb"]     = _mb(mi.rss)
            result["vms_mb"]     = _mb(mi.vms)
            if hasattr(mi, "private"):
                result["private_mb"] = _mb(mi.private)
        except psutil.AccessDenied:
            pass
        try:
            result["cpu_percent"]    = p.cpu_percent(interval=0.1)
            result["memory_percent"] = p.memory_percent()
        except Exception:
            pass
    except psutil.NoSuchProcess:
        result["error"] = "Process no longer exists."
        return result
    except psutil.AccessDenied:
        result["error"] = "Access denied by Windows."
    except Exception as exc:
        result["error"] = str(exc)

    # ── GetProcessMemoryInfo ──────────────────────────────────────────────
    try:
        wm = get_process_memory_counters(pid)
        if wm:
            result["page_fault_count"]       = wm["page_fault_count"]
            result["working_set_mb"]         = _mb(wm["working_set_bytes"])
            result["peak_working_set_mb"]    = _mb(wm["peak_working_set_bytes"])
            result["pagefile_usage_mb"]      = _mb(wm["pagefile_usage_bytes"])
            result["peak_pagefile_usage_mb"] = _mb(wm["peak_pagefile_usage_bytes"])
            result["private_usage_mb"]       = _mb(wm["private_usage_bytes"])
            result["quota_paged_pool_mb"]    = _mb(wm["quota_paged_pool_bytes"])
            result["quota_nonpaged_pool_mb"] = _mb(wm["quota_nonpaged_pool_bytes"])
    except Exception:
        pass

    return result


def list_processes() -> List[Dict[str, Any]]:
    """
    Return a lightweight list of all accessible processes suitable for
    populating a selection widget.
    """
    procs = []
    for p in psutil.process_iter(["pid", "name", "status"]):
        try:
            info = p.info
            procs.append({
                "pid":    info["pid"],
                "name":   info["name"] or "<unknown>",
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(procs, key=lambda x: x["name"].lower())
