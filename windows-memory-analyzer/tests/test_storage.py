"""
tests/test_storage.py
─────────────────────────────────────────────────────────────────────────────
Tests for storage/database.py and storage/export.py
"""

import os
import tempfile
import pytest
from storage.database import ExperimentDB
from storage.export   import samples_to_csv, summaries_to_csv


@pytest.fixture
def db(tmp_path):
    """Create a fresh in-process ExperimentDB for each test."""
    path = str(tmp_path / "test.db")
    return ExperimentDB(path)


# ─── ExperimentDB ─────────────────────────────────────────────────────────────

class TestExperimentDB:
    def test_create_experiment(self, db):
        eid = db.create_experiment("sequential", 64.0, 10.0, 1.0)
        assert isinstance(eid, int)
        assert eid > 0

    def test_get_experiment(self, db):
        eid = db.create_experiment("random", 32.0, 8.0, 0.5, random_seed=42)
        exp = db.get_experiment(eid)
        assert exp is not None
        assert exp["workload"]    == "random"
        assert exp["alloc_mb"]    == 32.0
        assert exp["duration_s"]  == 8.0
        assert exp["interval_s"]  == 0.5
        assert exp["random_seed"] == 42
        assert exp["status"]      == "running"

    def test_list_experiments(self, db):
        db.create_experiment("allocation", 64.0, 10.0, 1.0)
        db.create_experiment("sequential", 64.0, 10.0, 1.0)
        exps = db.list_experiments()
        assert len(exps) == 2

    def test_update_status(self, db):
        eid = db.create_experiment("sequential", 64.0, 10.0, 1.0)
        db.update_experiment_status(eid, "completed")
        exp = db.get_experiment(eid)
        assert exp["status"] == "completed"

    def test_update_summary(self, db):
        eid = db.create_experiment("sequential", 64.0, 10.0, 1.0)
        summary = {
            "initial_page_faults":  1000,
            "final_page_faults":    2000,
            "fault_delta":          1000,
            "fault_rate":           100.0,
            "peak_working_set_mb":  60.0,
            "final_working_set_mb": 58.0,
            "pagefile_usage_mb":    62.0,
            "final_available_ram_mb": 8000.0,
            "interpretation":       "Test interpretation text.",
        }
        db.update_experiment_summary(eid, summary)
        exp = db.get_experiment(eid)
        assert exp["fault_delta"] == 1000
        assert exp["peak_working_set_mb"] == 60.0
        assert "interpretation" in str(exp.get("interpretation", ""))

    def test_delete_experiment(self, db):
        eid = db.create_experiment("release", 32.0, 6.0, 1.0)
        db.delete_experiment(eid)
        assert db.get_experiment(eid) is None

    def test_samples_cascade_delete(self, db):
        eid = db.create_experiment("sequential", 64.0, 10.0, 1.0)
        db.add_sample(eid, {"elapsed_s": 1.0, "page_fault_count": 100,
                             "working_set_mb": 50.0, "available_ram_mb": 8000.0})
        db.delete_experiment(eid)
        assert db.get_sample_count(eid) == 0

    def test_add_and_get_samples(self, db):
        eid = db.create_experiment("sequential", 64.0, 10.0, 1.0)
        for i in range(5):
            db.add_sample(eid, {
                "elapsed_s":       float(i),
                "page_fault_count": 1000 + i * 100,
                "working_set_mb":   50.0 + i,
                "available_ram_mb": 8000.0,
            })
        samples = db.get_samples(eid)
        assert len(samples) == 5
        assert samples[0]["elapsed_s"] == 0.0
        assert samples[4]["page_fault_count"] == 1400

    def test_sample_count(self, db):
        eid = db.create_experiment("repeated", 64.0, 10.0, 1.0)
        assert db.get_sample_count(eid) == 0
        db.add_sample(eid, {"elapsed_s": 1.0})
        assert db.get_sample_count(eid) == 1

    def test_multiple_experiments_isolated(self, db):
        eid1 = db.create_experiment("sequential", 64.0, 10.0, 1.0)
        eid2 = db.create_experiment("random",     32.0, 8.0,  0.5)
        db.add_sample(eid1, {"elapsed_s": 1.0, "page_fault_count": 500})
        db.add_sample(eid2, {"elapsed_s": 1.0, "page_fault_count": 300})
        assert db.get_sample_count(eid1) == 1
        assert db.get_sample_count(eid2) == 1

    def test_nonexistent_experiment(self, db):
        assert db.get_experiment(99999) is None


# ─── CSV Export ───────────────────────────────────────────────────────────────

class TestSamplesToCSV:
    def test_empty(self):
        assert samples_to_csv([]) == ""

    def test_header_present(self):
        samples = [{"elapsed_s": 1.0, "page_fault_count": 100}]
        csv = samples_to_csv(samples)
        assert "elapsed_s" in csv
        assert "page_fault_count" in csv

    def test_values_present(self):
        samples = [{"elapsed_s": 2.5, "page_fault_count": 999}]
        csv = samples_to_csv(samples)
        assert "2.5" in csv
        assert "999" in csv

    def test_multiple_rows(self):
        samples = [
            {"elapsed_s": 1.0, "page_fault_count": 100},
            {"elapsed_s": 2.0, "page_fault_count": 150},
        ]
        csv = samples_to_csv(samples)
        lines = [l for l in csv.split("\n") if l.strip()]
        assert len(lines) == 3  # header + 2 rows

    def test_missing_field_empty_string(self):
        samples = [{"elapsed_s": 1.0}]
        csv = samples_to_csv(samples)
        # page_fault_count column should exist but value should be empty
        assert "page_fault_count" in csv

    def test_extra_fields_included(self):
        samples = [{"elapsed_s": 1.0, "custom_field": "hello"}]
        csv = samples_to_csv(samples)
        assert "custom_field" in csv
        assert "hello" in csv


class TestSummariesToCSV:
    def test_empty(self):
        assert summaries_to_csv([]) == ""

    def test_header_present(self):
        exps = [{"id": 1, "workload": "sequential", "alloc_mb": 64, "status": "completed"}]
        csv = summaries_to_csv(exps)
        assert "workload" in csv
        assert "alloc_mb" in csv

    def test_multiple_rows(self):
        exps = [
            {"id": 1, "workload": "sequential"},
            {"id": 2, "workload": "random"},
        ]
        csv = summaries_to_csv(exps)
        lines = [l for l in csv.split("\n") if l.strip()]
        assert len(lines) == 3

    def test_interpretation_excluded(self):
        """The long interpretation text should not appear in the summary CSV."""
        exps = [{"id": 1, "workload": "sequential",
                 "interpretation": "This is a long text explanation."}]
        csv = summaries_to_csv(exps)
        # interpretation is excluded from ordered_keys and from "all_keys"
        assert "This is a long text" not in csv
