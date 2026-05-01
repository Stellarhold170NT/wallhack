"""Detector package — presence detection and multi-node fusion."""

from detector.fusion import FusionEngine, FusionMode
from detector.presence import DetectionState, PresenceDetector

__all__ = [
    "DetectionState",
    "FusionEngine",
    "FusionMode",
    "PresenceDetector",
]
