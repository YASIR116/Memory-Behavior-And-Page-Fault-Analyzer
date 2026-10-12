"""
ui/experiments_page.py
─────────────────────────────────────────────────────────────────────────────
Streamlit page: Memory Experiments
Configure, run, monitor, and save controlled memory workloads.
"""

import time
import streamlit as st
import plotly.graph_objects as go
import psutil

from experiments.experiment_manager import ExperimentManager
from analysis.metrics import format_mb, fault_deltas_from_samples
from config import (
    DEFAULT_ALLOC_MB, MAX_ALLOC_MB, DEFAULT_DURATION_S,
    DEFAULT_SAMPLE_INTERVAL_S, DEFAULT_RANDOM_SEED, WORKLOAD_LABELS,
    COLOR_WORKING_SET, COLOR_VIRTUAL_MEM, COLOR_AVAILABLE, COLOR_PAGE_FAULT,
)


def _get_manager() -> ExperimentManager:
    if "exp_manager" not in st.session_state:
        st.session_state["exp_manager"] = ExperimentManager()
    return st.session_state["exp_manager"]


def _max_alloc_mb() -> float:
    """Return the smaller of MAX_ALLOC_MB and 10% of total RAM."""
    try:
        total_mb = psutil.virtual_memory().total / (1024 ** 2)
        return min(MAX_ALLOC_MB, total_mb * 0.10)
    except Exception:
        return MAX_ALLOC_MB


def _build_live_charts(samples: list, workload: str) -> None:
    if len(samples) < 2:
        return

    elapsed = [s.get("elapsed_s", 0) for s in samples]
    ws_mb   = [s.get("working_set_mb") for s in samples]
    vm_mb   = [s.get("virtual_mem_mb") for s in samples]
    avail   = [s.get("available_ram_mb") for s in samples]
    pf_cnts = [s.get("page_fault_count") for s in samples]
    pf_deltas = fault_deltas_from_samples(samples)

    col_a, col_b = st.columns(2)

    # Working set chart
    with col_a:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=elapsed, y=ws_mb, name="Working Set",
            line=dict(color=COLOR_WORKING_SET), fill="tozeroy",
        ))
        fig1.add_trace(go.Scatter(
            x=elapsed, y=vm_mb, name="Private Bytes",
            line=dict(color=COLOR_VIRTUAL_MEM, dash="dash"),
        ))
        fig1.update_layout(
            title=f"Process Memory — {WORKLOAD_LABELS.get(workload, workload)}",
            xaxis_title="Elapsed (s)",
            yaxis_title="MiB",
            legend=dict(orientation="h"),
            height=300,
            margin=dict(l=40, r=10, t=40, b=40),
        )
        st.plotly_chart(fig1, use_container_width=True)

    # Available RAM
    with col_b:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=elapsed, y=avail, name="Available RAM",
            line=dict(color=COLOR_AVAILABLE), fill="tozeroy",
        ))
        fig2.update_layout(
            title="System Available RAM",
            xaxis_title="Elapsed (s)",
            yaxis_title="MiB",
            height=300,
            margin=dict(l=40, r=10, t=40, b=40),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Page-fault delta per interval
    valid_deltas = [(e, d) for e, d in zip(elapsed[1:], pf_deltas[1:])
                    if d is not None]
    if valid_deltas:
        fd_x = [v[0] for v in valid_deltas]
        fd_y = [v[1] for v in valid_deltas]
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=fd_x, y=fd_y, name="Fault Δ per interval",
            marker_color=COLOR_PAGE_FAULT,
        ))
        fig3.update_layout(
            title="Page-Fault Count Δ per Sampling Interval",
            xaxis_title="Elapsed (s)",
            yaxis_title="Fault Δ",
            height=250,
            margin=dict(l=40, r=10, t=40, b=40),
        )
        st.plotly_chart(fig3, use_container_width=True)


