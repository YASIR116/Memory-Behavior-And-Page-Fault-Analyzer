"""
storage/export.py
─────────────────────────────────────────────────────────────────────────────
CSV export helpers for experiment summaries and raw sample data.
"""

import csv
import io
from typing import List, Dict, Any


def samples_to_csv(samples: List[Dict[str, Any]]) -> str:
    """
    Serialise a list of sample dicts to a CSV string (UTF-8).
    All columns present in any sample are included; missing values are ''.
    """
    if not samples:
        return ""

    # Collect all unique keys, keeping a sensible ordering
    ordered_keys = [
        "exp_id", "seq", "timestamp", "elapsed_s",
        "page_fault_count", "working_set_mb", "virtual_mem_mb",
        "available_ram_mb", "system_memory_pct",
    ]
    all_keys = list(ordered_keys)
    for s in samples:
        for k in s:
            if k not in all_keys:
                all_keys.append(k)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for s in samples:
        writer.writerow({k: s.get(k, "") for k in all_keys})

    return buf.getvalue()


def summaries_to_csv(experiments: List[Dict[str, Any]]) -> str:
    """
    Serialise a list of experiment summary dicts to a CSV string.
    """
    if not experiments:
        return ""

    ordered_keys = [
        "id", "created_at", "workload", "alloc_mb", "duration_s",
        "interval_s", "random_seed", "status",
        "initial_page_faults", "final_page_faults", "fault_delta",
        "fault_rate", "peak_working_set_mb", "final_working_set_mb",
        "pagefile_usage_mb", "available_ram_mb",
    ]
    all_keys = list(ordered_keys)
    for e in experiments:
        for k in e:
            if k not in all_keys and k not in ("interpretation", "summary_json"):
                all_keys.append(k)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for e in experiments:
        writer.writerow({k: e.get(k, "") for k in all_keys})

    return buf.getvalue()
