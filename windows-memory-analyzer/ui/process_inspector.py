"""
ui/process_inspector.py
─────────────────────────────────────────────────────────────────────────────
Streamlit page: Process Memory Inspector
"""

import streamlit as st
import plotly.graph_objects as go
from collectors.process_memory import list_processes, collect_process_memory
from analysis.metrics import format_mb, COUNTER_DESCRIPTIONS


def render_process_inspector():
    st.header("🔍 Process Memory Inspector")
    st.caption(
        "Select a running Windows process to inspect its memory counters. "
        "Information is collected via psutil and GetProcessMemoryInfo."
    )

    # ── Refresh controls ──────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("🔎 Filter by name", placeholder="e.g. chrome, python")
    with col2:
        if st.button("🔄 Refresh Process List"):
            if "proc_list" in st.session_state:
                del st.session_state["proc_list"]
    with col3:
        auto_refresh = st.toggle("Auto-refresh", value=False, key="proc_auto")

    # ── Process list ──────────────────────────────────────────────────────
    if "proc_list" not in st.session_state:
        with st.spinner("Loading process list…"):
            st.session_state["proc_list"] = list_processes()

    procs = st.session_state["proc_list"]

    if search:
        procs = [p for p in procs if search.lower() in p["name"].lower()]

    if not procs:
        st.warning("No processes match the filter.")
        return

    # Build display labels
    labels = [f"{p['name']}  (PID {p['pid']})" for p in procs]
    chosen_label = st.selectbox("Select process", labels, key="proc_select")

    if not chosen_label:
        return

    # Find selected process
    chosen_idx = labels.index(chosen_label)
    pid = procs[chosen_idx]["pid"]

    # ── Detail fetch ──────────────────────────────────────────────────────
    if st.button("📊 Inspect Selected Process") or st.session_state.get("proc_inspect_pid") == pid:
        st.session_state["proc_inspect_pid"] = pid
        with st.spinner(f"Collecting data for PID {pid}…"):
            info = collect_process_memory(pid)

        if info.get("error"):
            st.error(f"Could not collect data: {info['error']}")
            return

        # ── Identity ──────────────────────────────────────────────────────
        st.subheader(f"📋 {info.get('name', 'Unknown')}  (PID {pid})")

        id1, id2, id3, id4 = st.columns(4)
        id1.metric("PID",    str(pid))
        id2.metric("PPID",   str(info.get("ppid", "N/A")))
        id3.metric("Threads", str(info.get("num_threads", "N/A")))
        id4.metric("Status",  str(info.get("status", "N/A")).capitalize())

        with st.expander("Executable path & creation time"):
            st.code(info.get("exe", "N/A"))
            st.write(f"**Created:** {info.get('create_time', 'N/A')}")

        # ── Memory metrics ────────────────────────────────────────────────
        st.subheader("Memory Counters")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Working Set",      format_mb(info.get("working_set_mb")),
                  help=COUNTER_DESCRIPTIONS["working_set_mb"]["note"])
        m2.metric("Peak Working Set", format_mb(info.get("peak_working_set_mb")),
                  help=COUNTER_DESCRIPTIONS["peak_working_set_mb"]["note"])
        m3.metric("Private Bytes",    format_mb(info.get("pagefile_usage_mb")),
                  help=COUNTER_DESCRIPTIONS["pagefile_usage_mb"]["note"])
        m4.metric("Virtual Size",     format_mb(info.get("vms_mb")))

        pf1, pf2 = st.columns(2)
        pf_count = info.get("page_fault_count")
        pf1.metric(
            "Page Fault Count (cumulative)",
            f"{pf_count:,}" if pf_count is not None else "N/A",
            help=COUNTER_DESCRIPTIONS["page_fault_count"]["note"],
        )
        pf2.metric("Memory %",
                   f"{info.get('memory_percent', 0):.2f}%" if info.get("memory_percent") else "N/A")

        p1, p2 = st.columns(2)
        p1.metric("Paged Pool",    format_mb(info.get("quota_paged_pool_mb")))
        p2.metric("Non-paged Pool", format_mb(info.get("quota_nonpaged_pool_mb")))

        # ── Memory bar chart ──────────────────────────────────────────────
        metrics_chart = {
            "Working Set": info.get("working_set_mb") or 0,
            "Peak Working Set": info.get("peak_working_set_mb") or 0,
            "Private Bytes": info.get("pagefile_usage_mb") or 0,
            "Virtual Size (VMS)": info.get("vms_mb") or 0,
        }
        fig = go.Figure(go.Bar(
            x=list(metrics_chart.keys()),
            y=list(metrics_chart.values()),
            marker_color=["#1f77b4", "#aec7e8", "#ff7f0e", "#ffbb78"],
            text=[format_mb(v) for v in metrics_chart.values()],
            textposition="auto",
        ))
        fig.update_layout(
            title=f"Memory Profile — {info.get('name')} (PID {pid})",
            xaxis_title="Counter",
            yaxis_title="MiB",
            height=350,
            margin=dict(l=40, r=20, t=50, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Counter explanations ──────────────────────────────────────────
        with st.expander("ℹ️ Counter Definitions"):
            for key in ["working_set_mb", "peak_working_set_mb",
                        "pagefile_usage_mb", "page_fault_count"]:
                cd = COUNTER_DESCRIPTIONS.get(key, {})
                st.markdown(f"**{cd.get('name', key)}**")
                st.caption(
                    f"Source: {cd.get('source', 'N/A')} · "
                    f"Units: {cd.get('units', 'N/A')} · "
                    f"Kind: {cd.get('kind', 'N/A')} · "
                    f"Scope: {cd.get('scope', 'N/A')}"
                )
                st.write(cd.get("note", ""))
                st.markdown("---")

        # ── Auto-refresh ──────────────────────────────────────────────────
        if auto_refresh:
            import time
            time.sleep(2)
            st.rerun()
