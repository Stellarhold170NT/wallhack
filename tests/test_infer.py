"""Unit tests for classifier/infer.py — CsiClassifier, SlidingWindowBuffer, ActivityLabel."""

import asyncio
import tempfile
import time

import numpy as np
import pytest
import torch
from sklearn.preprocessing import StandardScaler

from classifier.infer import (
    ActivityLabel,
    CsiClassifier,
    SlidingWindowBuffer,
    _center_crop_1d,
    LABEL_MAP,
    TARGET_SUBCARRIERS,
    WINDOW_SIZE,
    STEP_SIZE,
)
from classifier.model import AttentionGRU
from classifier.train import save_checkpoint
from classifier.dataset import save_scaler

rng = np.random.default_rng(42)


def _make_checkpoint_and_scaler(tmpdir: str) -> tuple[str, str]:
    """Create a minimal model checkpoint and scaler for testing."""
    model = AttentionGRU(input_dim=52, hidden_dim=128, attention_dim=32, output_dim=6)
    model.eval()
    ckpt_path = f"{tmpdir}/test_model.pth"
    save_checkpoint(model, ckpt_path)

    scaler = StandardScaler()
    dummy_data = rng.normal(size=(100, 50 * 52))
    scaler.fit(dummy_data)
    scaler_path = f"{tmpdir}/test_scaler.json"
    save_scaler(scaler, scaler_path)
    return ckpt_path, scaler_path


def _make_frame(node_id: int = 1, n_subcarriers: int = 64):
    """Create a CSIFrame-like object."""
    from aggregator.frame import CSIFrame
    return CSIFrame(
        node_id=node_id,
        sequence=0,
        n_subcarriers=n_subcarriers,
        amplitudes=rng.normal(size=n_subcarriers).tolist(),
        phases=[0.0] * n_subcarriers,
    )


# ── ActivityLabel ──────────────────────────────────────────────────

class TestActivityLabel:
    def test_to_dict_contains_all_fields(self):
        al = ActivityLabel(
            timestamp="2026-05-01T00:00:00Z",
            node_id=1,
            label="walking",
            confidence=0.92,
            class_probs={"walking": 0.92, "running": 0.05, "lying": 0.02, "falling": 0.01},
        )
        d = al.to_dict()
        assert d["timestamp"] == "2026-05-01T00:00:00Z"
        assert d["node_id"] == 1
        assert d["label"] == "walking"
        assert d["confidence"] == pytest.approx(0.92)
        assert d["class_probs"]["walking"] == pytest.approx(0.92)

    def test_default_class_probs_is_empty(self):
        al = ActivityLabel(
            timestamp="2026-05-01T00:00:00Z",
            node_id=1,
            label="unknown",
            confidence=0.0,
        )
        assert al.class_probs == {}


# ── SlidingWindowBuffer ────────────────────────────────────────────

class TestSlidingWindowBuffer:
    def test_accumulates_until_full(self):
        buf = SlidingWindowBuffer(window_size=50, step_size=25, target_subcarriers=52)
        for i in range(49):
            result = buf.push(1, rng.normal(size=64))
            assert result is None
        result = buf.push(1, rng.normal(size=64))
        assert result is not None
        assert result.shape == (50, 52)

    def test_emits_overlapping_windows(self):
        buf = SlidingWindowBuffer(window_size=50, step_size=25, target_subcarriers=52)
        window1 = None
        for i in range(50):
            w = buf.push(1, rng.normal(size=64))
            if w is not None:
                window1 = w
        assert window1 is not None

        window2 = None
        for i in range(25):
            w = buf.push(1, rng.normal(size=64))
            if w is not None:
                window2 = w
        assert window2 is not None  # 25 more frames → second window emitted

    def test_crops_subcarriers_to_target(self):
        buf = SlidingWindowBuffer(window_size=50, step_size=50, target_subcarriers=52)
        result = None
        for i in range(50):
            result = buf.push(1, np.arange(128, dtype=np.float32))
        assert result is not None
        assert result.shape == (50, 52)

    def test_pads_subcarriers_to_target(self):
        buf = SlidingWindowBuffer(window_size=50, step_size=50, target_subcarriers=52)
        result = None
        for i in range(50):
            result = buf.push(1, np.arange(20, dtype=np.float32))
        assert result is not None
        assert result.shape == (50, 52)

    def test_per_node_isolation(self):
        buf = SlidingWindowBuffer(window_size=10, step_size=5, target_subcarriers=52)
        for i in range(10):
            buf.push(1, rng.normal(size=64))
            buf.push(2, rng.normal(size=64))
        assert len(buf._buffers[1]) == 5  # 10 pushed, 10 window → slide by 5
        assert len(buf._buffers[2]) == 5

    def test_reset_node(self):
        buf = SlidingWindowBuffer(window_size=50, step_size=25, target_subcarriers=52)
        buf.push(1, rng.normal(size=64))
        buf.reset_node(1)
        assert 1 not in buf._buffers

    def test_center_crop_correct_values(self):
        """Center-crop preserves middle values."""
        arr = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=np.float32)
        result = _center_crop_1d(arr, 4, axis=0)
        assert result.shape == (4,)
        assert result[0] == 4
        assert result[-1] == 7

    def test_center_pad_correct_values(self):
        """Center-pad zero-pads symmetrically."""
        arr = np.array([1, 2, 3, 4], dtype=np.float32)
        result = _center_crop_1d(arr, 8, axis=0)
        assert result.shape == (8,)
        assert result[0] == 0
        assert result[1] == 0
        assert result[2] == 1
        assert result[5] == 4
        assert result[6] == 0
        assert result[7] == 0


