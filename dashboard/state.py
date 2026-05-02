from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Callable

import numpy as np

logger = logging.getLogger("dashboard.state")


def _to_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    if hasattr(item, "to_dict"):
        return item.to_dict()
    return {}


class DashboardState:
    def __init__(
        self,
        alert_queue: asyncio.Queue,
        activity_queue: asyncio.Queue,
        amplitude_queue: asyncio.Queue,
        node_source: Callable[[], dict] | None = None,
    ) -> None:
        self.alert_queue = alert_queue
        self.activity_queue = activity_queue
        self.amplitude_queue = amplitude_queue
        self._node_source = node_source

        self._presence: dict[int, str] = {}
        self._activity: dict[int, dict] = {}
        self._alerts: deque[dict] = deque(maxlen=50)
        self._heatmap: dict[int, deque] = {}
        self._shutdown = asyncio.Event()

        self._tasks: list[asyncio.Task] = []

    def stop(self) -> None:
        self._shutdown.set()
        for t in self._tasks:
            t.cancel()

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._consume_alerts()),
            asyncio.create_task(self._consume_activity()),
            asyncio.create_task(self._consume_amplitude()),
        ]
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _consume_alerts(self) -> None:
        while not self._shutdown.is_set():
            try:
                item = await asyncio.wait_for(self.alert_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            d = _to_dict(item)
            self._alerts.appendleft(d)
            node_id = d.get("node_id")
            if node_id is not None and d.get("type") == "intrusion":
                self._presence[node_id] = d.get("status", "unknown")
            logger.debug("Alert consumed: node=%s type=%s", node_id, d.get("type"))

    async def _consume_activity(self) -> None:
        while not self._shutdown.is_set():
            try:
                item = await asyncio.wait_for(self.activity_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            d = _to_dict(item)
            node_id = d.get("node_id")
            if node_id is not None:
                self._activity[node_id] = d
            logger.debug("Activity consumed: node=%s label=%s", node_id, d.get("label"))

    async def _consume_amplitude(self) -> None:
        while not self._shutdown.is_set():
            try:
                frame = await asyncio.wait_for(self.amplitude_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            node_id = getattr(frame, "node_id", None)
            if node_id is None and isinstance(frame, dict):
                node_id = frame.get("node_id")
            amps = getattr(frame, "amplitudes", None)
            if amps is None and isinstance(frame, dict):
                amps = frame.get("amplitudes")
            if node_id is not None and amps is not None:
                if node_id not in self._heatmap:
                    self._heatmap[node_id] = deque(maxlen=200)
                self._heatmap[node_id].append(np.asarray(amps, dtype=np.float32))

    def get_status(self) -> dict:
        return {
            "presence": self._presence.copy(),
            "activity": self._activity.copy(),
            "node_health": self._get_node_health(),
        }

    def get_alerts(self, count: int = 50) -> list[dict]:
        return list(self._alerts)[:count]

    def get_heatmap(self) -> dict[int, list[list[float]]]:
        return {
            nid: [arr.tolist() for arr in self._heatmap[nid]]
            for nid in self._heatmap
        }

    def _get_node_health(self) -> dict:
        if self._node_source is None:
            return {}
        nodes = self._node_source()
        health: dict = {}
        for nid, node in nodes.items():
            health[nid] = {
                "fps": getattr(node, "fps", 0),
                "stale": getattr(node, "stale", False),
                "frame_count": getattr(node, "frame_count", 0),
                "last_seen": getattr(node, "last_seen", 0.0),
            }
        return health
