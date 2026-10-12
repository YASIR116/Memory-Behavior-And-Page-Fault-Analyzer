"""
experiments/experiment_manager.py
─────────────────────────────────────────────────────────────────────────────
High-level facade that ties together:
  • WorkloadRunner (subprocess + queue)
  • Storage (SQLite persistence)
  • Page-fault interpretation

The Streamlit UI interacts primarily with this class.
"""

import datetime
from typing import Dict, Any, List, Optional

from experiments.workload_runner import WorkloadRunner, validate_config
from collectors.page_faults import interpret_page_fault_delta
from storage.database import ExperimentDB
from config import DB_PATH


class ExperimentManager:
    """
    Manages the full lifecycle of memory experiments.

    One instance should live in st.session_state across Streamlit reruns.
    """

    def __init__(self, db_path: str = DB_PATH):
        self._runner = WorkloadRunner()
        self._db     = ExperimentDB(db_path)
        self._current_exp_id: Optional[int] = None
        self._current_cfg:    Optional[Dict[str, Any]] = None

    # ── experiment lifecycle ────────────────────────────────────────────────

    def start_experiment(self, workload: str, cfg: Dict[str, Any]) -> int:
        """
        Validate, persist metadata, and start the workload.
        Returns the experiment_id in the database.
        """
        err = validate_config({**cfg, "workload": workload})
        if err:
            raise ValueError(err)

        exp_id = self._db.create_experiment(
            workload=workload,
            alloc_mb=cfg["alloc_mb"],
            duration_s=cfg["duration_s"],
            interval_s=cfg["interval_s"],
            random_seed=cfg.get("random_seed"),
            status="running",
        )
        self._current_exp_id = exp_id
        self._current_cfg    = {**cfg, "workload": workload}
        self._runner.start(workload=workload, cfg=cfg)
        return exp_id

    def stop_experiment(self) -> None:
        """Cancel the running experiment and mark it as cancelled in DB."""
        self._runner.stop()
        if self._current_exp_id:
            self._db.update_experiment_status(self._current_exp_id, "cancelled")

    def collect_and_save(self) -> List[Dict[str, Any]]:
        """
        Flush new samples from the runner to the database.
        Returns the list of new samples collected since the last call.
        """
        if not self._current_exp_id:
            return []
        all_samples = self._runner.samples
        # Only store samples not yet persisted (track count)
        stored = self._db.get_sample_count(self._current_exp_id)
        new_samples = all_samples[stored:]
        for s in new_samples:
            self._db.add_sample(self._current_exp_id, s)
        return new_samples

    def finalise(self) -> Optional[Dict[str, Any]]:
        """
        Called when the runner reports done.
        Persists the summary and marks the experiment complete.
        Returns the summary dict with interpretation added.
        """
        if not self._current_exp_id:
            return None

        # Flush remaining samples
        self.collect_and_save()

        summary = self._runner.summary
        if summary is None:
            self._db.update_experiment_status(self._current_exp_id, "failed")
            return None

        workload = self._current_cfg.get("workload", "") if self._current_cfg else ""
        delta    = summary.get("fault_delta")
        summary["interpretation"] = interpret_page_fault_delta(delta, workload)

        self._db.update_experiment_summary(self._current_exp_id, summary)
        self._db.update_experiment_status(self._current_exp_id, "completed")
        return summary

    @property
    def is_running(self) -> bool:
        return self._runner.is_running

    @property
    def runner(self) -> WorkloadRunner:
        return self._runner

    @property
    def current_exp_id(self) -> Optional[int]:
        return self._current_exp_id

    # ── history queries ─────────────────────────────────────────────────────

    def list_experiments(self) -> List[Dict[str, Any]]:
        return self._db.list_experiments()

    def get_experiment(self, exp_id: int) -> Optional[Dict[str, Any]]:
        return self._db.get_experiment(exp_id)

    def get_samples(self, exp_id: int) -> List[Dict[str, Any]]:
        return self._db.get_samples(exp_id)

    def delete_experiment(self, exp_id: int) -> None:
        self._db.delete_experiment(exp_id)

    def get_db(self) -> ExperimentDB:
        return self._db
