"""
collectors/system_memory.py
─────────────────────────────────────────────────────────────────────────────
Collects system-wide Windows memory statistics using psutil and the Windows
GlobalMemoryStatusEx / GetPerformanceInfo APIs via ctypes.

Counter definitions
───────────────────
• total_physical_mb   – Total physical RAM installed (MB). Instantaneous / fixed.
• available_physical_mb – RAM not in use by any process (MB). Instantaneous.
• used_physical_mb    – total_physical_mb − available_physical_mb.
• memory_percent      – Fraction of physical RAM in use (0–100). Instantaneous.
• total_virtual_mb    – Total user-mode virtual address space committed limit (MB).
• available_virtual_mb – Unused virtual address space (MB).
• pagefile_total_mb   – Committed pagefile size limit (MB).
• pagefile_used_mb    – Currently committed pagefile bytes (MB).
• pagefile_percent    – pagefile_used_mb / pagefile_total_mb × 100.
• page_size_bytes     – OS page granularity (usually 4096 B on x86/x64).
• system_cache_mb     – Standby / system file-cache size (MB).
• cpu_percent         – Overall CPU utilisation (0–100). 1-second interval sample.
• cpu_count           – Logical processor count.
• process_count       – Number of live processes.
• timestamp           – ISO-8601 UTC timestamp of the observation.
"""

import ctypes
import ctypes.wintypes as wt
import datetime
import psutil
from typing import Dict, Any

# ─── Windows structures ────────────────────────────────────────────────────────

