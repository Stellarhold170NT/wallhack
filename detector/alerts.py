"""Alert emission with cooldown, JSONL persistence, and in-memory buffer."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("detector.alerts")


@dataclass
class Alert:
    """Single presence-detection alert."""

    timestamp: str
    node_id: int
    status: str
    confidence: float
    type: str
    trigger_feature: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "node_id": self.node_id,
            "status": self.status,
            "confidence": round(self.confidence, 4),
            "type": self.type,
            "trigger_feature": self.trigger_feature,
        }


class AlertManager:
    """Manages alert emission with cooldown, JSONL logging, and ring buffer."""

    def __init__(
        self,
        cooldown_seconds: float = 5.0,
        buffer_size: int = 100,
        log_dir: str = "data/alerts",
        heartbeat_interval: float = 30.0,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.buffer_size = buffer_size
        self.log_dir = log_dir
        self.heartbeat_interval = heartbeat_interval

        self._last_alert_time: float = 0.0
        self._buffer: deque[Alert] = deque(maxlen=buffer_size)
        self._heartbeat_last: float = 0.0
        self._lock = asyncio.Lock()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        os.makedirs(self.log_dir, exist_ok=True)
        self._log_file_path = os.path.join(
            self.log_dir, f"alerts_{today}.jsonl"
        )

    async def emit(self, alert: Alert) -> bool:
        """Emit an alert if it passes cooldown checks.

        Intrusion alerts are subject to *cooldown_seconds*.  Clear and
        heartbeat alerts bypass the cooldown.

        Returns:
            ``True`` if the alert was accepted and persisted.
        """
        now = asyncio.get_event_loop().time()

        async with self._lock:
            if alert.type == "intrusion":
                if now - self._last_alert_time < self.cooldown_seconds:
                    logger.debug(
                        "Alert cooldown active — suppressing intrusion"
                    )
                    return False
                self._last_alert_time = now

            self._buffer.append(alert)

            try:
                with open(
                    self._log_file_path, "a", encoding="utf-8"
                ) as fh:
                    fh.write(
                        json.dumps(
                            alert.to_dict(), ensure_ascii=False
                        )
                        + "\n"
                    )
            except OSError as exc:
                logger.error("Failed to write alert to JSONL: %s", exc)

        return True

    async def maybe_heartbeat(
        self, node_id: int, status: str, confidence: float
    ) -> bool:
        """Emit a periodic heartbeat alert if the interval has elapsed."""
        now = asyncio.get_event_loop().time()
        if now - self._heartbeat_last < self.heartbeat_interval:
            return False

        self._heartbeat_last = now
        alert = Alert(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node_id=node_id,
            status=status,
            confidence=confidence,
            type="heartbeat",
            trigger_feature="combined",
        )
        return await self.emit(alert)

    def get_recent(self, count: int = 50) -> list[dict]:
        return [
            a.to_dict()
            for a in list(self._buffer)[-count:][::-1]
        ]

    def get_buffer_size(self) -> int:
        return len(self._buffer)
