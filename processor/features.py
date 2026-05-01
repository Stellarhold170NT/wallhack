"""Feature extraction from windowed CSI amplitude data.

Computes per-window feature vectors: mean/variance per subcarrier,
motion energy (0.5-3 Hz band power), and breathing band (0.1-0.5 Hz).
"""

import numpy as np


def extract_features(
    amplitude_window: np.ndarray,
    phase_window: np.ndarray | None = None,
    sample_rate: float = 50.0,
) -> dict[str, np.ndarray | float]:
    """Extract feature vector from a CSI amplitude window.

    Args:
        amplitude_window: Shape ``(window_size, n_subcarriers)``.
        phase_window: Optional unwrapped/detrended phases of same shape.
        sample_rate: Sampling frequency in Hz (default 50.0).

    Returns:
        Dict with keys:
        - ``mean_amp``: shape ``(n_subcarriers,)``
        - ``var_amp``: shape ``(n_subcarriers,)``
        - ``motion_energy``: scalar float
        - ``breathing_band``: scalar float
        - ``phase_variance``: scalar float (only if phase_window provided)
    """
    arr = np.asarray(amplitude_window, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError(
            f"amplitude_window must be 2D, got shape {arr.shape}"
        )

    n_frames, n_subcarriers = arr.shape
    if n_frames == 0:
        raise ValueError("amplitude_window is empty")

    # Per-subcarrier statistics
    mean_amp = arr.mean(axis=0)
    var_amp = arr.var(axis=0)

    # Band power via FFT
    freqs = np.fft.rfftfreq(n_frames, d=1.0 / sample_rate)
    motion_energy = _band_power(arr, freqs, 0.5, 3.0)
    breathing_band = _band_power(arr, freqs, 0.1, 0.5)

    result: dict[str, np.ndarray | float] = {
        "mean_amp": mean_amp,
        "var_amp": var_amp,
        "motion_energy": motion_energy,
        "breathing_band": breathing_band,
    }

    if phase_window is not None:
        ph = np.asarray(phase_window, dtype=np.float64)
        if ph.shape != arr.shape:
            raise ValueError(
                f"phase_window shape {ph.shape} != amplitude_window shape {arr.shape}"
            )
        result["phase_variance"] = float(ph.var(axis=0).mean())

    return result


def _band_power(
    data: np.ndarray, freqs: np.ndarray, f_low: float, f_high: float
) -> float:
    """Compute average band power across all subcarriers.

    Args:
        data: Amplitude window of shape ``(n_frames, n_subcarriers)``.
        freqs: FFT frequency bins from ``np.fft.rfftfreq``.
        f_low: Lower frequency bound in Hz.
        f_high: Upper frequency bound in Hz.

    Returns:
        Mean power (sum of squared magnitudes) across all subcarriers.
    """
    # FFT per subcarrier (axis=0 = time)
    fft = np.fft.rfft(data, axis=0)
    power = np.abs(fft) ** 2

    # Select frequency bins in [f_low, f_high]
    mask = (freqs >= f_low) & (freqs <= f_high)
    if not np.any(mask):
        return 0.0

    # Sum power in band per subcarrier, then average across subcarriers
    band_power_per_subcarrier = power[mask, :].sum(axis=0)
    return float(band_power_per_subcarrier.mean())
