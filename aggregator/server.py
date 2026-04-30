"""Asyncio UDP server with dynamic node discovery and health tracking.

Binds to a UDP port, receives raw CSI frames, parses them via parser.py,
buffers per-node via buffer.py, and pushes to an asyncio.Queue for Phase 3.

Ref: D-06 (Queue handoff), D-10 (dynamic discovery)
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from collections import deque

from .frame import CSIFrame  # noqa: F401 — used via parse_frame return type
from .parser import parse_frame
from .buffer import NodeBuffer

logger = logging.getLogger(__name__)


@dataclass
class NodeState:
    """Runtime state for a dynamically discovered ESP32-S3 node."""

    node_id: int
    addr: tuple[str, int]
    buffer: NodeBuffer
    last_seen: float = 0.0
    frame_count: int = 0
    loss_count: int = 0
    last_sequence: int | None = None
    stale: bool = False


class CsiUdpServer(asyncio.DatagramProtocol):
    """Asyncio UDP server that receives and processes CSI frames.

    Dynamically discovers nodes on first valid frame, buffers frames
    per node with bounded memory, and pushes to an asyncio.Queue
    for downstream consumer (Phase 3 signal processing).

    Args:
        port: UDP port to bind (default 5005).
        queue: asyncio.Queue for Phase 3 handoff (created if None).
        buffer_capacity: Max frames per node before dropping oldest.
    """

    def __init__(
        self,
        port: int = 5005,
        queue: asyncio.Queue | None = None,
        buffer_capacity: int = 500,
    ) -> None:
        self.port = port
        self.buffer_capacity = buffer_capacity
        self.queue: asyncio.Queue = queue or asyncio.Queue(maxsize=0)
        self.nodes: dict[int, NodeState] = {}
        self.transport: asyncio.DatagramTransport | None = None

        self._shutdown_event = asyncio.Event()
        self._fps_task: asyncio.Task | None = None
        self._stale_task: asyncio.Task | None = None
        self._prev_frame_counts: dict[int, int] = {}
        # History stores (frame_count, loss_count) snapshots per second for accurate sustained loss calculation
        self._history: dict[int, deque[tuple[int, int]]] = {}

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport
        logger.info("UDP server bound to port %d", self.port)

    def connection_lost(self, exc: Exception | None) -> None:
        logger.info("UDP server connection lost%s", f": {exc}" if exc else "")

    def error_received(self, exc: Exception) -> None:
        logger.warning("UDP server error: %s", exc)

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        frame = parse_frame(data)
        if frame is None:
            return

        node_id = frame.node_id

        if node_id not in self.nodes:
            buffer = NodeBuffer(node_id, capacity=self.buffer_capacity)
            self.nodes[node_id] = NodeState(
                node_id=node_id,
                addr=addr,
                buffer=buffer,
                last_seen=time.monotonic(),
                frame_count=1,
                loss_count=0,
                last_sequence=frame.sequence,
            )
            self._prev_frame_counts[node_id] = 0
            self._history[node_id] = deque(maxlen=11)
            logger.info("Discovered new node %d at %s:%d", node_id, addr[0], addr[1])
        else:
            node = self.nodes[node_id]
            node.last_seen = time.monotonic()
            node.frame_count += 1
            node.stale = False

            if node.last_sequence is not None and frame.sequence > node.last_sequence:
                gap = frame.sequence - node.last_sequence - 1
                if gap > 0:
                    node.loss_count += gap

            node.last_sequence = frame.sequence

        node = self.nodes[node_id]
        node.buffer.push(frame)

        try:
            self.queue.put_nowait(frame)
        except asyncio.QueueFull:
            logger.warning("Queue full — dropping frame node=%d seq=%d", node_id, frame.sequence)

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=("0.0.0.0", self.port),
        )
        self._fps_task = asyncio.create_task(self._fps_logger())
        self._stale_task = asyncio.create_task(self._stale_checker())
        logger.info("CSI UDP Aggregator running on 0.0.0.0:%d", self.port)

    async def stop(self) -> None:
        logger.info("Stopping UDP aggregator...")
        self._shutdown_event.set()

        for task in (self._fps_task, self._stale_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self.transport:
            self.transport.close()

    async def _fps_logger(self) -> None:
        while not self._shutdown_event.is_set():
            await asyncio.sleep(1.0)
            for node_id, node in list(self.nodes.items()):
                prev = self._prev_frame_counts.get(node_id, 0)
                fps = node.frame_count - prev
                self._prev_frame_counts[node_id] = node.frame_count

                hist = self._history.get(node_id)
                if hist is not None:
                    hist.append((node.frame_count, node.loss_count))

                logger.info(
                    "Node %d: %d fps, %d total frames, %d dropped, %d loss",
                    node_id,
                    fps,
                    node.frame_count,
                    node.buffer.drop_count,
                    node.loss_count,
                )

                if hist and len(hist) == 11:
                    old_frames, old_loss = hist[0]
                    new_frames, new_loss = hist[-1]
                    recent_frames = new_frames - old_frames
                    recent_loss = new_loss - old_loss
                    if recent_frames > 0:
                        sustained = recent_loss / recent_frames
                        if sustained > 0.05:
                            logger.warning(
                                "Node %d: sustained loss %.1f%% (alert threshold 5%%) over last ~10s",
                                node_id,
                                sustained * 100,
                            )

    async def _stale_checker(self) -> None:
        while not self._shutdown_event.is_set():
            await asyncio.sleep(1.0)
            now = time.monotonic()
            for node in self.nodes.values():
                if not node.stale and (now - node.last_seen > 10.0):
                    node.stale = True
                    logger.info("Node %d marked stale (no frames for >10s)", node.node_id)
