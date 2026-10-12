"""
ui/results_page.py
─────────────────────────────────────────────────────────────────────────────
Streamlit page: Page-Fault Analysis
Shows detailed page-fault counter analysis for the most recently
completed experiment and any selected historical experiment.
"""

import streamlit as st
import plotly.graph_objects as go

from experiments.experiment_manager import ExperimentManager
from analysis.metrics import fault_deltas_from_samples, format_mb, counter_rate
from collectors.page_faults import interpret_page_fault_delta
from config import COLOR_PAGE_FAULT, COLOR_WORKING_SET, WORKLOAD_LABELS


def _get_manager() -> ExperimentManager:
    if "exp_manager" not in st.session_state:
        st.session_state["exp_manager"] = ExperimentManager()
    return st.session_state["exp_manager"]


def _render_fault_analysis(exp: dict, samples: list) -> None:
    workload = exp.get("workload", "")
    label    = WORKLOAD_LABELS.get(workload, workload)

    st.subheader(f"📋 Experiment #{exp['id']} — {label}")

    c1, c2, c3, c4 = st.columns(4)
    init_pf = exp.get("initial_page_faults")
    fin_pf  = exp.get("final_page_faults")
    delta   = exp.get("fault_delta")
    dur     = exp.get("duration_s")
    rate    = counter_rate(delta, dur)

    c1.metric("Initial Fault Count",
              f"{init_pf:,}" if init_pf is not None else "N/A",
              help="Cumulative PageFaultCount at experiment start")
    c2.metric("Final Fault Count",
              f"{fin_pf:,}" if fin_pf is not None else "N/A",
              help="Cumulative PageFaultCount at experiment end")
    c3.metric("Fault Count Δ",
              f"{delta:,}" if delta is not None else "N/A",
              help="Faults accumulated during the experiment (final − initial)")
    c4.metric("Fault Rate",
              f"{rate:.1f} /s" if rate is not None else "N/A",
              help="Δ / duration_s  — faults per second on average")

    st.markdown("**Interpretation:**")
    st.info(exp.get("interpretation") or interpret_page_fault_delta(delta, workload))

    with st.expander("⚠️ Counter Limitations"):
        st.markdown("""
**Windows `PageFaultCount` limitations:**

1. It is a **cumulative DWORD** counter — it counts all faults since process start and wraps at 2³².
2. It **does not distinguish** between:
   - **Soft faults** (page resolved from standby list — no disk I/O)
   - **Zero-demand faults** (new page, filled with zeros — no disk I/O)
   - **Copy-on-write faults** (private copy made — no disk I/O)
   - **Hard faults** (page read from pagefile or file — disk I/O occurs)
3. A large `PageFaultCount` **does not imply** heavy disk I/O.
4. Hard faults can be observed separately via the Windows Performance Counter
   `Process\\Page Faults/sec` → `Memory\\Page Reads/sec` but that API is heavier.
5. This experiment records the delta for the experiment window only — not the process lifetime.
""")

    if not samples:
        st.info("No time-series samples stored for this experiment.")
        return

    elapsed    = [s.get("elapsed_s", 0) for s in samples]
    ws_mb      = [s.get("working_set_mb") for s in samples]
    pf_counts  = [s.get("page_fault_count") for s in samples]
    pf_deltas  = fault_deltas_from_samples(samples)

    # Working set + fault count dual-axis
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=elapsed, y=ws_mb,
        name="Working Set (MiB)", yaxis="y1",
        line=dict(color=COLOR_WORKING_SET),
    ))
    fig.add_trace(go.Scatter(
        x=elapsed, y=pf_counts,
        name="Cumulative Page Faults", yaxis="y2",
        line=dict(color=COLOR_PAGE_FAULT, dash="dot"),
    ))
    fig.update_layout(
        title="Working Set vs Cumulative Page Faults",
        xaxis_title="Elapsed (s)",
        yaxis =dict(title="Working Set (MiB)", side="left",  color=COLOR_WORKING_SET),
        yaxis2=dict(title="Cumulative Page Faults", side="right",
                    overlaying="y", color=COLOR_PAGE_FAULT),
        legend=dict(orientation="h"),
        height=360,
        margin=dict(l=60, r=60, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per-interval delta bar chart
    valid_pairs = [(e, d) for e, d in zip(elapsed[1:], pf_deltas[1:]) if d is not None]
    if valid_pairs:
        fig2 = go.Figure(go.Bar(
            x=[v[0] for v in valid_pairs],
            y=[v[1] for v in valid_pairs],
            marker_color=COLOR_PAGE_FAULT,
            name="Fault Δ per interval",
        ))
        fig2.update_layout(
            title="Page-Fault Count Δ per Sampling Interval",
            xaxis_title="Elapsed (s)",
            yaxis_title="Fault Count Δ",
            height=280,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Raw sample table (collapsed)
    with st.expander("Raw Sample Data"):
        cols = ["elapsed_s", "page_fault_count", "working_set_mb",
                "virtual_mem_mb", "available_ram_mb"]
        rows = [{c: s.get(c) for c in cols} for s in samples]
        st.dataframe(rows, use_container_width=True)


def render_results():
    st.header("📉 Page-Fault Analysis")
    st.caption(
        "Detailed analysis of Windows `PageFaultCount` deltas for completed experiments."
    )

    manager = _get_manager()
    exps    = manager.list_experiments()

    completed = [e for e in exps if e.get("status") == "completed"]
    if not completed:
        st.info("No completed experiments yet.  Run an experiment from the **Memory Experiments** page.")
        return

    # Selector
    labels = [
        f"#{e['id']} — {WORKLOAD_LABELS.get(e['workload'], e['workload'])} "
        f"({e['alloc_mb']} MiB, {e['created_at'][:10]})"
        for e in completed
    ]
    chosen = st.selectbox("Select experiment", labels)
    if not chosen:
        return

    idx = labels.index(chosen)
    exp = completed[idx]
    samples = manager.get_samples(exp["id"])

    _render_fault_analysis(exp, samples)
