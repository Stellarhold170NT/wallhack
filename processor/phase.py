"""CSI phase sanitization: unwrap and detrend.

Applies numpy.unwrap along the time axis to remove 2π discontinuities,
followed by linear detrend per subcarrier to remove slow drift.

Usage order: unwrap_phase → detrend_phase (D-14).
"""

import numpy as np


def unwrap_phase(phases: np.ndarray) -> np.ndarray:
    """Remove 2π jumps from CSI phase data.

    Uses np.unwrap along axis=0 (time). Handles both 1D (single subcarrier)
    and 2D (multiple subcarriers × time) inputs.

    Args:
        phases: Phase array. Shape ``(n_frames, n_subcarriers)`` or
            ``(n_subcarriers,)``.

    Returns:
        Unwrapped phase array with same shape as input.
    """
    arr = np.asarray(phases, dtype=np.float64)
    if arr.ndim == 1:
        return np.unwrap(arr)
    if arr.ndim == 2:
        return np.unwrap(arr, axis=0)
    raise ValueError(f"phases must be 1D or 2D, got shape {arr.shape}")


def detrend_phase(phases: np.ndarray) -> np.ndarray:
    """Remove linear trend from unwrapped phase per subcarrier.

    Fits a least-squares line to each subcarrier's time series and
    subtracts it, leaving the residual (detrended) signal.

    Args:
        phases: Unwrapped phase array. Shape ``(n_frames, n_subcarriers)``.

    Returns:
        Detrended phase array with same shape as input.
    """
    arr = np.asarray(phases, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError(f"phases must be 2D (time, subcarriers), got shape {arr.shape}")

    n_frames, n_subcarriers = arr.shape
    if n_frames < 2:
        return arr.copy()

    # Time indices: 0, 1, 2, ..., n_frames-1
    t = np.arange(n_frames, dtype=np.float64)
    t_mean = t.mean()
    t_var = ((t - t_mean) ** 2).sum()

    if t_var == 0:
        return arr.copy()

    # Compute slope and intercept for each subcarrier (column)
    # slope = Cov(t, y) / Var(t)
    slopes = ((t - t_mean)[:, None] * (arr - arr.mean(axis=0))).sum(axis=0) / t_var
    intercepts = arr.mean(axis=0) - slopes * t_mean

    trend = t[:, None] * slopes + intercepts
    return arr - trend
