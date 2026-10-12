"""
tests/test_metrics.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for analysis/metrics.py
"""

import pytest
from analysis.metrics import (
    bytes_to_mb, bytes_to_gb, mb_to_gb, format_bytes, format_mb,
    counter_delta, counter_rate, percentage,
    extract_series, peak_value, min_value, fault_deltas_from_samples,
)


# ─── bytes_to_mb ──────────────────────────────────────────────────────────────

class TestBytesToMb:
    def test_zero(self):
        assert bytes_to_mb(0) == 0.0

    def test_one_mib(self):
        assert bytes_to_mb(1024 * 1024) == 1.0

    def test_one_gib(self):
        assert bytes_to_mb(1024 * 1024 * 1024) == 1024.0

    def test_none(self):
        assert bytes_to_mb(None) is None

    def test_fractional(self):
        result = bytes_to_mb(512 * 1024)
        assert result == 0.5


class TestBytesToGb:
    def test_one_gib(self):
        assert bytes_to_gb(1024 ** 3) == 1.0

    def test_none(self):
        assert bytes_to_gb(None) is None


class TestMbToGb:
    def test_1024_mb(self):
        assert mb_to_gb(1024.0) == pytest.approx(1.0, rel=1e-3)

    def test_none(self):
        assert mb_to_gb(None) is None


class TestFormatBytes:
    def test_bytes(self):
        assert "512 B" in format_bytes(512)

    def test_kib(self):
        assert "KiB" in format_bytes(2048)

    def test_mib(self):
        assert "MiB" in format_bytes(5 * 1024 * 1024)

    def test_gib(self):
        assert "GiB" in format_bytes(2 * 1024 ** 3)

    def test_none(self):
        assert format_bytes(None) == "N/A"


class TestFormatMb:
    def test_small(self):
        result = format_mb(512.0)
        assert "MiB" in result

    def test_large(self):
        result = format_mb(2048.0)
        assert "GiB" in result

    def test_none(self):
        assert format_mb(None) == "N/A"


# ─── counter_delta ─────────────────────────────────────────────────────────────

class TestCounterDelta:
    def test_simple(self):
        assert counter_delta(100, 200) == 100

    def test_zero_delta(self):
        assert counter_delta(500, 500) == 0

    def test_none_initial(self):
        assert counter_delta(None, 200) is None

    def test_none_final(self):
        assert counter_delta(100, None) is None

    def test_both_none(self):
        assert counter_delta(None, None) is None

    def test_wraparound_32bit(self):
        # Simulates a DWORD wrapping at 2^32
        initial = 2 ** 32 - 10
        final   = 5
        assert counter_delta(initial, final, bits=32) == 15

    def test_large_values(self):
        assert counter_delta(1_000_000, 1_005_000) == 5000


# ─── counter_rate ──────────────────────────────────────────────────────────────

class TestCounterRate:
    def test_simple(self):
        assert counter_rate(100, 10.0) == 10.0

    def test_none_delta(self):
        assert counter_rate(None, 10.0) is None

    def test_none_duration(self):
        assert counter_rate(100, None) is None

    def test_zero_duration(self):
        assert counter_rate(100, 0) is None

    def test_fractional(self):
        assert counter_rate(50, 3.0) == pytest.approx(16.67, rel=1e-2)


# ─── percentage ───────────────────────────────────────────────────────────────

class TestPercentage:
    def test_half(self):
        assert percentage(50.0, 100.0) == 50.0

    def test_zero_total(self):
        assert percentage(10.0, 0.0) is None

    def test_none_part(self):
        assert percentage(None, 100.0) is None

    def test_none_total(self):
        assert percentage(10.0, None) is None

    def test_over_100(self):
        # Working-set can briefly exceed total in edge cases — we don't clamp
        result = percentage(110.0, 100.0)
        assert result == pytest.approx(110.0, rel=1e-3)


# ─── series helpers ────────────────────────────────────────────────────────────

SAMPLE_LIST = [
    {"elapsed_s": 0.0, "working_set_mb": 10.0, "page_fault_count": 1000},
    {"elapsed_s": 1.0, "working_set_mb": 20.0, "page_fault_count": 1200},
    {"elapsed_s": 2.0, "working_set_mb": None,  "page_fault_count": 1250},
    {"elapsed_s": 3.0, "working_set_mb": 30.0, "page_fault_count": 1300},
]


class TestExtractSeries:
    def test_existing_key(self):
        result = extract_series(SAMPLE_LIST, "working_set_mb")
        assert result == [10.0, 20.0, None, 30.0]

    def test_missing_key(self):
        result = extract_series(SAMPLE_LIST, "nonexistent")
        assert all(v is None for v in result)


class TestPeakValue:
    def test_normal(self):
        assert peak_value([10.0, 20.0, None, 30.0]) == 30.0

    def test_all_none(self):
        assert peak_value([None, None]) is None

    def test_empty(self):
        assert peak_value([]) is None


class TestMinValue:
    def test_normal(self):
        assert min_value([10.0, 20.0, None, 30.0]) == 10.0

    def test_all_none(self):
        assert min_value([None]) is None


# ─── fault_deltas_from_samples ────────────────────────────────────────────────

class TestFaultDeltas:
    def test_basic(self):
        deltas = fault_deltas_from_samples(SAMPLE_LIST)
        assert deltas[0] is None          # first sample, no prior
        assert deltas[1] == 200           # 1200 - 1000
        assert deltas[2] == 50            # 1250 - 1200
        assert deltas[3] == 50            # 1300 - 1250

    def test_empty(self):
        assert fault_deltas_from_samples([]) == []

    def test_single_sample(self):
        result = fault_deltas_from_samples([{"page_fault_count": 100}])
        assert result == [None]

    def test_none_fault_count(self):
        samples = [
            {"page_fault_count": None},
            {"page_fault_count": None},
        ]
        deltas = fault_deltas_from_samples(samples)
        assert deltas[0] is None
        assert deltas[1] is None
