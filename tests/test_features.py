"""Unit tests for feature extraction."""

import math
import numpy as np
import pytest
from processor.features import extract_features, _band_power


class TestExtractFeatures:
    """Feature extraction tests."""

    def test_constant_window(self):
        """Constant amplitude → mean≈1.0, var≈0, energies≈0."""
        window = np.ones((200, 64))
        result = extract_features(window)

        assert "mean_amp" in result
        assert "var_amp" in result
        assert "motion_energy" in result
        assert "breathing_band" in result

        assert result["mean_amp"].shape == (64,)
        assert result["var_amp"].shape == (64,)
        np.testing.assert_allclose(result["mean_amp"], np.ones(64), atol=1e-10)
        np.testing.assert_allclose(result["var_amp"], np.zeros(64), atol=1e-10)
        assert result["motion_energy"] == pytest.approx(0.0, abs=1e-6)
        assert result["breathing_band"] == pytest.approx(0.0, abs=1e-6)

    def test_sine_1hz_motion_energy(self):
        """1 Hz sine wave → motion_energy > 0, breathing_band ≈ 0."""
        t = np.arange(200) / 50.0  # 200 samples @ 50 Hz = 4s
        signal = np.sin(2 * math.pi * 1.0 * t)  # 1 Hz
        window = np.column_stack([signal] * 64)
        result = extract_features(window, sample_rate=50.0)

        assert result["motion_energy"] > 0.1
        assert result["breathing_band"] == pytest.approx(0.0, abs=1e-3)

    def test_sine_0_2hz_breathing_band(self):
        """0.2 Hz sine wave → breathing_band > 0, motion_energy ≈ 0."""
        t = np.arange(200) / 50.0
        signal = np.sin(2 * math.pi * 0.2 * t)  # 0.2 Hz — well inside breathing band
        window = np.column_stack([signal] * 64)
        result = extract_features(window, sample_rate=50.0)

        assert result["breathing_band"] > 0.1
        # Allow small FFT leakage into motion band
        assert result["motion_energy"] < result["breathing_band"] * 0.5

    def test_output_shapes(self):
        """Verify output dict has correct keys and shapes."""
        window = np.random.randn(200, 64)
        result = extract_features(window)

        assert isinstance(result["mean_amp"], np.ndarray)
        assert isinstance(result["var_amp"], np.ndarray)
        assert result["mean_amp"].shape == (64,)
        assert result["var_amp"].shape == (64,)
        assert isinstance(result["motion_energy"], float)
        assert isinstance(result["breathing_band"], float)

    def test_feature_count(self):
        """Total scalar feature count = 64 + 64 + 1 + 1 = 130."""
        window = np.random.randn(200, 64)
        result = extract_features(window)
        count = len(result["mean_amp"]) + len(result["var_amp"]) + 1 + 1
        assert count == 130

    def test_with_phase_window(self):
        """Phase window adds phase_variance key."""
        amp_window = np.random.randn(200, 64)
        phase_window = np.random.randn(200, 64)
        result = extract_features(amp_window, phase_window=phase_window)

        assert "phase_variance" in result
        assert isinstance(result["phase_variance"], float)
        assert result["phase_variance"] >= 0.0

    def test_phase_window_shape_mismatch(self):
        """Phase window with wrong shape raises ValueError."""
        amp_window = np.random.randn(200, 64)
        phase_window = np.random.randn(200, 32)
        with pytest.raises(ValueError, match="phase_window shape"):
            extract_features(amp_window, phase_window=phase_window)

    def test_invalid_ndim(self):
        """1D input raises ValueError."""
        with pytest.raises(ValueError, match="amplitude_window must be 2D"):
            extract_features(np.zeros(64))

    def test_empty_window(self):
        """Empty window raises ValueError."""
        with pytest.raises(ValueError, match="amplitude_window is empty"):
            extract_features(np.zeros((0, 64)))


class TestBandPower:
    """Band power computation tests."""

    def test_band_power_constant_zero(self):
        """Zero signal has zero band power."""
        data = np.zeros((200, 64))
        freqs = np.fft.rfftfreq(200, d=1.0 / 50.0)
        power = _band_power(data, freqs, 0.5, 3.0)
        assert power == pytest.approx(0.0, abs=1e-10)

    def test_band_power_isolates_frequency(self):
        """1 Hz signal has power in 0.5-3 Hz band, not in 0.1-0.5 Hz."""
        t = np.arange(200) / 50.0
        signal = np.sin(2 * math.pi * 1.0 * t)
        data = np.column_stack([signal] * 64)
        freqs = np.fft.rfftfreq(200, d=1.0 / 50.0)

        motion_power = _band_power(data, freqs, 0.5, 3.0)
        breathing_power = _band_power(data, freqs, 0.1, 0.5)

        assert motion_power > 0.1
        assert breathing_power == pytest.approx(0.0, abs=1e-3)
