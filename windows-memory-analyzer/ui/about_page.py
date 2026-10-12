"""
ui/about_page.py
─────────────────────────────────────────────────────────────────────────────
Streamlit page: About and Metric Definitions
"""

import streamlit as st
from analysis.metrics import COUNTER_DESCRIPTIONS
from config import APP_TITLE, APP_VERSION


def render_about():
    st.header("ℹ️ About & Metric Definitions")

    st.markdown(f"""
## {APP_TITLE}
**Version:** {APP_VERSION}

This application investigates how memory allocation and access patterns
affect process memory usage and page-fault activity on **Windows 10/11**.

It is a fourth-year university mini-project for the subject
*Windows and Linux Internals* (Windows implementation).
""")

    st.markdown("---")
    st.subheader("Architecture Overview")
    st.markdown("""
| Module | Purpose |
|--------|---------|
| `collectors/system_memory.py` | System RAM, pagefile, virtual memory via `GlobalMemoryStatusEx` + `GetPerformanceInfo` |
| `collectors/process_memory.py` | Per-process counters via `GetProcessMemoryInfo` (PROCESS_MEMORY_COUNTERS_EX) |
| `collectors/page_faults.py` | Page-fault monitoring, series collection, and interpretation |
| `experiments/memory_workloads.py` | Five workloads (A–E) running in subprocess, emitting samples via Queue |
| `experiments/workload_runner.py` | Subprocess lifecycle management, queue draining, cancellation |
| `experiments/experiment_manager.py` | High-level facade: start/stop/persist/finalise |
| `analysis/metrics.py` | Pure metric helpers: conversion, delta, rate, counter catalogue |
| `analysis/comparison.py` | Side-by-side experiment comparison logic |
| `storage/database.py` | SQLite persistence (WAL mode, experiments + samples tables) |
| `storage/export.py` | CSV export for summaries and raw samples |
| `ui/*` | Streamlit pages (Dashboard, Inspector, Experiments, Results, Comparison, History) |
""")

    st.markdown("---")
    st.subheader("Windows Memory Concepts")

    st.markdown("""
### Physical Memory vs Virtual Memory
**Physical memory (RAM)** is the actual hardware.  A process's **working set**
is the subset of its virtual address space currently backed by physical pages.

**Virtual memory** is the process's full address space (can be much larger than RAM).
Pages not in the working set are either on disk, on the standby list, or simply
not yet allocated.

### The Windows Page Fault
A page fault occurs when the CPU accesses a virtual page not currently mapped.
Windows resolves it as:

| Type | Cause | Disk I/O? |
|------|-------|-----------|
| Zero-demand fault | New private page — filled with zeros | ❌ No |
| Soft fault (standby) | Recently evicted page still in RAM | ❌ No |
| Copy-on-write fault | Shared page needs a private copy | ❌ No |
| Hard fault (page-in) | Page must be read from pagefile or file | ✅ Yes |

`PageFaultCount` counts **all** of these types together.
A high count does not imply disk activity.

### Working Set vs Private Bytes
- **Working Set** (`WorkingSetSize`) — physical pages currently resident.
- **Private Bytes** (`PagefileUsage`) — virtual pages committed exclusively to this process.
  A process can have large private bytes but a small working set if most pages are paged out.

### Pagefile
The pagefile is a system-managed file on disk that backs committed virtual memory
not currently resident in RAM.  A page in the pagefile is only read when its virtual
page is accessed (hard fault).  The pagefile does not need to store all committed
memory simultaneously — only evicted pages.
""")

    st.markdown("---")
    st.subheader("Counter Reference")

    for key, cd in COUNTER_DESCRIPTIONS.items():
        with st.expander(f"**{cd['name']}** ({cd['scope']}, {cd['kind']})"):
            st.markdown(f"**Source:** `{cd['source']}`")
            st.markdown(f"**Units:** {cd['units']}")
            st.markdown(cd["note"])

    st.markdown("---")
    st.subheader("Technology Stack")
    st.markdown("""
| Component | Library |
|-----------|---------|
| UI | Streamlit |
| Charts | Plotly |
| System metrics | psutil |
| Windows APIs | ctypes (kernel32, psapi) |
| Database | SQLite (built-in) |
| Export | csv (built-in) |
| Tests | pytest |
""")
