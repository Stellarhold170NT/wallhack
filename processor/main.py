"""Asyncio CsiProcessor task for real-time signal processing.

Consumes raw CSI frames from an input Queue, processes them through
SlidingWindow + feature extraction, and pushes feature vectors to an
output Queue for Phase 4 (presence detection).
"""

import asyncio
import logging
import numpy as np
from aggregator.frame import CSIFrame
from processor.hampel import hampel_filter
from processor.window import SlidingWindow
from processor.features import extract_features
from processor.phase import unwrap_phase, detrend_phase  # noqa: F401 — reserved for phase features

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "window_size": 200,
    "step_size": 100,
    "sample_rate": 50.0,
    "hampel_window": 7,
    "hampel_threshold": 3.0,
    "max_nodes": 16,
}


class CsiProcessor:
    """Asyncio task that processes CSI frames into feature vectors.

    Maintains per-node SlidingWindow state (D-18) and emits feature dicts
    to an output Queue when windows are full.
    """

    def __init__(
        self,
        input_queue: asyncio.Queue,
        output_queue: asyncio.Queue | None = None,
        config: dict | None = None,
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._windows: dict[int, SlidingWindow] = {}
        self._shutdown = asyncio.Event()
        self._max_nodes = self.config["max_nodes"]

    async def run(self) -> None:
        """Main processing loop."""
        logger.info("CsiProcessor started")
        while not self._shutdown.is_set():
            try:
                frame = await asyncio.wait_for(
                    self.input_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            self.process_frame(frame)
        logger.info("CsiProcessor stopped")

    def process_frame(self, frame: CSIFrame) -> dict | None:
        """Process a single frame and return feature dict if window ready."""
        node_id = frame.node_id
        n_subcarriers = frame.n_subcarriers

        if node_id not in self._windows:
            if len(self._windows) >= self._max_nodes:
                logger.warning(
                    "Max nodes (%d) reached — skipping frame from node %d",
                    self._max_nodes,
                    node_id,
                )
                return None
            self._windows[node_id] = SlidingWindow(
                n_subcarriers=n_subcarriers,
                window_size=self.config["window_size"],
                step_size=self.config["step_size"],
            )

        sw = self._windows[node_id]

        # Adapt frame to window's subcarrier count instead of skipping/resetting
        if sw.n_subcarriers != n_subcarriers:
            logger.debug(
                "Node %d: adapting %d-SC frame to window %d",
                node_id,
                n_subcarriers,
                sw.n_subcarriers,
            )
            frame = self._adapt_frame(frame, sw.n_subcarriers)

        amp_window = sw.push(frame)
        if amp_window is None:
            return None

        # Apply Hampel filter per subcarrier (column)
        cleaned = self._apply_hampel(amp_window)

        # Optional phase processing for presence detection
        phase_window = None
        if frame.phases and len(frame.phases) == sw.n_subcarriers:
            # Phase window requires historical data; use current frame only
            # for now. Full phase windowing needs phase collection per node.
            # For v1, we skip phase-based features in real-time path.
            pass

        features = extract_features(
            cleaned,
            phase_window=phase_window,
            sample_rate=self.config["sample_rate"],
        )

        # Flatten to 1D array: mean_amp[N] + var_amp[N] + motion + breathing
        flat = np.concatenate([
            features["mean_amp"],
            features["var_amp"],
            [features["motion_energy"], features["breathing_band"]],
        ])

        feature_dict = {
            "node_id": node_id,
            "window_start_ms": 0,
            "window_end_ms": 0,
            "features": flat,
        }

        logger.info(
            "Node %d: emitted feature vector (len=%d, sc=%d)",
            node_id,
            len(flat),
            sw.n_subcarriers,
        )

        if self.output_queue is not None:
            try:
                self.output_queue.put_nowait(feature_dict)
            except asyncio.QueueFull:
                logger.warning("Output queue full — dropping feature vector")

        return feature_dict

    def _adapt_frame(self, frame: CSIFrame, target_sc: int) -> CSIFrame:
        """Pad or crop frame amplitudes/phases to target subcarrier count."""
        if frame.n_subcarriers == target_sc:
            return frame

        new_amps = self._adapt_array(
            np.asarray(frame.amplitudes, dtype=np.float64), target_sc
        )
        new_phases = None
        if frame.phases:
            new_phases = self._adapt_array(
                np.asarray(frame.phases, dtype=np.float64), target_sc
            )

        return CSIFrame(
            node_id=frame.node_id,
            sequence=frame.sequence,
            timestamp_ms=frame.timestamp_ms,
            rssi=frame.rssi,
            noise_floor=frame.noise_floor,
            frequency_mhz=frame.frequency_mhz,
            n_subcarriers=target_sc,
            amplitudes=new_amps.tolist(),
            phases=new_phases.tolist() if new_phases is not None else [],
        )

    @staticmethod
    def _adapt_array(arr: np.ndarray, target: int) -> np.ndarray:
        """Pad or crop a 1-D array to target length."""
        if len(arr) == target:
            return arr
        if len(arr) > target:
            # Crop from center to preserve core subcarriers
            start = (len(arr) - target) // 2
            return arr[start : start + target]
        # Zero-pad symmetrically
        pad_total = target - len(arr)
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        return np.pad(arr, (pad_left, pad_right), mode="constant")

    def _apply_hampel(self, window: np.ndarray) -> np.ndarray:
        """Apply Hampel filter to each subcarrier column."""
        cleaned = window.copy()
        hampel_w = self.config["hampel_window"]
        hampel_t = self.config["hampel_threshold"]
        for col in range(window.shape[1]):
            cleaned[:, col] = hampel_filter(
                window[:, col], window_size=hampel_w, threshold=hampel_t
            )
        return cleaned

    def stop(self) -> None:
        """Signal the processor to shut down."""
        self._shutdown.set()
