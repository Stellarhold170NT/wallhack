"""Raw CSI amplitude persistence as .npy files for Phase 5 dataset collection.

Writes amplitude matrices with companion metadata JSON per node,
organized by timestamped session directories under data/raw/.

Ref: D-08 (only amplitudes, not phases)
"""

import json
import time
import logging
import pathlib
from datetime import datetime

import numpy as np

from .frame import CSIFrame

logger = logging.getLogger(__name__)


class NpyWriter:
    """Accumulates CSI amplitudes per node and flushes to .npy files.

    Rotation: when a node reaches *rotation_frames* frames, its buffer
    is flushed to disk and cleared for the next batch.

    Args:
        output_dir: Root directory for data (default: "data/raw").
        rotation_frames: Frames per .npy file before auto-rotation.
    """

    def __init__(
        self,
        output_dir: str = "data/raw",
        rotation_frames: int = 10000,
    ) -> None:
        self.output_dir = pathlib.Path(output_dir)
        self.rotation_frames = rotation_frames
        self._buffers: dict[int, list[list[float]]] = {}
        self._frame_counts: dict[int, int] = {}
        self._start_times: dict[int, float] = {}
        self._session_dir: pathlib.Path | None = None
        self._flush_counter: dict[int, int] = {}

    def _ensure_session_dir(self) -> pathlib.Path:
        if self._session_dir is None:
            self._session_dir = self.output_dir / datetime.now().strftime(
                "%Y-%m-%d_%H-%M"
            )
            self._session_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created session directory: %s", self._session_dir)
        return self._session_dir

    def write(self, frame: CSIFrame) -> None:
        node_id = frame.node_id

        if node_id not in self._buffers:
            self._buffers[node_id] = []
            self._frame_counts[node_id] = 0
            self._start_times[node_id] = time.time()

        self._buffers[node_id].append(frame.amplitudes)
        self._frame_counts[node_id] += 1

        if self._frame_counts[node_id] >= self.rotation_frames:
            self._flush_node(node_id)

    def _flush_node(self, node_id: int) -> None:
        if node_id not in self._buffers or not self._buffers[node_id]:
            return

        session_dir = self._ensure_session_dir()
        self._flush_counter[node_id] = self._flush_counter.get(node_id, 0) + 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch = self._flush_counter[node_id]
        npy_path = session_dir / f"node_{node_id}_{ts}_{batch:04d}.npy"
        meta_path = session_dir / f"node_{node_id}_{ts}_{batch:04d}.json"

        arr = np.array(self._buffers[node_id], dtype=np.float32)
        np.save(npy_path, arr)

        metadata = {
            "node_id": node_id,
            "start_time": self._start_times.get(node_id, 0.0),
            "frame_count": len(self._buffers[node_id]),
            "shape": list(arr.shape),
        }
        meta_path.write_text(json.dumps(metadata, indent=2))

        logger.info(
            "Flushed %d frames (shape %s) to %s",
            len(self._buffers[node_id]),
            arr.shape,
            npy_path,
        )

        self._buffers[node_id] = []
        self._frame_counts[node_id] = 0
        self._start_times[node_id] = time.time()

    def flush_all(self) -> None:
        for node_id in list(self._buffers.keys()):
            self._flush_node(node_id)
