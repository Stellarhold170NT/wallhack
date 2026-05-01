"""Unit tests for detector/presence.py and detector/fusion.py."""

import numpy as np
import pytest

from detector.presence import DetectionState, PresenceDetector
from detector.fusion import FusionEngine, FusionMode

rng = np.random.default_rng(42)


def make_feature_vector(motion: float, breathing: float, n_subcarriers: int = 64) -> np.ndarray:
    """Build a synthetic feature vector with the given motion and breathing values."""
    N = n_subcarriers
    fv = np.zeros(N * 2 + 2, dtype=np.float64)
    fv[2 * N] = motion
    fv[2 * N + 1] = breathing
    return fv


# ------------------------------------------------------------------
# PresenceDetector tests
# ------------------------------------------------------------------

class TestPresenceDetector:
    def test_baseline_converges(self):
        det = PresenceDetector(node_id=0, baseline_alpha=0.1)
        for _ in range(20):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        assert det.is_baseline_ready
        assert det._baseline_mean == pytest.approx(1.0, abs=0.1)
        assert det._baseline_std < 0.1

    def test_empty_room_stays_empty(self):
        det = PresenceDetector(node_id=0)
        for _ in range(30):
            result = det.update(make_feature_vector(motion=1.0, breathing=1.0))
        assert det.state == DetectionState.EMPTY
        assert result is None

    def test_motion_triggers_occupied(self):
        det = PresenceDetector(node_id=0, enter_frames=3)
        # Baseline
        for _ in range(10):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        # Motion spike - need 3 consecutive frames
        results = []
        for _ in range(3):
            r = det.update(make_feature_vector(motion=50.0, breathing=50.0))
            results.append(r)
        assert det.state == DetectionState.OCCUPIED
        assert results[-1] is not None
        assert results[-1]["status"] == "occupied"

    def test_single_spike_does_not_trigger(self):
        det = PresenceDetector(node_id=0)
        for _ in range(10):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        det.update(make_feature_vector(motion=50.0, breathing=50.0))
        for _ in range(5):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        assert det.state == DetectionState.EMPTY

    def test_hysteresis_prevents_flip(self):
        det = PresenceDetector(node_id=0, enter_frames=3, exit_frames=5)
        # Establish baseline
        for _ in range(10):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        # Trigger occupied
        for _ in range(3):
            det.update(make_feature_vector(motion=50.0, breathing=50.0))
        assert det.state == DetectionState.OCCUPIED
        # Single dip below exit threshold should NOT flip
        det.update(make_feature_vector(motion=1.0, breathing=1.0))
        assert det.state == DetectionState.CONFIRMING_EMPTY
        # Back above exit threshold → back to OCCUPIED
        det.update(make_feature_vector(motion=50.0, breathing=50.0))
        assert det.state == DetectionState.OCCUPIED

    def test_exit_requires_sustained_low(self):
        det = PresenceDetector(node_id=0, enter_frames=3, exit_frames=5)
        # Baseline + enter
        for _ in range(10):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        for _ in range(3):
            det.update(make_feature_vector(motion=50.0, breathing=50.0))
        assert det.state == DetectionState.OCCUPIED
        # Exit with 5 low frames
        results = []
        for _ in range(5):
            r = det.update(make_feature_vector(motion=1.0, breathing=1.0))
            results.append(r)
        assert det.state == DetectionState.EMPTY
        assert results[-1] is not None
        assert results[-1]["status"] == "empty"

    def test_confidence_range(self):
        det = PresenceDetector(node_id=0, enter_frames=1)
        for _ in range(10):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        # Force immediate transition with enter_frames=1
        r = det.update(make_feature_vector(motion=100.0, breathing=100.0))
        assert r is not None
        assert 0.0 <= r["confidence"] <= 1.0

    def test_nan_input_returns_none(self):
        det = PresenceDetector(node_id=0)
        fv = make_feature_vector(motion=1.0, breathing=1.0)
        fv[0] = np.nan
        result = det.update(fv)
        assert result is None

    def test_inf_input_returns_none(self):
        det = PresenceDetector(node_id=0)
        fv = make_feature_vector(motion=1.0, breathing=1.0)
        fv[0] = np.inf
        result = det.update(fv)
        assert result is None

    def test_baseline_resets(self):
        det = PresenceDetector(node_id=0)
        for _ in range(15):
            det.update(make_feature_vector(motion=1.0, breathing=1.0))
        assert det.is_baseline_ready
        det.reset_baseline()
        assert not det.is_baseline_ready
        assert det._baseline_mean == 0.0

    def test_short_vector_returns_none(self):
        det = PresenceDetector(node_id=0)
        result = det.update(np.array([1.0, 2.0], dtype=np.float64))
        assert result is None

    def test_wrong_dimensions_returns_none(self):
        det = PresenceDetector(node_id=0)
        result = det.update(np.zeros((10, 10), dtype=np.float64))
        assert result is None


