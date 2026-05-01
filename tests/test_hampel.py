"""Unit tests for Hampel outlier filter."""

import numpy as np
import pytest
from processor.hampel import hampel_filter


class TestHampelFilter:
    """Hampel filter core tests."""

    def test_spike_replacement(self):
        """Single spike is replaced with median."""
        data = np.ones(100)
        data[50] = 100.0  # spike
        result = hampel_filter(data, window_size=7, threshold=3.0)
        # Spike should be replaced with ~1.0
        assert result[50] == pytest.approx(1.0, abs=0.1)
        # Reduction should be >80%
        reduction = (100.0 - result[50]) / 100.0
        assert reduction > 0.8

    def test_no_false_positives_on_clean_noise(self):
        """Clean Gaussian noise has <5% replacements."""
        np.random.seed(42)
        data = np.random.normal(loc=1.0, scale=0.1, size=1000)
        result = hampel_filter(data, window_size=7, threshold=3.0)
        replacements = np.sum(result != data)
        rate = replacements / len(data)
        assert rate < 0.05

    def test_multiple_spikes(self):
        """Multiple spikes are all replaced."""
        data = np.ones(100)
        data[20] = 50.0
        data[50] = -40.0
        data[80] = 60.0
        result = hampel_filter(data, window_size=7, threshold=3.0)
        assert result[20] == pytest.approx(1.0, abs=0.1)
        assert result[50] == pytest.approx(1.0, abs=0.1)
        assert result[80] == pytest.approx(1.0, abs=0.1)

    def test_constant_array_no_change(self):
        """All-constant array returns unchanged."""
        data = np.full(50, 5.0)
        result = hampel_filter(data, window_size=7, threshold=3.0)
        np.testing.assert_array_equal(result, data)

    def test_window_size_even_gets_bumped(self):
        """Even window_size is automatically made odd."""
        data = np.ones(50)
        data[25] = 100.0
        # window_size=6 should behave like 7
        result = hampel_filter(data, window_size=6, threshold=3.0)
        assert result[25] == pytest.approx(1.0, abs=0.1)

    def test_single_element(self):
        """Single-element array returns copy."""
        data = np.array([42.0])
        result = hampel_filter(data, window_size=7, threshold=3.0)
        assert result[0] == 42.0

    def test_empty_array(self):
        """Empty array returns empty copy."""
        data = np.array([], dtype=float)
        result = hampel_filter(data, window_size=7, threshold=3.0)
        assert len(result) == 0

    def test_2d_input_raises(self):
        """2D input raises ValueError."""
        with pytest.raises(ValueError, match="data must be 1D"):
            hampel_filter(np.zeros((10, 10)))

    def test_nan_input_raises(self):
        """NaN input raises ValueError (T-03-01)."""
        data = np.array([1.0, np.nan, 3.0])
        with pytest.raises(ValueError, match="NaN or Inf"):
            hampel_filter(data)

    def test_inf_input_raises(self):
        """Inf input raises ValueError (T-03-01)."""
        data = np.array([1.0, np.inf, 3.0])
        with pytest.raises(ValueError, match="NaN or Inf"):
            hampel_filter(data)

    def test_low_threshold_catches_more(self):
        """Lower threshold catches more outliers."""
        np.random.seed(42)
        data = np.random.normal(loc=0.0, scale=1.0, size=500)
        data[250] = 5.0  # 5-sigma outlier — caught at 1.5, passes at 6.0
        result_strict = hampel_filter(data, window_size=7, threshold=1.5)
        result_loose = hampel_filter(data, window_size=7, threshold=6.0)
        # Strict threshold should replace the outlier; loose may not
        assert result_strict[250] != pytest.approx(5.0, abs=0.1)
        # Loose threshold should keep it (or replace with similar value)
        assert result_loose[250] == pytest.approx(5.0, abs=0.1)
