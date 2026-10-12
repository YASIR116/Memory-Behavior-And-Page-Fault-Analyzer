"""
config.py – Application-wide configuration and constants.
"""
import os

# ─── Application metadata ────────────────────────────────────────────────────
APP_TITLE = "Windows Memory Behavior and Page-Fault Analyzer"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = (
    "Investigates how memory allocation and access patterns affect "
    "process memory usage and page-fault activity on Windows."
)

# ─── Database ─────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "memory_analyzer.db")

# ─── Experiment defaults ──────────────────────────────────────────────────────
DEFAULT_ALLOC_MB = 64          # MiB
MAX_ALLOC_MB = 256             # hard cap; also clamped to 10 % of total RAM
DEFAULT_DURATION_S = 12        # seconds
DEFAULT_SAMPLE_INTERVAL_S = 1  # seconds
DEFAULT_RANDOM_SEED = 42

# ─── Monitoring ───────────────────────────────────────────────────────────────
DEFAULT_MONITOR_INTERVAL_S = 2  # dashboard auto-refresh interval (seconds)

# ─── Workload types ───────────────────────────────────────────────────────────
WORKLOAD_ALLOCATION = "allocation"
WORKLOAD_SEQUENTIAL = "sequential"
WORKLOAD_REPEATED   = "repeated"
WORKLOAD_RANDOM     = "random"
WORKLOAD_RELEASE    = "release"

WORKLOAD_LABELS = {
    WORKLOAD_ALLOCATION: "A – Memory Allocation",
    WORKLOAD_SEQUENTIAL: "B – Sequential Access",
    WORKLOAD_REPEATED:   "C – Repeated Access",
    WORKLOAD_RANDOM:     "D – Random Access",
    WORKLOAD_RELEASE:    "E – Memory Release",
}

# ─── UI colour palette ────────────────────────────────────────────────────────
COLOR_PRIMARY     = "#1f77b4"
COLOR_SECONDARY   = "#ff7f0e"
COLOR_SUCCESS     = "#2ca02c"
COLOR_DANGER      = "#d62728"
COLOR_WORKING_SET = "#1f77b4"
COLOR_VIRTUAL_MEM = "#ff7f0e"
COLOR_AVAILABLE   = "#2ca02c"
COLOR_PAGE_FAULT  = "#9467bd"
