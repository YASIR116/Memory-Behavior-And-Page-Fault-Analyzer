"""
tests/test_comparison.py
─────────────────────────────────────────────────────────────────────────────
Tests for analysis/comparison.py
"""

import pytest
from analysis.comparison import compare_experiments, diff_summary


def _make_exp(exp_id: int, workload: str, alloc_mb: float,
              duration_s: float, fault_delta: int = None,
              peak_ws: float = None) -> dict:
    return {
        "id":                  exp_id,
        "workload":            workload,
        "alloc_mb":            alloc_mb,
        "duration_s":          duration_s,
        "interval_s":          1.0,
        "status":              "completed",
        "peak_working_set_mb": peak_ws or alloc_mb * 0.9,
        "final_working_set_mb": alloc_mb * 0.8,
        "pagefile_usage_mb":   alloc_mb,
        "available_ram_mb":    8000.0,
        "fault_delta":         fault_delta or alloc_mb * 10,
        "fault_rate":          None,
    }


EXP_A = _make_exp(1, "sequential", 64, 12, fault_delta=16384, peak_ws=62.0)
EXP_B = _make_exp(2, "random",     64, 12, fault_delta=16200, peak_ws=61.5)
EXP_C = _make_exp(3, "repeated",   64, 12, fault_delta=17000, peak_ws=63.0)


class TestCompareExperiments:
    def test_requires_two(self):
        with pytest.raises(ValueError, match="at least two"):
            compare_experiments([EXP_A])

    def test_returns_dict_structure(self):
        result = compare_experiments([EXP_A, EXP_B])
        assert "rows"     in result
        assert "charts"   in result
        assert "warnings" in result
        assert "n"        in result

    def test_n_equals_input_length(self):
        result = compare_experiments([EXP_A, EXP_B])
        assert result["n"] == 2

    def test_three_experiments(self):
        result = compare_experiments([EXP_A, EXP_B, EXP_C])
        assert result["n"] == 3

    def test_rows_have_correct_structure(self):
        result = compare_experiments([EXP_A, EXP_B])
        for row in result["rows"]:
            assert "field"  in row
            assert "label"  in row
            assert "values" in row
            assert len(row["values"]) == 2

    def test_no_warning_same_config(self):
        result = compare_experiments([EXP_A, EXP_B])
        # Both have same alloc_mb and duration_s → no compatibility warning
        assert result["warnings"] == []

    def test_warning_different_alloc(self):
        exp_x = _make_exp(4, "sequential", 128, 12)
        result = compare_experiments([EXP_A, exp_x])
        assert any("allocation" in w.lower() or "sizes" in w.lower()
                   for w in result["warnings"])

    def test_warning_different_duration(self):
        exp_y = _make_exp(5, "sequential", 64, 20)
        result = compare_experiments([EXP_A, exp_y])
        assert any("duration" in w.lower() for w in result["warnings"])

    def test_charts_have_values(self):
        result = compare_experiments([EXP_A, EXP_B])
        for chart in result["charts"]:
            assert len(chart["values"]) == 2
            assert len(chart["labels"]) == 2

    def test_fault_rate_computed(self):
        # fault_rate key is None in input but should be computed
        result = compare_experiments([EXP_A, EXP_B])
        row = next(r for r in result["rows"] if r["field"] == "fault_rate")
        # Should not be "N/A" for both since delta and duration are set
        assert row["values"][0] != "N/A"


class TestDiffSummary:
    def test_positive_diff(self):
        diff = diff_summary(EXP_A, EXP_C)
        assert diff["fault_delta"] == pytest.approx(17000 - 16384, rel=1e-3)

    def test_negative_diff(self):
        diff = diff_summary(EXP_C, EXP_A)
        assert diff["fault_delta"] == pytest.approx(16384 - 17000, rel=1e-3)

    def test_none_if_missing_key(self):
        exp_no_peak = {**EXP_A, "peak_working_set_mb": None}
        diff = diff_summary(exp_no_peak, EXP_B)
        assert diff["peak_working_set_mb"] is None

    def test_keys_present(self):
        diff = diff_summary(EXP_A, EXP_B)
        assert "alloc_mb"            in diff
        assert "duration_s"          in diff
        assert "peak_working_set_mb" in diff
        assert "fault_delta"         in diff
