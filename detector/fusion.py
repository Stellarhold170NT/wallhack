"""Multi-node presence fusion with OR/AND modes and stale-node exclusion.

FusionEngine aggregates per-node PresenceDetector results into a single
system-wide presence state. Supports OR and AND fusion modes, automatic
stale-node exclusion, and graceful degradation for zero/single-node
scenarios.
"""

import logging
import time
from enum import Enum

import numpy as np

from detector.presence import PresenceDetector

logger = logging.getLogger(__name__)


class FusionMode(Enum):
    """Multi-node fusion logic mode."""

    OR = "or"
    AND = "and"


class FusionEngine:
    """Multi-node presence fusion engine.

    Holds a dictionary of per-node PresenceDetector instances and fuses
    their individual detections into a single system-wide presence state.

    Stale nodes (marked via set_node_stale) are excluded from voting
    and must pass 3 consecutive valid update cycles before rejoining.
    """

    def __init__(
        self,
        mode: FusionMode = FusionMode.OR,
        config: dict | None = None,
    ) -> None:
        self.mode = mode
        self._config = config or {}

        self._detectors: dict[int, PresenceDetector] = {}
        self._node_stale: dict[int, bool] = {}
        self._node_recovery: dict[int, int] = {}
        self._last_fused_state: str = "unknown"
        self._last_fused_at: float = 0.0

    def register_node(self, node_id: int) -> None:
        """Register a new node, creating its PresenceDetector.

        Args:
            node_id: Unique node identifier.

        Raises:
            ValueError: If node_id is already registered.
        """
        if node_id in self._detectors:
            raise ValueError(f"Node {node_id} is already registered")

        presence_cfg = {
            k: v
            for k, v in self._config.items()
            if k in {
                "enter_threshold_sigma",
                "exit_threshold_sigma",
                "enter_frames",
                "exit_frames",
                "baseline_alpha",
                "min_baseline_frames",
                "baseline_skip_threshold_sigma",
            }
        }
        self._detectors[node_id] = PresenceDetector(
            node_id=node_id, **presence_cfg
        )
        self._node_stale[node_id] = False
        self._node_recovery[node_id] = 0
        logger.info("📡 FusionEngine: registered node %d", node_id)

    def update_node(
        self, node_id: int, feature_vector: np.ndarray
    ) -> dict | None:
        """Feed a feature vector to a node's detector.

        Auto-registers unknown nodes. Handles stale-node recovery:
        a stale node rejoins fusion after 3 valid consecutive frames
        (D-31).

        Args:
            node_id: Node identifier.
            feature_vector: 1D float64 array matching the
                PresenceDetector feature vector format.

        Returns:
            Per-node detection result (pass-through from
            PresenceDetector.update), or None if no state transition
            occurred or input was invalid.
        """
        if node_id not in self._detectors:
            self.register_node(node_id)

        detector = self._detectors[node_id]
        result = detector.update(feature_vector)

        if self._node_stale.get(node_id, False):
            self._node_recovery[node_id] += 1
            logger.debug(
                "FusionEngine: node %d recovery frame %d/3",
                node_id,
                self._node_recovery[node_id],
            )
            if self._node_recovery[node_id] >= 3:
                self._node_stale[node_id] = False
                self._node_recovery[node_id] = 0
                logger.info(
                    "✅ FusionEngine: node %d recovered after 3 valid frames",
                    node_id,
                )

        return result

    def set_node_stale(self, node_id: int, stale: bool) -> None:
        if node_id not in self._detectors:
            return

        if stale:
            if not self._node_stale.get(node_id, False):
                self._node_stale[node_id] = True
                self._node_recovery[node_id] = 0
                logger.info("⚠️ FusionEngine: node %d marked stale", node_id)
        else:
            if self._node_stale.get(node_id, False):
                logger.info(
                    "FusionEngine: node %d recovery requested, "
                    "waiting for 3 valid frames",
                    node_id,
                )

    def fuse(self) -> dict:
        """Compute the fused system-wide presence state.

        Only healthy (non-stale) nodes participate in voting.

        * 0 healthy nodes → ``"unknown"`` with last known state timestamp.
        * 1 healthy node → that node's current state (D-32).
        * 2+ healthy nodes → OR or AND fusion based on ``self.mode``.

        Returns:
            A dict with keys: ``status``, ``timestamp``, ``node_states``,
            ``fusion_mode``.
        """
        now = time.monotonic()

        healthy_detectors = {
            nid: det
            for nid, det in self._detectors.items()
            if not self._node_stale.get(nid, False)
        }

        node_states: dict[int, str] = {
            nid: (
                "occupied"
                if det.state.value in ("occupied", "confirming_occupied")
                else "empty"
            )
            for nid, det in self._detectors.items()
        }

        if not healthy_detectors:
            result = {
                "status": "unknown",
                "timestamp": now,
                "node_states": node_states,
                "fusion_mode": self.mode.value,
                "last_known": self._last_fused_state,
            }
            logger.info("❓ Fusion: 0 healthy nodes → unknown")
            return result

        if len(healthy_detectors) == 1:
            nid = next(iter(healthy_detectors))
            det = healthy_detectors[nid]
            status = (
                "occupied"
                if det.state.value in ("occupied", "confirming_occupied")
                else "empty"
            )
            icon = "🚨" if status == "occupied" else "✅"
            logger.info(
                "%s Fusion: single node %d → %s (state=%s)",
                icon,
                nid,
                status,
                det.state.value,
            )
            result = {
                "status": status,
                "timestamp": now,
                "node_states": node_states,
                "fusion_mode": self.mode.value,
            }
            self._last_fused_state = status
            self._last_fused_at = now
            return result

        statuses = [
            (
                "occupied"
                if det.state.value in ("occupied", "confirming_occupied")
                else "empty"
            )
            for det in healthy_detectors.values()
        ]

        if self.mode == FusionMode.OR:
            status = "occupied" if any(s == "occupied" for s in statuses) else "empty"
        else:
            status = "occupied" if all(s == "occupied" for s in statuses) else "empty"

        icon = "🚨" if status == "occupied" else "✅"
        logger.info(
            "%s Fusion: %s mode, %d/%d nodes occupied → %s",
            icon,
            self.mode.value.upper(),
            sum(1 for s in statuses if s == "occupied"),
            len(statuses),
            status,
        )

        self._last_fused_state = status
        self._last_fused_at = now

        result = {
            "status": status,
            "timestamp": now,
            "node_states": node_states,
            "fusion_mode": self.mode.value,
        }
        return result

    def get_detector(self, node_id: int) -> PresenceDetector:
        """Return the PresenceDetector for a specific node.

        Args:
            node_id: Node identifier.

        Returns:
            The PresenceDetector instance.

        Raises:
            KeyError: If node_id is not registered.
        """
        return self._detectors[node_id]
