"""
tests/test_workloads.py
─────────────────────────────────────────────────────────────────────────────
Tests for workload configuration validation and runner logic.
"""

import pytest
from experiments.workload_runner import validate_config
from config import MAX_ALLOC_MB


class TestValidateConfig:
    def _good_cfg(self, **overrides):
        cfg = {
            "workload":   "sequential",
            "alloc_mb":   64,
            "duration_s": 10,
            "interval_s": 1.0,
        }
        cfg.update(overrides)
        return cfg

    def test_valid_config(self):
        assert validate_config(self._good_cfg()) is None

    def test_valid_allocation(self):
        assert validate_config(self._good_cfg(workload="allocation")) is None

    def test_valid_repeated(self):
        assert validate_config(self._good_cfg(workload="repeated")) is None

    def test_valid_random(self):
        assert validate_config(self._good_cfg(workload="random")) is None

    def test_valid_release(self):
        assert validate_config(self._good_cfg(workload="release")) is None

    def test_alloc_zero(self):
        err = validate_config(self._good_cfg(alloc_mb=0))
        assert err is not None
        assert "0" in err or "greater" in err.lower()

    def test_alloc_negative(self):
        err = validate_config(self._good_cfg(alloc_mb=-10))
        assert err is not None

    def test_alloc_exceeds_max(self):
        err = validate_config(self._good_cfg(alloc_mb=MAX_ALLOC_MB + 1))
        assert err is not None
        assert str(MAX_ALLOC_MB) in err

    def test_duration_too_short(self):
        err = validate_config(self._good_cfg(duration_s=1))
        assert err is not None

    def test_duration_too_long(self):
        err = validate_config(self._good_cfg(duration_s=400))
        assert err is not None

    def test_interval_too_small(self):
        err = validate_config(self._good_cfg(interval_s=0.05))
        assert err is not None

    def test_interval_too_large(self):
        err = validate_config(self._good_cfg(interval_s=120))
        assert err is not None

    def test_unknown_workload(self):
        err = validate_config(self._good_cfg(workload="unknown_type"))
        assert err is not None

    def test_non_numeric_alloc(self):
        err = validate_config(self._good_cfg(alloc_mb="not_a_number"))
        assert err is not None

    def test_boundary_alloc_max(self):
        """Exactly MAX_ALLOC_MB should be valid."""
        assert validate_config(self._good_cfg(alloc_mb=MAX_ALLOC_MB)) is None

    def test_boundary_duration_min(self):
        assert validate_config(self._good_cfg(duration_s=3)) is None

    def test_boundary_interval_min(self):
        assert validate_config(self._good_cfg(interval_s=0.1)) is None