def render_experiments():
    st.header("🧪 Memory Experiments")

    manager = _get_manager()
    max_alloc = _max_alloc_mb()

    # ── Configuration sidebar ────────────────────────────────────────────
    with st.sidebar:
        st.subheader("Experiment Configuration")

        workload = st.selectbox(
            "Workload Type",
            options=list(WORKLOAD_LABELS.keys()),
            format_func=lambda k: WORKLOAD_LABELS[k],
            key="exp_workload",
        )
        alloc_mb = st.slider(
            "Allocation Size (MiB)",
            min_value=4, max_value=int(max_alloc),
            value=min(DEFAULT_ALLOC_MB, int(max_alloc)),
            key="exp_alloc_mb",
        )
        duration_s = st.slider(
            "Duration (seconds)", 5, 60, DEFAULT_DURATION_S, key="exp_duration"
        )
        interval_s = st.select_slider(
            "Sample Interval (s)",
            options=[0.5, 1.0, 2.0, 5.0],
            value=DEFAULT_SAMPLE_INTERVAL_S,
            key="exp_interval",
        )
        if workload == "random":
            seed = st.number_input("Random Seed", value=DEFAULT_RANDOM_SEED,
                                   step=1, key="exp_seed")
        else:
            seed = DEFAULT_RANDOM_SEED

        st.markdown("---")
        st.caption(f"Max allowed allocation: **{max_alloc:.0f} MiB**")

    cfg = {
        "alloc_mb":   alloc_mb,
        "duration_s": duration_s,
        "interval_s": interval_s,
        "random_seed": seed,
    }

    # ── Workload description ─────────────────────────────────────────────
    DESCRIPTIONS = {
        "allocation": (
            "**Experiment A – Memory Allocation:** Allocates a private memory block "
            "without deliberately accessing every page.  On Windows, virtual memory "
            "is *reserved* and *committed* but pages are demand-zero: physical RAM "
            "is only assigned when a page is first accessed.  This experiment lets "
            "you observe the difference between committed virtual size and actual "
            "working-set size."
        ),
        "sequential": (
            "**Experiment B – Sequential Access:** Allocates a block and then writes "
            "one byte to every page in address order.  Each first-touch triggers a "
            "page fault; Windows resolves it by mapping a zero-filled page.  Expect "
            "working-set size to rise linearly and page-fault count to increase "
            "proportionally to the number of pages."
        ),
        "repeated": (
            "**Experiment C – Repeated Access:** Initialises a block then reads and "
            "writes it multiple times.  After the first pass, pages are resident; "
            "subsequent passes should produce far fewer additional faults unless "
            "Windows evicts pages under memory pressure."
        ),
        "random": (
            "**Experiment D – Random Access:** Accesses a shuffled page list using "
            "a configurable seed (reproducible).  On a machine with ample RAM, total "
            "fault count is often similar to sequential; however, cache-miss patterns "
            "differ.  Outcomes depend on available RAM, working-set size, and OS "
            "memory pressure."
        ),
        "release": (
            "**Experiment E – Memory Release:** Allocates, touches all pages, holds "
            "briefly, then frees the allocation.  After release, process working-set "
            "size decreases; however, system-wide physical RAM usage may remain "
            "elevated briefly as Windows places freed pages on the standby list."
        ),
    }

    st.info(DESCRIPTIONS.get(workload, ""))

    # ── Control buttons ──────────────────────────────────────────────────
    b1, b2, b3 = st.columns(3)

    with b1:
        start_pressed = st.button(
            "▶ Start Experiment",
            disabled=manager.is_running,
            use_container_width=True,
            type="primary",
        )
    with b2:
        stop_pressed = st.button(
            "⏹ Stop",
            disabled=not manager.is_running,
            use_container_width=True,
        )
    with b3:
        reset_pressed = st.button("🔁 Reset", use_container_width=True,
                                  disabled=manager.is_running)

    if reset_pressed:
        for key in ["exp_samples", "exp_summary", "exp_id", "exp_workload_run"]:
            st.session_state.pop(key, None)
        st.rerun()

    # ── Start ─────────────────────────────────────────────────────────────
    if start_pressed and not manager.is_running:
        st.session_state.pop("exp_samples", None)
        st.session_state.pop("exp_summary", None)
        try:
            exp_id = manager.start_experiment(workload=workload, cfg=cfg)
            st.session_state["exp_id"]          = exp_id
            st.session_state["exp_workload_run"] = workload
            st.success(f"Experiment #{exp_id} started.")
        except ValueError as exc:
            st.error(f"Configuration error: {exc}")
            return

    # ── Stop ──────────────────────────────────────────────────────────────
    if stop_pressed and manager.is_running:
        manager.stop_experiment()
        st.warning("Experiment cancelled.")

    # ── Live monitoring ───────────────────────────────────────────────────
    current_workload = st.session_state.get("exp_workload_run", workload)

    if manager.is_running:
        status_placeholder = st.empty()
        chart_placeholder  = st.container()

        with status_placeholder:
            st.info(f"⏳ Experiment running…  ({len(manager.runner.samples)} samples collected)")

        # Flush to DB and display
        manager.collect_and_save()
        samples = manager.runner.samples

        with chart_placeholder:
            _build_live_charts(samples, current_workload)

        time.sleep(max(0.5, float(interval_s)))
        st.rerun()

    # ── Post-run results ──────────────────────────────────────────────────
    elif st.session_state.get("exp_id") and not manager.is_running:
        # Finalise once
        if not st.session_state.get("exp_summary"):
            summary = manager.finalise()
            if summary:
                st.session_state["exp_summary"] = summary
                st.session_state["exp_samples"] = manager.runner.samples
                st.success("✅ Experiment complete and saved.")
            elif manager.runner.errors:
                for e in manager.runner.errors:
                    st.error(f"Worker error: {e}")

        summary = st.session_state.get("exp_summary")
        samples = st.session_state.get("exp_samples", [])

        if summary:
            st.subheader("📊 Results")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Duration", f"{summary.get('duration_s', 0):.1f} s")
            r2.metric("Fault Δ",  f"{summary.get('fault_delta', 'N/A'):,}" if summary.get('fault_delta') is not None else "N/A")
            r3.metric("Peak Working Set", format_mb(summary.get("peak_working_set_mb")))
            r4.metric("Allocation", f"{summary.get('alloc_mb', 0):.0f} MiB")

            st.markdown("**Page-Fault Interpretation:**")
            st.info(summary.get("interpretation", ""))

            if samples:
                _build_live_charts(samples, current_workload)

        # Errors
        for e in manager.runner.errors:
            st.warning(f"Worker message: {e}")
