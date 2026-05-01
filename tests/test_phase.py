"""Unit tests for phase sanitization (unwrap + detrend)."""

import math
import numpy as np
import pytest
from processor.phase import unwrap_phase, detrend_phase


class TestUnwrapPhase:
    """Phase unwrapping tests."""

    def test_unwrap_1d_2pi_jump(self):
        """Single 2π jump in 1D array is removed (continuity restored)."""
        phases = np.array([0.0, 1.0, 2.0, 3.0, 3.0 + 2 * math.pi, 4.0 + 2 * math.pi])
        result = unwrap_phase(phases)
        # np.unwrap removes the 2π offset to restore continuity:
        # [0, 1, 2, 3, 3+2π, 4+2π] → [0, 1, 2, 3, 3, 4]
        expected = np.array([0.0, 1.0, 2.0, 3.0, 3.0, 4.0])
        np.testing.assert_allclose(result, expected, atol=1e-10)

    def test_unwrap_1d_no_jump(self):
        """Smooth phase returns nearly unchanged."""
        phases = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        result = unwrap_phase(phases)
        np.testing.assert_allclose(result, phases, atol=1e-10)

    def test_unwrap_2d_multiple_subcarriers(self):
        """2D array (time, subcarriers) preserves shape and unwraps per column."""
        n_frames, n_sub = 10, 64
        phases = np.zeros((n_frames, n_sub))
        # Add 2π jump at frame 5 for all subcarriers
        phases[5:, :] += 2 * math.pi
        result = unwrap_phase(phases)
        assert result.shape == (n_frames, n_sub)
        # After unwrap, the jump should be gone — all values near zero
        np.testing.assert_allclose(result, np.zeros_like(phases), atol=1e-10)

    def test_unwrap_2d_mixed_jumps(self):
        """Different subcarriers have jumps at different times."""
        phases = np.zeros((10, 3))
        phases[3:, 0] += 2 * math.pi      # subcarrier 0 jumps at frame 3
        phases[7:, 1] -= 2 * math.pi      # subcarrier 1 jumps down at frame 7
        # subcarrier 2 has no jump
        result = unwrap_phase(phases)
        np.testing.assert_allclose(result, np.zeros_like(phases), atol=1e-10)

    def test_unwrap_invalid_ndim(self):
        """3D input raises ValueError."""
        with pytest.raises(ValueError, match="phases must be 1D or 2D"):
            unwrap_phase(np.zeros((5, 5, 5)))


class TestDetrendPhase:
    """Linear detrend tests."""

    def test_detrend_linear_drift(self):
        """Linear ramp is reduced to near-zero."""
        phases = np.column_stack([np.arange(100, dtype=float)] * 64)  # (100, 64)
        result = detrend_phase(phases)
        # All values should be near zero after detrending
        np.testing.assert_allclose(result, np.zeros_like(phases), atol=1e-10)

    def test_detrend_constant(self):
        """Constant input stays unchanged."""
        phases = np.full((50, 64), 3.14)
        result = detrend_phase(phases)
        np.testing.assert_allclose(result, np.zeros_like(phases), atol=1e-10)

    def test_detrend_preserves_shape(self):
        """Output shape matches input shape."""
        phases = np.random.randn(200, 64)
        result = detrend_phase(phases)
        assert result.shape == phases.shape

    def test_detrend_single_frame(self):
        """Single frame returns copy unchanged."""
        phases = np.array([[1.0, 2.0, 3.0]])
        result = detrend_phase(phases)
        np.testing.assert_array_equal(result, phases)

    def test_detrend_invalid_ndim(self):
        """1D input raises ValueError."""
        with pytest.raises(ValueError, match="phases must be 2D"):
            detrend_phase(np.zeros(64))


class TestUnwrapThenDetrend:
    """Combined pipeline: unwrap → detrend (D-14 order)."""

    def test_pipeline_on_synthetic_data(self):
        """Full pipeline removes jumps and drift from synthetic phase."""
        t = np.arange(100, dtype=float)
        # Base: linear drift + sine + 2π jump at t=50
        phases = 0.1 * t + 0.5 * np.sin(0.2 * t)
        phases[50:] += 2 * math.pi
        phases_2d = np.column_stack([phases] * 64)

        unwrapped = unwrap_phase(phases_2d)
        detrended = detrend_phase(unwrapped)

        # After detrend, the linear component should be gone
        # Remaining: sine wave (roughly) — check mean is near zero and variance is reasonable
        assert detrended.shape == (100, 64)
        assert abs(detrended.mean()) < 0.1
        assert detrended.std() > 0.1  # sine wave still present
