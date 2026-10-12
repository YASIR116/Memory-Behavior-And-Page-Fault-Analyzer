"""
ui/dashboard.py
─────────────────────────────────────────────────────────────────────────────
Streamlit page: Windows Memory Dashboard
Shows real-time system memory statistics with auto-refresh.
"""

import time
import datetime
import streamlit as st
import plotly.graph_objects as go
from collectors.system_memory import collect_system_memory
from analysis.metrics import format_mb, mb_to_gb
from config import DEFAULT_MONITOR_INTERVAL_S


def _gauge(value: float, title: str, max_val: float = 100,
           suffix: str = "%", color: str = "#1f77b4") -> go.Figure:
    """Create a compact gauge chart."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": suffix, "font": {"size": 24}},
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, max_val]},
            "bar":  {"color": color},
            "steps": [
                {"range": [0,      max_val * 0.6], "color": "#d4f1d4"},
                {"range": [max_val * 0.6, max_val * 0.85], "color": "#fff3cd"},
                {"range": [max_val * 0.85, max_val],       "color": "#f8d7da"},
            ],
            "threshold": {"line": {"color": "red", "width": 3},
                          "thickness": 0.75, "value": max_val * 0.9},
        },
    ))
    fig.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=10))
    return fig


def render_dashboard():
    st.header("🖥️ Windows Memory Dashboard")
    st.caption("Real-time system memory statistics collected via Windows APIs.")

    # ── Controls ──────────────────────────────────────────────────────────
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 2])
    with col_ctrl1:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.session_state["dash_last_refresh"] = 0  # force refresh
    with col_ctrl2:
        auto = st.toggle("Auto-refresh", value=st.session_state.get("dash_auto", False),
                         key="dash_auto")
    with col_ctrl3:
        interval = st.slider("Refresh interval (s)", 1, 30,
                             st.session_state.get("dash_interval", DEFAULT_MONITOR_INTERVAL_S),
                             key="dash_interval")

    # ── Data fetch (cached per interval) ──────────────────────────────────
    now = time.monotonic()
    last = st.session_state.get("dash_last_refresh", 0)
    data = st.session_state.get("dash_data")

    if data is None or (now - last) >= interval:
        with st.spinner("Collecting system memory data…"):
            data = collect_system_memory()
        st.session_state["dash_data"]         = data
        st.session_state["dash_last_refresh"] = now

        # Keep a rolling history for the trend chart (max 120 points)
        hist: list = st.session_state.get("dash_history", [])
        hist.append(data)
        if len(hist) > 120:
            hist = hist[-120:]
        st.session_state["dash_history"] = hist

    ts_str = data.get("timestamp", "")
    st.caption(f"Last updated: {ts_str}")

    # ── Gauges row ────────────────────────────────────────────────────────
    st.subheader("System Overview")
    g1, g2, g3 = st.columns(3)

    mem_pct = data.get("memory_percent", 0) or 0
    cpu_pct = data.get("cpu_percent", 0)    or 0
    pf_pct  = data.get("pagefile_percent", 0) or 0

    with g1:
        st.plotly_chart(_gauge(mem_pct, "RAM Utilisation", color="#1f77b4"),
                        use_container_width=True, config={"displayModeBar": False})
    with g2:
        st.plotly_chart(_gauge(cpu_pct, "CPU Utilisation", color="#ff7f0e"),
                        use_container_width=True, config={"displayModeBar": False})
    with g3:
        st.plotly_chart(_gauge(pf_pct, "Pagefile Usage", color="#9467bd"),
                        use_container_width=True, config={"displayModeBar": False})

    # ── Key metrics ───────────────────────────────────────────────────────
    st.subheader("Physical Memory")
    m1, m2, m3, m4 = st.columns(4)

    total_mb = data.get("total_physical_mb")
    avail_mb = data.get("available_physical_mb")
    used_mb  = data.get("used_physical_mb")

    m1.metric("Total RAM",     format_mb(total_mb))
    m2.metric("Used RAM",      format_mb(used_mb),
              delta=f"{mem_pct:.1f}% utilised", delta_color="off")
    m3.metric("Available RAM", format_mb(avail_mb))
    m4.metric("RAM %",         f"{mem_pct:.1f}%")

    st.subheader("Virtual Memory & Pagefile")
    v1, v2, v3, v4 = st.columns(4)

    v1.metric("Pagefile Total",      format_mb(data.get("pagefile_total_mb")))
    v2.metric("Pagefile Used",       format_mb(data.get("pagefile_used_mb")))
    v3.metric("Virtual Addr Total",  format_mb(data.get("total_virtual_mb")))
    v4.metric("Virtual Addr Avail",  format_mb(data.get("available_virtual_mb")))

    st.subheader("Additional Windows Counters")
    e1, e2, e3, e4 = st.columns(4)

    e1.metric("System Cache",        format_mb(data.get("system_cache_mb")))
    e2.metric("Committed Memory",    format_mb(data.get("commit_total_mb")))
    e3.metric("Kernel Non-paged",    format_mb(data.get("kernel_nonpaged_mb")))
    e4.metric("Page Size",
              f"{data.get('page_size_bytes', 'N/A')} B"
              if data.get("page_size_bytes") else "N/A")

    st.subheader("CPU & Processes")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CPU Utilisation",  f"{cpu_pct:.1f}%")
    c2.metric("Logical CPUs",     str(data.get("cpu_count", "N/A")))
    c3.metric("Process Count",    str(data.get("process_count", "N/A")))
    c4.metric("Thread Count",     str(data.get("thread_count", "N/A")))

    # ── Trend chart ───────────────────────────────────────────────────────
    hist = st.session_state.get("dash_history", [])
    if len(hist) >= 2:
        st.subheader("Memory Trend")
        times      = [h.get("timestamp", "") for h in hist]
        mem_pcts   = [h.get("memory_percent", 0) or 0 for h in hist]
        avail_mbs  = [h.get("available_physical_mb", 0) or 0 for h in hist]
        cpu_pcts   = [h.get("cpu_percent", 0) or 0 for h in hist]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=times, y=mem_pcts,
                                 name="RAM %", line=dict(color="#1f77b4")))
        fig.add_trace(go.Scatter(x=times, y=cpu_pcts,
                                 name="CPU %", line=dict(color="#ff7f0e")))
        fig.update_layout(
            title="System Utilisation Over Time",
            xaxis_title="Timestamp (UTC)",
            yaxis_title="Utilisation (%)",
            yaxis=dict(range=[0, 100]),
            legend=dict(orientation="h"),
            height=300,
            margin=dict(l=40, r=20, t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=times, y=avail_mbs,
                                  fill="tozeroy", name="Available RAM (MiB)",
                                  line=dict(color="#2ca02c")))
        fig2.update_layout(
            title="Available Physical RAM Over Time",
            xaxis_title="Timestamp (UTC)",
            yaxis_title="MiB",
            height=250,
            margin=dict(l=40, r=20, t=40, b=40),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Auto-refresh ──────────────────────────────────────────────────────
    if auto:
        time.sleep(max(1, interval - 1))
        st.rerun()
