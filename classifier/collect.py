"""CLI data collection tool for labeled CSI activity recording.

Records UDP CSI frames from ESP32-S3 node(s) for a specified
duration, assembles 50-frame sliding windows (25-frame step),
and saves amplitude matrices as .npy with metadata JSON sidecars.

Usage:
    python -m classifier.collect --label walking --duration 30 --output data/activities/

Ref: D-37, D-40
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import signal
import time
from collections import deque
from datetime import datetime, timezone

import numpy as np

from aggregator.parser import parse_frame

logger = logging.getLogger(__name__)

VALID_LABELS = {"walking", "running", "lying", "bending"}
WINDOW_SIZE = 50
WINDOW_STEP = 25


class CsiCollector:
    """Records CSI amplitude windows from UDP streams for a labeled activity.

    Args:
        label: Activity label (walking, running, lying, bending).
        duration: Recording duration in seconds.
        output_dir: Root directory for saved .npy + .json files.
        port: UDP port to bind (default 5005).
        host: Bind address (default 0.0.0.0).
        min_samples: Minimum 50-frame windows to collect.
    """

    def __init__(
        self,
        label: str,
        duration: float,
        output_dir: str = "data/activities",
        port: int = 5005,
        host: str = "0.0.0.0",
        min_samples: int = 10,
    ) -> None:
        if label not in VALID_LABELS:
            raise ValueError(
                f"Unknown label {label!r}. Must be one of {sorted(VALID_LABELS)}"
            )

        self.label = label
        self.duration = duration
        self.output_dir = pathlib.Path(output_dir) / label
        self.port = port
        self.host = host
        self.min_samples = min_samples

        self._transport: asyncio.DatagramTransport | None = None
        self._buffers: dict[int, deque[np.ndarray]] = {}
        self._window_counts: dict[int, int] = {}
        self._total_frames = 0
        self._total_windows = 0
        self._shutdown = asyncio.Event()

    def _save_window(self, node_id: int, window: np.ndarray) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        base = self.output_dir / f"{timestamp}_{node_id}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        np.save(base.with_suffix(".npy"), window.astype(np.float32))

        metadata = {
            "label": self.label,
            "duration": self.duration,
            "node_id": node_id,
            "subcarrier_count": int(window.shape[1]),
            "sample_count": int(window.shape[0]),
            "timestamp": timestamp,
            "window_size": WINDOW_SIZE,
            "step_size": WINDOW_STEP,
        }
        base.with_suffix(".json").write_text(json.dumps(metadata, indent=2))

        self._window_counts[node_id] = self._window_counts.get(node_id, 0) + 1
        self._total_windows += 1

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if self._shutdown.is_set():
            return

        frame = parse_frame(data)
        if frame is None:
            return

        node_id = frame.node_id
        amplitudes = np.array(frame.amplitudes, dtype=np.float32)

        if node_id not in self._buffers:
            self._buffers[node_id] = deque()

        self._buffers[node_id].append(amplitudes)
        self._total_frames += 1

        buf = self._buffers[node_id]
        while len(buf) >= WINDOW_SIZE:
            window = np.stack(list(buf)[:WINDOW_SIZE], axis=0)
            self._save_window(node_id, window)

            for _ in range(WINDOW_STEP):
                buf.popleft()

    def error_received(self, exc: Exception) -> None:
        logger.warning("UDP error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        pass

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.host, self.port),
        )
        logger.info(
            "Recording %r for %.0fs on %s:%d → %s",
            self.label, self.duration, self.host, self.port, self.output_dir,
        )

    async def stop(self) -> None:
        self._shutdown.set()
        if self._transport:
            self._transport.close()
        logger.info(
            "Recording complete — %d frames, %d windows saved",
            self._total_frames, self._total_windows,
        )

    async def run(self) -> None:
        await self.start()

        try:
            last_report = time.monotonic()
            end_time = time.monotonic() + self.duration

            while time.monotonic() < end_time:
                now = time.monotonic()
                if now - last_report >= 2.0:
                    logger.info(
                        "Recording %s... %d frames, %d windows saved",
                        self.label, self._total_frames, self._total_windows,
                    )
                    last_report = now
                await asyncio.sleep(0.1)

            if self._total_windows < self.min_samples:
                logger.warning(
                    "Only %d windows collected (min: %d) — try longer duration",
                    self._total_windows, self.min_samples,
                )

        finally:
            await self.stop()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Record labeled CSI activity data"
    )
    parser.add_argument(
        "--label", required=True,
        help="Activity label (walking, running, lying, bending)",
    )
    parser.add_argument(
        "--duration", type=float, default=30.0,
        help="Recording duration in seconds (default: 30)",
    )
    parser.add_argument(
        "--output-dir", default="data/activities",
        help="Output directory (default: data/activities/)",
    )
    parser.add_argument(
        "--port", type=int, default=5005,
        help="UDP port (default: 5005)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--min-samples", type=int, default=10,
        help="Minimum 50-frame windows to collect (default: 10)",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    label = args.label
    if label not in VALID_LABELS:
        parser.error(
            f"Invalid label {label!r}. Must be one of {sorted(VALID_LABELS)}"
        )

    collector = CsiCollector(
        label=label,
        duration=args.duration,
        output_dir=args.output_dir,
        port=args.port,
        host=args.host,
        min_samples=args.min_samples,
    )

    loop = asyncio.new_event_loop()

    def _sig_handler():
        logger.info("Interrupted — stopping...")
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(collector.stop()))

    try:
        loop.add_signal_handler(signal.SIGINT, _sig_handler)
    except NotImplementedError:
        pass

    try:
        loop.run_until_complete(collector.run())
    except KeyboardInterrupt:
        logger.info("Interrupted — stopping...")
        loop.run_until_complete(collector.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
