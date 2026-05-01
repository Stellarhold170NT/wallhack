"""Sliding window buffer for CSI frame streams.

Maintains a circular buffer of amplitude values per node, emitting
a fixed-size window matrix when enough frames have accumulated (D-17).
"""

import logging
import numpy as np
from aggregator.frame import CSIFrame

logger = logging.getLogger(__name__)


class SlidingWindow:
    """Fixed-size sliding window for CSI amplitude frames.

    Emits a ``(window_size, n_subcarriers)`` numpy array every
    ``step_size`` frames once the buffer is full.
    """

    def __init__(
        self,
        n_subcarriers: int = 64,
        window_size: int = 200,
        step_size: int = 100,
    ) -> None:
        self._n_subcarriers = n_subcarriers
        self._window_size = window_size
        self._step_size = step_size
        self._buffer: np.ndarray = np.zeros((window_size, n_subcarriers), dtype=np.float64)
        self._count = 0
        self._emit_counter = 0

    @property
    def n_subcarriers(self) -> int:
        return self._n_subcarriers

    @property
    def window_size(self) -> int:
        return self._window_size

    @property
    def step_size(self) -> int:
        return self._step_size

    def push(self, frame: CSIFrame) -> np.ndarray | None:
        """Append a frame and return a window if ready.

        Args:
            frame: Parsed CSI frame with amplitude array.

        Returns:
            Window array of shape ``(window_size, n_subcarriers)``
            if enough frames have accumulated, else ``None``.
        """
        amplitudes = np.asarray(frame.amplitudes, dtype=np.float64)
        if len(amplitudes) != self._n_subcarriers:
            logger.warning(
                "Frame amplitude length %d != expected %d — skipping",
                len(amplitudes),
                self._n_subcarriers,
            )
            return None

        # Circular buffer: roll left and append at end
        self._buffer = np.roll(self._buffer, -1, axis=0)
        self._buffer[-1, :] = amplitudes
        self._count += 1
        self._emit_counter += 1

        if self._count >= self._window_size and self._emit_counter >= self._step_size:
            self._emit_counter = 0
            return self._buffer.copy()
        return None

    def is_full(self) -> bool:
        """Return True if buffer has received at least window_size frames."""
        return self._count >= self._window_size

    def reset(self) -> None:
        """Clear buffer and counters."""
        self._buffer.fill(0.0)
        self._count = 0
        self._emit_counter = 0
