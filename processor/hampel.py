"""Hampel outlier filter for CSI amplitude streams.

Pure numpy implementation (no scipy dependency). Replaces outliers
using running median ± scaled MAD per subcarrier (D-15).
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


def hampel_filter(
    data: np.ndarray, window_size: int = 7, threshold: float = 3.0
) -> np.ndarray:
    """Apply Hampel filter to a 1D amplitude time series.

    For each sample, computes the median and MAD (Median Absolute Deviation)
    within a sliding window. If the sample deviates from the median by more
    than ``threshold * MAD``, it is replaced with the median.

    Args:
        data: 1D array of amplitude values for a single subcarrier.
        window_size: Size of the sliding window. Must be odd; if even, 1 is
            added automatically.
        threshold: Number of MADs beyond which a sample is considered an
            outlier. Default 3.0.

    Returns:
        Cleaned 1D array with same length and dtype as input.
    """
    arr = np.asarray(data, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"data must be 1D, got shape {arr.shape}")

    n = len(arr)
    if n == 0:
        return arr.copy()

    # Validate input is finite (T-03-01)
    if not np.all(np.isfinite(arr)):
        raise ValueError("Input contains NaN or Inf — cannot apply Hampel filter")

    # Ensure odd window size
    if window_size % 2 == 0:
        window_size += 1

    half = window_size // 2
    cleaned = arr.copy()

    for i in range(n):
        # Define window around index i
        left = max(0, i - half)
        right = min(n, i + half + 1)
        window = arr[left:right]

        median = np.median(window)
        mad = np.median(np.abs(window - median))

        # MAD to standard deviation conversion factor
        sigma_est = 1.4826 * mad

        if sigma_est == 0:
            # MAD is zero: either all values identical, or one outlier among
            # identical values. Replace only if current value differs from median.
            if arr[i] != median:
                cleaned[i] = median
            continue

        if np.abs(arr[i] - median) > threshold * sigma_est:
            cleaned[i] = median

    return cleaned
