"""
app.py
─────────────────────────────────────────────────────────────────────────────
Windows Memory Behavior and Page-Fault Analyzer
Entry point for Streamlit application.

Launch:
    streamlit run app.py
"""

import multiprocessing
import streamlit as st

# Must be the first Streamlit call
st.set_page_config(
    page_title="Windows Memory Analyzer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.dashboard         import render_dashboard
from ui.process_inspector import render_process_inspector
from ui.experiments_page  import render_experiments
from ui.results_page      import render_results
from ui.comparison_page   import render_comparison
from ui.history_page      import render_history
from ui.about_page        import render_about
from config               import APP_TITLE, APP_VERSION


# ─── Sidebar navigation ────────────────────────────────────────────────────────

PAGES = {
    "🖥️ Dashboard":             render_dashboard,
    "🔍 Process Inspector":     render_process_inspector,
    "🧪 Memory Experiments":    render_experiments,
    "📉 Page-Fault Analysis":   render_results,
    "⚖️ Experiment Comparison": render_comparison,
    "📚 Experiment History":    render_history,
    "ℹ️ About & Metrics":       render_about,
}

with st.sidebar:
    st.title("🧠 Memory Analyzer")
    st.caption(f"v{APP_VERSION} · Windows 10/11")
    st.markdown("---")
    selected = st.radio(
        "Navigate",
        list(PAGES.keys()),
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("Mini-project · Windows & Linux Internals")

# ─── Render selected page ──────────────────────────────────────────────────────

PAGES[selected]()


# ─── Windows multiprocessing guard ────────────────────────────────────────────
# Required on Windows to prevent infinite subprocess spawning when using
# multiprocessing with the 'spawn' start method (the Windows default).
if __name__ == "__main__":
    multiprocessing.freeze_support()
