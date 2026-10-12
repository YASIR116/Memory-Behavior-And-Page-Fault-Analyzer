"""
ui/comparison_page.py  (maps to experiments_page comparison tab)
─────────────────────────────────────────────────────────────────────────────
Streamlit page: Experiment Comparison
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from experiments.experiment_manager import ExperimentManager
from analysis.comparison import compare_experiments
from config import WORKLOAD_LABELS
from analysis.metrics import format_mb


def _get_manager() -> ExperimentManager:
    if "exp_manager" not in st.session_state:
        st.session_state["exp_manager"] = ExperimentManager()
    return st.session_state["exp_manager"]


def render_comparison():
    st.header("⚖️ Experiment Comparison")
    st.caption("Select two or more completed experiments to compare side-by-side.")

    manager = _get_manager()
    exps    = manager.list_experiments()
    completed = [e for e in exps if e.get("status") == "completed"]

    if len(completed) < 2:
        st.info(
            "You need at least **two completed experiments** to compare. "
            "Run more experiments from the **Memory Experiments** page."
        )
        return

    labels = [
        f"#{e['id']} — {WORKLOAD_LABELS.get(e['workload'], e['workload'])} "
        f"({e['alloc_mb']} MiB)"
        for e in completed
    ]

    chosen_labels = st.multiselect(
        "Select experiments (2 or more)",
        options=labels,
        default=labels[:min(2, len(labels))],
    )

    if len(chosen_labels) < 2:
        st.warning("Select at least two experiments.")
        return

    chosen_exps = [completed[labels.index(lbl)] for lbl in chosen_labels]

    try:
        result = compare_experiments(chosen_exps)
    except ValueError as exc:
        st.error(str(exc))
        return

    # ── Warnings ─────────────────────────────────────────────────────────
    for w in result["warnings"]:
        st.warning(w)

    # ── Side-by-side table ────────────────────────────────────────────────
    st.subheader("Side-by-Side Comparison")

    table_data = {"Metric": [r["label"] for r in result["rows"]]}
    for i, lbl in enumerate(chosen_labels):
        table_data[lbl] = [r["values"][i] for r in result["rows"]]

    import pandas as pd
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Comparison charts ─────────────────────────────────────────────────
    st.subheader("Comparison Charts")

    CHART_DISPLAY = [
        ("peak_working_set_mb", "Peak Working Set (MiB)"),
        ("fault_delta",          "Page-Fault Count Δ"),
        ("fault_rate",           "Fault Rate (faults/s)"),
    ]

    cols = st.columns(len(CHART_DISPLAY))
    chart_data = {c["metric"]: c for c in result["charts"]}

    for col, (metric, label) in zip(cols, CHART_DISPLAY):
        cd = chart_data.get(metric)
        if not cd:
            continue
        with col:
            fig = go.Figure(go.Bar(
                x=cd["labels"],
                y=cd["values"],
                text=[f"{v:,.1f}" for v in cd["values"]],
                textposition="auto",
            ))
            fig.update_layout(
                title=label,
                xaxis_tickangle=-30,
                height=320,
                margin=dict(l=20, r=10, t=50, b=60),
                yaxis_title=label,
            )
            col.plotly_chart(fig, use_container_width=True)

    # ── Time-series overlay (working set) ─────────────────────────────────
    st.subheader("Working Set Over Time — Overlay")
    fig_ts = go.Figure()
    colors = px.colors.qualitative.Plotly

    for i, exp in enumerate(chosen_exps):
        samples = manager.get_samples(exp["id"])
        if not samples:
            continue
        elapsed = [s.get("elapsed_s", 0) for s in samples]
        ws_mb   = [s.get("working_set_mb") for s in samples]
        lbl = f"#{exp['id']} {WORKLOAD_LABELS.get(exp['workload'], exp['workload'])}"
        fig_ts.add_trace(go.Scatter(
            x=elapsed, y=ws_mb, name=lbl,
            line=dict(color=colors[i % len(colors)]),
        ))

    fig_ts.update_layout(
        title="Working Set Size Over Time (all selected experiments)",
        xaxis_title="Elapsed (s)",
        yaxis_title="Working Set (MiB)",
        legend=dict(orientation="h"),
        height=380,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    # ── Page-fault delta overlay ───────────────────────────────────────────
    st.subheader("Cumulative Page-Fault Count Over Time — Overlay")
    fig_pf = go.Figure()

    for i, exp in enumerate(chosen_exps):
        samples = manager.get_samples(exp["id"])
        if not samples:
            continue
        elapsed   = [s.get("elapsed_s", 0) for s in samples]
        pf_counts = [s.get("page_fault_count") for s in samples]
        # Normalise to delta from start for comparison
        base = next((p for p in pf_counts if p is not None), None)
        if base is not None:
            pf_deltas_abs = [
                (p - base if p is not None else None) for p in pf_counts
            ]
        else:
            pf_deltas_abs = pf_counts

        lbl = f"#{exp['id']} {WORKLOAD_LABELS.get(exp['workload'], exp['workload'])}"
        fig_pf.add_trace(go.Scatter(
            x=elapsed, y=pf_deltas_abs, name=lbl,
            line=dict(color=colors[i % len(colors)], dash="dot"),
        ))

    fig_pf.update_layout(
        title="Cumulative Page-Fault Δ from Experiment Start",
        xaxis_title="Elapsed (s)",
        yaxis_title="Fault Count Δ (from experiment start)",
        legend=dict(orientation="h"),
        height=320,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    st.plotly_chart(fig_pf, use_container_width=True)

    with st.expander("ℹ️ Comparison Caveats"):
        st.markdown("""
- Fault counts depend on system memory pressure at the time of the experiment.
- A single run is not sufficient to claim one access pattern is always better.
- Experiments with different allocation sizes or durations should be compared using **fault rate** (faults/s), not raw deltas.
- Windows may have pre-fetched or cached pages between experiments, affecting working-set growth rates.
- This comparison reflects **Windows only** behavior — no Linux conclusions are drawn.
""")
