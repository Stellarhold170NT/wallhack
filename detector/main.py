"""Asyncio task wrapper that consumes feature vectors and emits alerts."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from detector.alerts import Alert, AlertManager
from detector.fusion import FusionEngine, FusionMode

logger = logging.getLogger("detector.main")

DEFAULT_CONFIG = {
    "fusion_mode": "or",
    "cooldown_seconds": 5.0,
    "buffer_size": 100,
    "log_dir": "data/alerts",
    "max_nodes": 16,
}


class CsiDetector:
    """Asyncio task that consumes feature_queue and produces alerts."""

    def __init__(
        self,
        input_queue: asyncio.Queue,
        output_queue: Optional[asyncio.Queue] = None,
        node_health_source: Optional[dict] = None,
        config: Optional[dict] = None,
    ) -> None:
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.node_health_source = node_health_source

        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self._max_nodes = cfg["max_nodes"]

        mode = FusionMode.OR if cfg["fusion_mode"] == "or" else FusionMode.AND
        self.fusion = FusionEngine(mode=mode, config=cfg)

        self.alert_manager = AlertManager(
            cooldown_seconds=cfg["cooldown_seconds"],
            buffer_size=cfg["buffer_size"],
            log_dir=cfg["log_dir"],
        )

        self._shutdown = asyncio.Event()

    def stop(self) -> None:
        """Signal the detector loop to exit gracefully."""
        self._shutdown.set()

    async def run(self) -> None:
        """Main processing loop."""
        logger.info("CsiDetector started")
        try:
            while not self._shutdown.is_set():
                try:
                    feature_dict = await asyncio.wait_for(
                        self.input_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    self._sync_stale_state()
                    continue
                except asyncio.CancelledError:
                    break

                node_id = feature_dict["node_id"]
                features = feature_dict["features"]

                if node_id not in self.fusion._detectors:
                    if len(self.fusion._detectors) >= self._max_nodes:
                        logger.warning(
                            "Max nodes reached — skipping node %d", node_id
                        )
                        continue
                    self.fusion.register_node(node_id)

                self._sync_stale_state()
                detector_result = self.fusion.update_node(node_id, features)

                if detector_result is not None:
                    alert_type = (
                        "intrusion"
                        if detector_result["status"] == "occupied"
                        else "clear"
                    )
                    icon = "🔴" if alert_type == "intrusion" else "🟢"
                    logger.info(
                        "%s ALERT: node=%d, type=%s, status=%s, confidence=%.2f, sigma=%.2f",
                        icon,
                        node_id,
                        alert_type,
                        detector_result["status"],
                        detector_result["confidence"],
                        detector_result.get("sigma", 0.0),
                    )
                    alert = Alert(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        node_id=node_id,
                        status=detector_result["status"],
                        confidence=detector_result["confidence"],
                        type=alert_type,
                        trigger_feature=detector_result.get(
                            "trigger_feature", "combined"
                        ),
                    )
                    emitted = await self.alert_manager.emit(alert)
                    if emitted and self.output_queue is not None:
                        try:
                            self.output_queue.put_nowait(alert.to_dict())
                        except asyncio.QueueFull:
                            logger.warning(
                                "⚠️ Alert queue full — dropping alert"
                            )

                fused = self.fusion.fuse()
                heartbeat_emitted = await self.alert_manager.maybe_heartbeat(
                    node_id=0,
                    status=fused["status"],
                    confidence=1.0 if fused["status"] != "unknown" else 0.0,
                )
                if heartbeat_emitted:
                    icon = "🚨" if fused["status"] == "occupied" else "✅"
                    logger.info(
                        "💓 Heartbeat: system=%s%s, nodes=%s",
                        icon,
                        fused["status"],
                        fused.get("node_states", {}),
                    )
        finally:
            logger.info("CsiDetector stopped")

    def _sync_stale_state(self) -> None:
        """Mirror stale flags from the server node dict."""
        if self.node_health_source is None:
            return
        for node_id, node_state in self.node_health_source.items():
            self.fusion.set_node_stale(
                node_id, getattr(node_state, "stale", False)
            )