# ------------------------------------------------------------------
# FusionEngine tests
# ------------------------------------------------------------------

class TestFusionEngine:
    def test_or_mode_any_occupied(self):
        engine = FusionEngine(mode=FusionMode.OR)
        # Baseline both nodes
        for _ in range(10):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
            engine.update_node(1, make_feature_vector(1.0, 1.0))
        # Occupy node 0 only
        for _ in range(3):
            engine.update_node(0, make_feature_vector(50.0, 50.0))
            engine.update_node(1, make_feature_vector(1.0, 1.0))
        fused = engine.fuse()
        assert fused["status"] == "occupied"

    def test_and_mode_requires_all(self):
        engine = FusionEngine(mode=FusionMode.AND)
        for _ in range(10):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
            engine.update_node(1, make_feature_vector(1.0, 1.0))
        for _ in range(3):
            engine.update_node(0, make_feature_vector(50.0, 50.0))
            engine.update_node(1, make_feature_vector(1.0, 1.0))
        fused = engine.fuse()
        assert fused["status"] == "empty"

    def test_stale_node_excluded(self):
        engine = FusionEngine(mode=FusionMode.OR)
        for _ in range(10):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
            engine.update_node(1, make_feature_vector(1.0, 1.0))
        engine.set_node_stale(1, True)
        # Feed only 2 frames to stale node so it does not recover (D-31)
        for _ in range(2):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
            engine.update_node(1, make_feature_vector(50.0, 50.0))
        fused = engine.fuse()
        assert fused["status"] == "empty"
        assert fused["node_states"][1] == "occupied"  # node1 still tracked

    def test_zero_nodes_unknown(self):
        engine = FusionEngine()
        fused = engine.fuse()
        assert fused["status"] == "unknown"
        assert "last_known" in fused

    def test_single_node_degradation(self):
        engine = FusionEngine()
        for _ in range(10):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
        for _ in range(3):
            engine.update_node(0, make_feature_vector(50.0, 50.0))
        fused = engine.fuse()
        assert fused["status"] == "occupied"

    def test_node_rejoin_after_recovery(self):
        engine = FusionEngine()
        for _ in range(10):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
        engine.set_node_stale(0, True)
        assert engine._node_stale[0]
        # Feed 3 valid frames to recover
        for _ in range(3):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
        assert not engine._node_stale[0]

    def test_duplicate_registration_raises(self):
        engine = FusionEngine()
        engine.register_node(0)
        with pytest.raises(ValueError):
            engine.register_node(0)

    def test_get_detector(self):
        engine = FusionEngine()
        engine.register_node(5)
        det = engine.get_detector(5)
        assert det.node_id == 5

    def test_fused_includes_node_states(self):
        engine = FusionEngine()
        for _ in range(10):
            engine.update_node(0, make_feature_vector(1.0, 1.0))
        fused = engine.fuse()
        assert "node_states" in fused
        assert 0 in fused["node_states"]
        assert fused["fusion_mode"] == "or"

    def test_set_node_stale_unknown_no_op(self):
        engine = FusionEngine()
        engine.set_node_stale(99, True)
        assert 99 not in engine._detectors