class MEMORYSTATUSEX(ctypes.Structure):
    """Maps to MEMORYSTATUSEX in winbase.h (GlobalMemoryStatusEx)."""
    _fields_ = [
        ("dwLength",                wt.DWORD),
        ("dwMemoryLoad",            wt.DWORD),
        ("ullTotalPhys",            ctypes.c_ulonglong),
        ("ullAvailPhys",            ctypes.c_ulonglong),
        ("ullTotalPageFile",        ctypes.c_ulonglong),
        ("ullAvailPageFile",        ctypes.c_ulonglong),
        ("ullTotalVirtual",         ctypes.c_ulonglong),
        ("ullAvailVirtual",         ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]
    def __init__(self):
        super().__init__()
        self.dwLength = ctypes.sizeof(self)


class PERFORMANCE_INFORMATION(ctypes.Structure):
    """Maps to PERFORMANCE_INFORMATION in psapi.h (GetPerformanceInfo)."""
    _fields_ = [
        ("cb",                wt.DWORD),
        ("CommitTotal",       ctypes.c_size_t),
        ("CommitLimit",       ctypes.c_size_t),
        ("CommitPeak",        ctypes.c_size_t),
        ("PhysicalTotal",     ctypes.c_size_t),
        ("PhysicalAvailable", ctypes.c_size_t),
        ("SystemCache",       ctypes.c_size_t),
        ("KernelTotal",       ctypes.c_size_t),
        ("KernelPaged",       ctypes.c_size_t),
        ("KernelNonpaged",    ctypes.c_size_t),
        ("PageSize",          ctypes.c_size_t),
        ("HandleCount",       wt.DWORD),
        ("ProcessCount",      wt.DWORD),
        ("ThreadCount",       wt.DWORD),
    ]
    def __init__(self):
        super().__init__()
        self.cb = ctypes.sizeof(self)


def _get_global_memory_status() -> Dict[str, Any]:
    """Call GlobalMemoryStatusEx and return a dict of raw fields."""
    ms = MEMORYSTATUSEX()
    ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    if not ok:
        raise ctypes.WinError()
    return {
        "memory_load_pct":        ms.dwMemoryLoad,
        "total_physical":         ms.ullTotalPhys,
        "available_physical":     ms.ullAvailPhys,
        "total_pagefile":         ms.ullTotalPageFile,
        "available_pagefile":     ms.ullAvailPageFile,
        "total_virtual":          ms.ullTotalVirtual,
        "available_virtual":      ms.ullAvailVirtual,
    }


def _get_performance_info() -> Dict[str, Any]:
    """Call GetPerformanceInfo (psapi.dll) and return a dict of raw fields."""
    pi = PERFORMANCE_INFORMATION()
    psapi = ctypes.windll.psapi
    ok = psapi.GetPerformanceInfo(ctypes.byref(pi), ctypes.sizeof(pi))
    if not ok:
        raise ctypes.WinError()
    return {
        "commit_total":      pi.CommitTotal,
        "commit_limit":      pi.CommitLimit,
        "physical_total":    pi.PhysicalTotal,
        "physical_avail":    pi.PhysicalAvailable,
        "system_cache":      pi.SystemCache,
        "kernel_total":      pi.KernelTotal,
        "kernel_nonpaged":   pi.KernelNonpaged,
        "page_size":         pi.PageSize,
        "handle_count":      pi.HandleCount,
        "process_count":     pi.ProcessCount,
        "thread_count":      pi.ThreadCount,
    }


def _mb(b: int) -> float:
    """Convert bytes to MiB (2^20)."""
    return round(b / (1024 ** 2), 2)


def collect_system_memory() -> Dict[str, Any]:
    """
    Return a snapshot of current system memory statistics.

    All size values are expressed in MiB.  The page_size_bytes field
    is kept in bytes because it is a hardware/OS constant.

    Falls back gracefully: if a Windows API call fails (e.g. in a
    sandboxed test environment), psutil values are used and the
    extended fields are set to None.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    # ── psutil baseline (always available) ────────────────────────────────
    vm   = psutil.virtual_memory()
    swap = psutil.swap_memory()

    result: Dict[str, Any] = {
        "timestamp":              ts,
        "total_physical_mb":      _mb(vm.total),
        "available_physical_mb":  _mb(vm.available),
        "used_physical_mb":       _mb(vm.used),
        "memory_percent":         vm.percent,
        # pagefile baseline from psutil
        "pagefile_total_mb":      _mb(swap.total)   if swap.total else None,
        "pagefile_used_mb":       _mb(swap.used)    if swap.total else None,
        "pagefile_percent":       swap.percent       if swap.total else None,
        # virtual memory
        "total_virtual_mb":       None,
        "available_virtual_mb":   None,
        # extended
        "page_size_bytes":        None,
        "system_cache_mb":        None,
        "commit_total_mb":        None,
        "commit_limit_mb":        None,
        "kernel_nonpaged_mb":     None,
        "process_count":          None,
        "thread_count":           None,
        "handle_count":           None,
        # CPU
        "cpu_percent":            psutil.cpu_percent(interval=0.2),
        "cpu_count":              psutil.cpu_count(logical=True),
        "source":                 "psutil+winapi",
    }

    # ── GlobalMemoryStatusEx override ─────────────────────────────────────
    try:
        gms = _get_global_memory_status()
        result["total_physical_mb"]     = _mb(gms["total_physical"])
        result["available_physical_mb"] = _mb(gms["available_physical"])
        result["used_physical_mb"]      = _mb(gms["total_physical"] - gms["available_physical"])
        result["memory_percent"]        = gms["memory_load_pct"]
        result["pagefile_total_mb"]     = _mb(gms["total_pagefile"])
        result["pagefile_used_mb"]      = _mb(gms["total_pagefile"] - gms["available_pagefile"])
        result["pagefile_percent"]      = round(
            (gms["total_pagefile"] - gms["available_pagefile"]) / gms["total_pagefile"] * 100, 2
        ) if gms["total_pagefile"] else None
        result["total_virtual_mb"]      = _mb(gms["total_virtual"])
        result["available_virtual_mb"]  = _mb(gms["available_virtual"])
    except Exception:
        pass  # keep psutil values

    # ── GetPerformanceInfo ─────────────────────────────────────────────────
    try:
        pi = _get_performance_info()
        ps = pi["page_size"]
        result["page_size_bytes"]     = ps
        result["system_cache_mb"]     = _mb(pi["system_cache"] * ps)
        result["commit_total_mb"]     = _mb(pi["commit_total"] * ps)
        result["commit_limit_mb"]     = _mb(pi["commit_limit"] * ps)
        result["kernel_nonpaged_mb"]  = _mb(pi["kernel_nonpaged"] * ps)
        result["process_count"]       = pi["process_count"]
        result["thread_count"]        = pi["thread_count"]
        result["handle_count"]        = pi["handle_count"]
    except Exception:
        # Fallback process count
        try:
            result["process_count"] = len(psutil.pids())
        except Exception:
            pass

    return result


def get_page_size() -> int:
    """Return the Windows page size in bytes (default 4096)."""
    try:
        si = ctypes.wintypes.SYSTEM_INFO()
        ctypes.windll.kernel32.GetSystemInfo(ctypes.byref(si))
        return si.dwPageSize
    except Exception:
        try:
            pi = _get_performance_info()
            return pi["page_size"]
        except Exception:
            return 4096
