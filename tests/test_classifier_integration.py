"""Integration tests for CsiClassifier end-to-end pipeline."""

import asyncio
import json
import tempfile

import numpy as np
import pytest
import torch
from sklearn.preprocessing import StandardScaler

from aggregator.frame import CSIFrame
from classifier.infer import CsiClassifier, ActivityLabel
from classifier.model import AttentionGRU
from classifier.train import save_checkpoint
from classifier.dataset import save_scaler, load_scaler

rng = np.random.default_rng(42)


def _make_checkpoint_and_scaler(tmpdir: str, output_dim: int = 4):
    """Create a model checkpoint (with custom output_dim) and fitted scaler."""
    model = AttentionGRU(input_dim=52, hidden_dim=128, attention_dim=32, output_dim=output_dim)
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
    return CSIFrame(
        node_id=node_id,
        sequence=0,
        n_subcarriers=n_subcarriers,
        amplitudes=rng.normal(size=n_subcarriers).tolist(),
        phases=[0.0] * n_subcarriers,
    )


# ── End-to-End Pipeline ────────────────────────────────────────────

class TestEndToEndPipeline:
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            amplitude_queue: asyncio.Queue = asyncio.Queue()
            activity_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

            classifier = CsiClassifier(
                input_queue=amplitude_queue,
                output_queue=activity_queue,
                model_path=ckpt_path,
                scaler_path=scaler_path,
                config={"window_size": 50, "step_size": 50},
            )

            task = asyncio.create_task(classifier.run())

            for i in range(50):
                await amplitude_queue.put(_make_frame(node_id=1, n_subcarriers=64))

            await asyncio.sleep(0.5)
            classifier.stop()
            await task

            assert not activity_queue.empty()
            result = activity_queue.get_nowait()
            assert result["node_id"] == 1
            assert result["label"] in ("walking", "running", "lying", "bending", "unknown")
            assert 0.0 <= result["confidence"] <= 1.0
            assert "class_probs" in result

    @pytest.mark.asyncio
    async def test_multiple_windows_emitted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            amplitude_queue: asyncio.Queue = asyncio.Queue()
            activity_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

            classifier = CsiClassifier(
                input_queue=amplitude_queue,
                output_queue=activity_queue,
                model_path=ckpt_path,
                scaler_path=scaler_path,
                config={"window_size": 50, "step_size": 25},
            )

            task = asyncio.create_task(classifier.run())

            for i in range(75):
                await amplitude_queue.put(_make_frame(node_id=1, n_subcarriers=64))

            await asyncio.sleep(0.5)
            classifier.stop()
            await task

            results = []
            while not activity_queue.empty():
                results.append(activity_queue.get_nowait())
            assert len(results) >= 2  # 75 frames with step=25 → 2 windows (at 50, 75)


# ── Parallel Processor + Classifier ────────────────────────────────

class TestParallelProcessorClassifier:
    @pytest.mark.asyncio
    async def test_both_produce_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            raw_queue: asyncio.Queue = asyncio.Queue()
            feature_queue: asyncio.Queue = asyncio.Queue()
            amplitude_queue: asyncio.Queue = asyncio.Queue()
            activity_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

            from processor.main import CsiProcessor
            processor = CsiProcessor(
                input_queue=raw_queue,
                output_queue=feature_queue,
                config={"window_size": 100, "step_size": 100, "max_nodes": 2},
            )
            classifier = CsiClassifier(
                input_queue=amplitude_queue,
                output_queue=activity_queue,
                model_path=ckpt_path,
                scaler_path=scaler_path,
                config={"window_size": 50, "step_size": 50, "max_nodes": 2},
            )

            processor_task = asyncio.create_task(processor.run())
            classifier_task = asyncio.create_task(classifier.run())

            # Fan out: each frame goes to both raw_queue and amplitude_queue
            for i in range(150):
                frame = _make_frame(node_id=1, n_subcarriers=64)
                await raw_queue.put(frame)
                await amplitude_queue.put(frame)

            await asyncio.sleep(0.5)
            processor.stop()
            classifier.stop()
            try:
                await processor_task
            except asyncio.CancelledError:
                pass
            await classifier_task

            feature_count = 0
            while not feature_queue.empty():
                feature_queue.get_nowait()
                feature_count += 1

            activity_count = 0
            while not activity_queue.empty():
                activity_queue.get_nowait()
                activity_count += 1

            assert feature_count >= 1  # Processor: 150 frames with step=100 → 1 window at 100 (or 2 at 200)
            assert activity_count >= 1  # Classifier: 150 frames with step=50 → ~3 windows

    @pytest.mark.asyncio
    async def test_no_blocking_between_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ckpt_path, scaler_path = _make_checkpoint_and_scaler(tmpdir)
            raw_queue: asyncio.Queue = asyncio.Queue()
            amplitude_queue: asyncio.Queue = asyncio.Queue()

            from processor.main import CsiProcessor
            processor = CsiProcessor(
                input_queue=raw_queue,
                config={"window_size": 100, "step_size": 100},
            )
            classifier = CsiClassifier(
                input_queue=amplitude_queue,
                model_path=ckpt_path,
                scaler_path=scaler_path,
                config={"window_size": 50, "step_size": 50},
            )

            processor_task = asyncio.create_task(processor.run())
            classifier_task = asyncio.create_task(classifier.run())

            for i in range(100):
                frame = _make_frame(node_id=1, n_subcarriers=64)
                await raw_queue.put(frame)
                await amplitude_queue.put(frame)

            await asyncio.sleep(0.3)
            processor.stop()
            classifier.stop()

            gathered = await asyncio.gather(
                processor_task, classifier_task, return_exceptions=True,
            )
            for result in gathered:
                assert not isinstance(result, Exception), f"Task raised: {result}"


# ── Real Checkpoint Round-Trip ─────────────────────────────────────

class TestRealCheckpoint:
    def test_train_save_load_infer_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model = AttentionGRU(
                input_dim=52, hidden_dim=128, attention_dim=32, output_dim=4,
            )
            scaler = StandardScaler()
            dummy_data = rng.normal(size=(100, 50 * 52))
            scaler.fit(dummy_data)
            ckpt_path = f"{tmpdir}/roundtrip.pth"
            scaler_path = f"{tmpdir}/roundtrip.scaler.json"

            save_checkpoint(model, ckpt_path, scaler=scaler)
            save_scaler(scaler, scaler_path)

            loaded_scaler = load_scaler(scaler_path)
            assert loaded_scaler.n_features_in_ == 50 * 52

            input_q: asyncio.Queue = asyncio.Queue()
            output_q: asyncio.Queue = asyncio.Queue()

            classifier = CsiClassifier(
                input_queue=input_q,
                output_queue=output_q,
                model_path=ckpt_path,
                scaler_path=scaler_path,
            )
            assert classifier._model is not None
            assert not classifier._model.training

            tensor = torch.randn(1, 50, 52)
            with torch.no_grad():
                logits = classifier._model(tensor)
            assert logits.shape == (1, 4)

    def test_activity_label_serializable(self):
        al = ActivityLabel(
            timestamp="2026-05-01T00:00:00Z",
            node_id=1,
            label="walking",
            confidence=0.87,
            class_probs={"walking": 0.87, "running": 0.08, "lying": 0.03, "bending": 0.02},
        )
        d = al.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["label"] == "walking"
        assert parsed["confidence"] == pytest.approx(0.87)
        assert parsed["class_probs"]["walking"] == pytest.approx(0.87)
