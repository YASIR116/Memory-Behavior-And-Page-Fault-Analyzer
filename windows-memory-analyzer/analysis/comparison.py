"""
analysis/comparison.py
─────────────────────────────────────────────────────────────────────────────
Experiment comparison logic.

Produces side-by-side comparison tables and diff metrics from two or more
saved experiment records.  Pure Python – no Windows API dependencies.
"""

from typing import Dict, Any, List, Optional
from analysis.metrics import counter_delta, counter_rate, format_mb


def compare_experiments(
    experiments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compare a list of experiment summary records.

    Each record is expected to contain keys from ExperimentDB.get_experiment().

    Returns a dict with:
      • rows    – list of {field, label, values} for table display
      • charts  – list of {metric, label, values} for graph display
      • warning – list of warnings about incompatible configs
    """
    if len(experiments) < 2:
        raise ValueError("Need at least two experiments to compare.")

    warnings: List[str] = []

    # Check compatibility
    alloc_sizes = {e.get("alloc_mb") for e in experiments}
    if len(alloc_sizes) > 1:
        warnings.append(
            "Experiments were run with different allocation sizes "
            f"({', '.join(str(s) + ' MiB' for s in sorted(alloc_sizes))}). "
            "Comparing fault counts directly may be misleading."
        )

    durations = {round(float(e.get("duration_s", 0)), 0) for e in experiments}
    if len(durations) > 1:
        warnings.append(
            "Experiments have different durations.  Fault rates (per second) "
            "are a more comparable metric than raw deltas."
        )

    # Build comparison rows
    FIELDS = [
        ("workload",           "Workload Type"),
        ("alloc_mb",           "Allocation Size (MiB)"),
        ("duration_s",         "Duration (s)"),
        ("interval_s",         "Sample Interval (s)"),
        ("peak_working_set_mb","Peak Working Set (MiB)"),
        ("final_working_set_mb","Final Working Set (MiB)"),
        ("pagefile_usage_mb",  "Final Private Bytes (MiB)"),
        ("available_ram_mb",   "Final Available RAM (MiB)"),
        ("fault_delta",        "Page-Fault Count Δ"),
        ("fault_rate",         "Fault Rate (faults/s)"),
        ("status",             "Experiment Status"),
    ]

    rows = []
    for field, label in FIELDS:
        values = []
        for e in experiments:
            v = e.get(field)
            if v is None and field == "fault_rate":
                # compute it
                delta    = e.get("fault_delta")
                duration = e.get("duration_s")
                v = counter_rate(delta, duration)
            if v is None:
                values.append("N/A")
            elif isinstance(v, float):
                values.append(f"{v:,.2f}")
            else:
                values.append(str(v))
        rows.append({"field": field, "label": label, "values": values})

    # Build chart data (numeric metrics only)
    CHART_METRICS = [
        ("peak_working_set_mb",  "Peak Working Set (MiB)"),
        ("fault_delta",          "Page-Fault Count Δ"),
        ("fault_rate",           "Fault Rate (faults/s)"),
        ("alloc_mb",             "Allocation Size (MiB)"),
        ("duration_s",           "Duration (s)"),
    ]

    charts = []
    for metric, label in CHART_METRICS:
        values = []
        labels = []
        for e in experiments:
            v = e.get(metric)
            if v is None and metric == "fault_rate":
                v = counter_rate(e.get("fault_delta"), e.get("duration_s"))
            try:
                v = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                v = 0.0
            values.append(v)
            labels.append(
                f"{e.get('workload','?')} #{e.get('id','?')}"
            )
        charts.append({"metric": metric, "label": label, "labels": labels, "values": values})

    return {
        "rows":     rows,
        "charts":   charts,
        "warnings": warnings,
        "n":        len(experiments),
    }


def diff_summary(exp_a: Dict[str, Any], exp_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a simple numeric diff between two experiments.
    Positive delta_b means exp_b has a higher value.
    """
    NUMERIC_KEYS = [
        "alloc_mb", "duration_s", "peak_working_set_mb",
        "fault_delta", "available_ram_mb",
    ]
    diffs = {}
    for k in NUMERIC_KEYS:
        a = exp_a.get(k)
        b = exp_b.get(k)
        if a is not None and b is not None:
            try:
                diffs[k] = round(float(b) - float(a), 3)
            except (TypeError, ValueError):
                diffs[k] = None
        else:
            diffs[k] = None
    return diffs