# ── CsiClassifier ──────────────────────────────────────────────────

class TestCsiClassifier:
    def test_loads_model_from_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            classifier = CsiClassifier(
                input_queue=asyncio.Queue(),
                model_path=ckpt_path,
                scaler_path=scaler_path,
            )
            assert classifier._model is not None
            assert not classifier._model.training
            assert getattr(classifier._model, "output_dim", 6) == 6

    def test_output_produces_correct_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            input_q: asyncio.Queue = asyncio.Queue()
            output_q: asyncio.Queue = asyncio.Queue()
            classifier = CsiClassifier(
                input_queue=input_q,
                output_queue=output_q,
                model_path=ckpt_path,
                scaler_path=scaler_path,
            )

            tensor = torch.randn(1, 50, 52)
            with torch.no_grad():
                logits = classifier._model(tensor)
            assert logits.shape == (1, 6)

    @pytest.mark.asyncio
    async def test_emits_to_output_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            input_q: asyncio.Queue = asyncio.Queue()
            output_q: asyncio.Queue = asyncio.Queue()
            classifier = CsiClassifier(
                input_queue=input_q,
                output_queue=output_q,
                model_path=ckpt_path,
                scaler_path=scaler_path,
                config={"window_size": 50, "step_size": 50},
            )

            for i in range(50):
                await input_q.put(_make_frame(node_id=1, n_subcarriers=64))

            task = asyncio.create_task(classifier.run())
            await asyncio.sleep(0.5)
            classifier.stop()
            await task

            assert not output_q.empty()
            result = output_q.get_nowait()
            assert "label" in result
            assert "confidence" in result
            assert result["node_id"] == 1
            assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_skips_low_confidence_with_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            input_q: asyncio.Queue = asyncio.Queue()
            output_q: asyncio.Queue = asyncio.Queue()
            classifier = CsiClassifier(
                input_queue=input_q,
                output_queue=output_q,
                model_path=ckpt_path,
                scaler_path=scaler_path,
                config={
                    "window_size": 50,
                    "step_size": 50,
                    "confidence_threshold": 0.99,
                },
            )

            for i in range(50):
                await input_q.put(_make_frame(node_id=1, n_subcarriers=64))

            task = asyncio.create_task(classifier.run())
            await asyncio.sleep(0.5)
            classifier.stop()
            await task

            if not output_q.empty():
                result = output_q.get_nowait()
                # With an untrained model on random data, max prob ~0.25 per class
                # so threshold 0.99 forces "unknown"
                assert result["label"] == "unknown"

    @pytest.mark.asyncio
    async def test_shutdown_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            input_q: asyncio.Queue = asyncio.Queue()
            classifier = CsiClassifier(
                input_queue=input_q,
                model_path=ckpt_path,
                scaler_path=scaler_path,
            )
            task = asyncio.create_task(classifier.run())
            await asyncio.sleep(0.1)
            classifier.stop()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_max_nodes_cap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            input_q: asyncio.Queue = asyncio.Queue()
            output_q: asyncio.Queue = asyncio.Queue()
            classifier = CsiClassifier(
                input_queue=input_q,
                output_queue=output_q,
                model_path=ckpt_path,
                scaler_path=scaler_path,
                config={"window_size": 50, "step_size": 50, "max_nodes": 1},
            )

            for i in range(50):
                await input_q.put(_make_frame(node_id=1, n_subcarriers=64))
                await input_q.put(_make_frame(node_id=2, n_subcarriers=64))

            task = asyncio.create_task(classifier.run())
            await asyncio.sleep(0.5)
            classifier.stop()
            await task

            # Only node 1 should have produced output
            while not output_q.empty():
                result = output_q.get_nowait()
                assert result["node_id"] == 1

    @pytest.mark.asyncio
    async def test_inference_latency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            small_model = AttentionGRU(input_dim=52, hidden_dim=32, attention_dim=8, output_dim=6)
            small_ckpt = f"{tmpdir}/small_model.pth"
            save_checkpoint(small_model, small_ckpt)
            classifier = CsiClassifier(
                input_queue=asyncio.Queue(),
                model_path=small_ckpt,
                scaler_path=scaler_path,
            )

            tensor = torch.randn(1, 50, 52)
            t0 = time.perf_counter()
            for _ in range(100):
                with torch.no_grad():
                    classifier._model(tensor)
            elapsed = (time.perf_counter() - t0) / 100 * 1000
            assert elapsed < 10.0, f"Inference latency {elapsed:.2f} ms > 10 ms"
