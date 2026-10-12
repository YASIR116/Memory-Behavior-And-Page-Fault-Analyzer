"""
ui/history_page.py
─────────────────────────────────────────────────────────────────────────────
Streamlit page: Experiment History and CSV Export
"""

import streamlit as st
import pandas as pd

from experiments.experiment_manager import ExperimentManager
from storage.export import samples_to_csv, summaries_to_csv
from config import WORKLOAD_LABELS
from analysis.metrics import format_mb, counter_rate


def _get_manager() -> ExperimentManager:
    if "exp_manager" not in st.session_state:
        st.session_state["exp_manager"] = ExperimentManager()
    return st.session_state["exp_manager"]


def render_history():
    st.header("📚 Experiment History")

    manager = _get_manager()
    exps    = manager.list_experiments()

    if not exps:
        st.info("No experiments recorded yet.")
        return

    # ── Summary table ─────────────────────────────────────────────────────
    rows = []
    for e in exps:
        fault_rate = counter_rate(e.get("fault_delta"), e.get("duration_s"))
        rows.append({
            "ID":         e["id"],
            "Date":       (e.get("created_at") or "")[:19].replace("T", " "),
            "Workload":   WORKLOAD_LABELS.get(e.get("workload", ""), e.get("workload", "")),
            "Alloc (MiB)": e.get("alloc_mb"),
            "Duration (s)": e.get("duration_s"),
            "Status":     e.get("status", ""),
            "Fault Δ":    e.get("fault_delta"),
            "Fault /s":   fault_rate,
            "Peak WS":    format_mb(e.get("peak_working_set_mb")),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Export all summaries ──────────────────────────────────────────────
    st.subheader("Export")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        csv_all = summaries_to_csv(exps)
        st.download_button(
            "⬇️ Export All Summaries (CSV)",
            data=csv_all.encode("utf-8"),
            file_name="experiment_summaries.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_exp2:
        # Export all samples for all experiments
        all_samples = []
        for e in exps:
            ss = manager.get_samples(e["id"])
            all_samples.extend(ss)
        csv_samples = samples_to_csv(all_samples)
        st.download_button(
            "⬇️ Export All Samples (CSV)",
            data=csv_samples.encode("utf-8"),
            file_name="experiment_samples.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("Individual Experiment Actions")

    # ── Per-experiment actions ─────────────────────────────────────────────
    selected_id = st.selectbox(
        "Select experiment",
        options=[e["id"] for e in exps],
        format_func=lambda eid: (
            f"#{eid} — {WORKLOAD_LABELS.get(next((e['workload'] for e in exps if e['id'] == eid), ''), '')} "
            f"({next((e.get('created_at','')[:10] for e in exps if e['id'] == eid), '')})"
        ),
    )

    if selected_id:
        exp = manager.get_experiment(selected_id)
        samples = manager.get_samples(selected_id)

        if exp:
            with st.expander(f"Summary for Experiment #{selected_id}", expanded=True):
                keys = [
                    "id", "created_at", "workload", "alloc_mb", "duration_s",
                    "interval_s", "status", "initial_page_faults",
                    "final_page_faults", "fault_delta",
                    "peak_working_set_mb", "final_working_set_mb",
                    "available_ram_mb", "interpretation",
                ]
                for k in keys:
                    v = exp.get(k)
                    if v is not None:
                        st.write(f"**{k}:** {v}")

            col_dl1, col_dl2, col_dl3 = st.columns(3)

            with col_dl1:
                if samples:
                    csv_s = samples_to_csv(samples)
                    st.download_button(
                        "⬇️ Samples CSV",
                        data=csv_s.encode("utf-8"),
                        file_name=f"exp_{selected_id}_samples.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                else:
                    st.write("No samples stored.")

            with col_dl2:
                csv_e = summaries_to_csv([exp])
                st.download_button(
                    "⬇️ Summary CSV",
                    data=csv_e.encode("utf-8"),
                    file_name=f"exp_{selected_id}_summary.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with col_dl3:
                if st.button("🗑️ Delete Experiment", type="secondary",
                             use_container_width=True):
                    st.session_state["delete_confirm"] = selected_id

    # ── Delete confirmation ───────────────────────────────────────────────
    confirm_id = st.session_state.get("delete_confirm")
    if confirm_id:
        st.warning(f"Are you sure you want to delete experiment #{confirm_id}?")
        yes, no = st.columns(2)
        with yes:
            if st.button("✅ Yes, delete", type="primary", use_container_width=True):
                manager.delete_experiment(confirm_id)
                del st.session_state["delete_confirm"]
                st.success(f"Experiment #{confirm_id} deleted.")
                st.rerun()
        with no:
            if st.button("❌ Cancel", use_container_width=True):
                del st.session_state["delete_confirm"]
                st.rerun()
