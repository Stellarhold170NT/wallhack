"""Real-time activity classification inference as asyncio task.

Consumes raw CSI frames from an input Queue via amplitude_queue fan-out,
accumulates 50-frame sliding windows per node, runs Attention-GRU
inference, and emits ActivityLabel dicts to an output Queue.

Ref: D-34, D-35, D-37, D-39
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger("classifier.infer")

LABEL_MAP = {
    0: "walking",
    1: "sitting",
    2: "standing",
}
TARGET_SUBCARRIERS = 52
WINDOW_SIZE = 50
STEP_SIZE = 25

DEFAULT_CONFIG: dict[str, Any] = {
    "confidence_threshold": 0.0,
    "max_nodes": 16,
    "window_size": WINDOW_SIZE,
    "step_size": STEP_SIZE,
    "target_subcarriers": TARGET_SUBCARRIERS,
}


def _center_crop_1d(arr: np.ndarray, target: int, axis: int) -> np.ndarray:
    """Center-crop or pad a 1-D array to target length."""
    n = arr.shape[axis]
    if n <= target:
        pad_before = (target - n) // 2
        pad_after = target - n - pad_before
        pad_width = [(0, 0)] * arr.ndim
        pad_width[axis] = (pad_before, pad_after)
        return np.pad(arr, pad_width, mode="constant")
    start = (n - target) // 2
    slc = [slice(None)] * arr.ndim
    slc[axis] = slice(start, start + target)
    return arr[tuple(slc)]


@dataclass
class ActivityLabel:
    """Classification result for a single window.

    Fields:
        timestamp: ISO8601 UTC timestamp when inference completed.
        node_id: Source ESP32-S3 node identifier.
        label: Predicted activity class or "unknown".
        confidence: Softmax probability of the predicted class.
        class_probs: Dict mapping class names to probabilities.
    """

    timestamp: str
    node_id: int
    label: str
    confidence: float
    class_probs: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "node_id": self.node_id,
            "label": self.label,
            "confidence": self.confidence,
            "class_probs": self.class_probs,
        }


class SlidingWindowBuffer:
    """Per-node circular accumulator for raw amplitude frames.

    Accepts frames with variable subcarrier counts, center-crops/pads
    to TARGET_SUBCARRIERS, and emits (window_size, TARGET_SUBCARRIERS)
    arrays using step_size overlap.
    """

    def __init__(
        self,
        window_size: int = WINDOW_SIZE,
        step_size: int = STEP_SIZE,
        target_subcarriers: int = TARGET_SUBCARRIERS,
    ) -> None:
        self.window_size = window_size
        self.step_size = step_size
        self.target_subcarriers = target_subcarriers
        self._buffers: dict[int, list[np.ndarray]] = {}

    def push(self, node_id: int, amplitudes: np.ndarray) -> np.ndarray | None:
        """Append a frame and return a full window if ready.

        Args:
            node_id: ESP32-S3 node identifier.
            amplitudes: 1-D numpy array of subcarrier amplitudes.

        Returns:
            (window_size, target_subcarriers) array or None.
        """
        processed = _center_crop_1d(amplitudes, self.target_subcarriers, axis=0)

        if node_id not in self._buffers:
            self._buffers[node_id] = []

        buf = self._buffers[node_id]
        buf.append(processed)

        if len(buf) < self.window_size:
            return None

        window = np.stack(buf[: self.window_size], axis=0).astype(np.float32)
        # Slide: discard first step_size frames
        self._buffers[node_id] = buf[self.step_size :]
        return window

    def reset_node(self, node_id: int) -> None:
        """Clear buffer for a specific node."""
        self._buffers.pop(node_id, None)


class CsiClassifier:
    """Asyncio task for real-time activity classification.

    Loads a trained Attention-GRU model and StandardScaler from a
    checkpoint, consumes raw CSI frames, and emits ActivityLabel dicts.

    Follows the same pattern as CsiProcessor and CsiDetector.
    """

    def __init__(
        self,
        input_queue: asyncio.Queue,
        output_queue: asyncio.Queue | None = None,
        model_path: str = "checkpoints/best_model.pth",
        scaler_path: str = "checkpoints/scaler.json",
        config: dict[str, Any] | None = None,
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue

        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self._max_nodes = int(cfg["max_nodes"])
        self._confidence_threshold = float(cfg.get("confidence_threshold", 0.0))

        self._id2label: dict[int, str] = {**LABEL_MAP}

        # ---- Load model ----
        from classifier.train import load_checkpoint

        model, meta = load_checkpoint(model_path, device="cpu")
        self._model = model
        self._model.eval()

        scaler = meta.get("scaler")
        if scaler is not None:
            self._scaler = scaler
        else:
            from classifier.dataset import load_scaler

            self._scaler = load_scaler(scaler_path)
        logger.info(
            "Loaded model (input=%d, output=%d) from %s",
            getattr(self._model, "input_dim", 52),
            getattr(self._model, "output_dim", 6),
            model_path,
        )

        # ---- Sliding window buffer ----
        buffer_cfg = {
            k: int(cfg[k])
            for k in ("window_size", "step_size", "target_subcarriers")
            if k in cfg
        }
        self._buffer = SlidingWindowBuffer(**buffer_cfg)

        self._shutdown = asyncio.Event()

    def stop(self) -> None:
        """Signal the classifier loop to exit gracefully."""
        self._shutdown.set()

    async def run(self) -> None:
        """Main inference loop.

        Drains input_queue, accumulates windows, and emits predictions.
        """
        logger.info(
            "CsiClassifier started (threshold=%.2f, max_nodes=%d)",
            self._confidence_threshold,
            self._max_nodes,
        )
        try:
            while not self._shutdown.is_set():
                try:
                    frame = await asyncio.wait_for(
                        self.input_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break

                self._process_frame(frame)
        finally:
            logger.info("CsiClassifier stopped")

    def _process_frame(self, frame: Any) -> None:
        """Process a single incoming frame.

        Expects a CSIFrame-like object with node_id, amplitudes, and
        optionally n_subcarriers.
        """
        node_id = getattr(frame, "node_id", None)
        if node_id is None:
            logger.warning("Frame missing node_id — skipping")
            return

        # Reject new nodes when at capacity
        if (node_id not in self._buffer._buffers
                and len(self._buffer._buffers) >= self._max_nodes):
            logger.debug("Max nodes reached — skipping node %d", node_id)
            return

        amplitudes = np.asarray(getattr(frame, "amplitudes", []), dtype=np.float32)
        if amplitudes.size == 0:
            logger.warning("Empty amplitudes for node %d — skipping", node_id)
            return

        # Guard against malformed input (T-05-07)
        if not np.all(np.isfinite(amplitudes)):
            logger.warning(
                "Non-finite amplitudes for node %d seq %d — dropping",
                node_id,
                getattr(frame, "sequence", -1),
            )
            return

        window = self._buffer.push(node_id, amplitudes)
        if window is None:
            return

        # Normalize: flatten → transform → reshape
        orig_shape = window.shape  # (window_size, target_subcarriers)
        flat = window.reshape(1, -1).astype(np.float64)
        normalized = self._scaler.transform(flat)
        window_norm = normalized.reshape(orig_shape).astype(np.float32)

        # Temporal difference: highlight motion patterns (Matching dataset.py logic)
        window_diff = np.diff(window_norm, axis=0)  # (49, 52)
        # Pad first row with zeros to maintain 50 timesteps
        window_final = np.vstack([np.zeros((1, window_norm.shape[1]), dtype=window_norm.dtype), window_diff])
        
        # Inference
        tensor = torch.from_numpy(window_final).unsqueeze(0)  # (1, T, C)
        t_start = time.perf_counter()
        with torch.no_grad():
            logits = self._model(tensor)
        elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()
        best_idx = int(np.argmax(probs))
        confidence = float(probs[best_idx])

        if confidence < self._confidence_threshold:
            label = "unknown"
        else:
            label = self._id2label.get(best_idx, "unknown")

        activity = ActivityLabel(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node_id=node_id,
            label=label,
            confidence=confidence,
            class_probs={
                self._id2label.get(i, str(i)): float(p)
                for i, p in enumerate(probs)
            },
        )

        logger.info(
            "Node %d Activity: %s (confidence=%.2f)",
            node_id,
            label.upper(),
            confidence,
        )
        logger.debug(
            "Inference latency: %.2f ms",
            elapsed_ms,
        )
        if elapsed_ms > 10.0:
            logger.warning(
                "Inference latency %.2f ms exceeds 10 ms target",
                elapsed_ms,
            )

        if self.output_queue is not None:
            try:
                self.output_queue.put_nowait(activity.to_dict())
            except asyncio.QueueFull:
                logger.warning(
                    "Activity queue full — dropping prediction for node %d",
                    node_id,
                )
