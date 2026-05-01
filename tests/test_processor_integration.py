"""Integration tests for CsiProcessor and offline CLI."""

import asyncio
import tempfile
import numpy as np
import pytest
from aggregator.frame import CSIFrame
from processor.main import CsiProcessor
from processor.__main__ import process_npy


def make_frame(node_id: int, sequence: int, amplitudes: list[float]) -> CSIFrame:
    """Helper to create a CSIFrame."""
    return CSIFrame(
        node_id=node_id,
        sequence=sequence,
        n_subcarriers=len(amplitudes),
        amplitudes=amplitudes,
        phases=[0.0] * len(amplitudes),
    )


class TestCsiProcessorAsync:
    """Asyncio integration tests for CsiProcessor."""

    @pytest.mark.asyncio
    async def test_400_frames_produce_three_feature_vectors(self):
        """400 frames → 3 feature dicts in output queue (at 200, 300, 400)."""
        input_q: asyncio.Queue = asyncio.Queue()
        output_q: asyncio.Queue = asyncio.Queue()
        processor = CsiProcessor(input_q, output_q)

        # Push 400 frames from node 1
        for i in range(400):
            frame = make_frame(1, i, [float(i)] * 64)
            await input_q.put(frame)

        # Run processor briefly
        task = asyncio.create_task(processor.run())
        await asyncio.sleep(0.5)
        processor.stop()
        await task

        # Drain output queue
        vectors = []
        while not output_q.empty():
            vectors.append(output_q.get_nowait())

        assert len(vectors) == 3
        for v in vectors:
            assert v["node_id"] == 1
            assert "features" in v
            assert isinstance(v["features"], np.ndarray)
            assert v["features"].ndim == 1
            assert len(v["features"]) >= 130

    @pytest.mark.asyncio
    async def test_per_node_isolation(self):
        """Alternating node IDs produce separate feature streams."""
        input_q: asyncio.Queue = asyncio.Queue()
        output_q: asyncio.Queue = asyncio.Queue()
        processor = CsiProcessor(input_q, output_q)

        # Push 400 frames alternating node 1 and 2
        for i in range(400):
            node_id = 1 if i % 2 == 0 else 2
            frame = make_frame(node_id, i, [float(i)] * 64)
            await input_q.put(frame)

        task = asyncio.create_task(processor.run())
        await asyncio.sleep(0.5)
        processor.stop()
        await task

        vectors = []
        while not output_q.empty():
            vectors.append(output_q.get_nowait())

        assert len(vectors) >= 2
        node_ids = [v["node_id"] for v in vectors]
        assert 1 in node_ids
        assert 2 in node_ids

    @pytest.mark.asyncio
    async def test_cancellation_handled_gracefully(self):
        """CancelledError is handled without crashing."""
        input_q: asyncio.Queue = asyncio.Queue()
        processor = CsiProcessor(input_q, None)

        task = asyncio.create_task(processor.run())
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

    @pytest.mark.asyncio
    async def test_max_nodes_cap(self):
        """Exceeding max_nodes skips extra nodes."""
        input_q: asyncio.Queue = asyncio.Queue()
        output_q: asyncio.Queue = asyncio.Queue()
        processor = CsiProcessor(input_q, output_q, config={"max_nodes": 2})

        # Push frames from 5 different nodes
        for i in range(100):
            node_id = (i % 5) + 1
            frame = make_frame(node_id, i, [float(i)] * 64)
            await input_q.put(frame)

        task = asyncio.create_task(processor.run())
        await asyncio.sleep(0.5)
        processor.stop()
        await task

        vectors = []
        while not output_q.empty():
            vectors.append(output_q.get_nowait())

        # Only nodes 1 and 2 should have produced vectors
        node_ids = {v["node_id"] for v in vectors}
        assert node_ids.issubset({1, 2})


class TestOfflineCLI:
    """Offline CLI integration tests."""

    def test_process_npy_creates_output(self):
        """CLI processes .npy and creates feature output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = f"{tmpdir}/input.npy"
            output_path = f"{tmpdir}/output.npy"

            # Create synthetic data: 400 frames, 64 subcarriers
            data = np.random.randn(400, 64).astype(np.float64)
            np.save(input_path, data)

            count = process_npy(input_path, output_path)

            assert count == 3  # 400 frames → windows at 200, 300, 400
            assert np.load(output_path, allow_pickle=True) is not None

    def test_process_npy_not_enough_frames(self):
        """Too few frames generates no features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = f"{tmpdir}/input.npy"
            output_path = f"{tmpdir}/output.npy"

            data = np.random.randn(50, 64).astype(np.float64)
            np.save(input_path, data)

            count = process_npy(input_path, output_path)
            assert count == 0

    @pytest.mark.asyncio
    async def test_subcarrier_count_change_resets_window(self):
        """Subcarrier count change mid-stream resets window gracefully."""
        input_q: asyncio.Queue = asyncio.Queue()
        output_q: asyncio.Queue = asyncio.Queue()
        processor = CsiProcessor(input_q, output_q)

        # Push 150 frames with 64 subcarriers (not enough for window)
        for i in range(150):
            frame = make_frame(1, i, [float(i)] * 64)
            await input_q.put(frame)

        # Push 200 frames with 128 subcarriers (different count)
        for i in range(200):
            frame = make_frame(1, i + 150, [float(i)] * 128)
            await input_q.put(frame)

        task = asyncio.create_task(processor.run())
        await asyncio.sleep(0.5)
        processor.stop()
        await task

        vectors = []
        while not output_q.empty():
            vectors.append(output_q.get_nowait())

        # Should get at least 1 vector from the 128-SC stream (200 frames → 1 window)
        assert len(vectors) >= 1
        for v in vectors:
            assert v["node_id"] == 1
            # Feature count = 128*2 + 2 = 258 for 128-SC frames
            assert len(v["features"]) in {130, 258}

    def test_process_npy_invalid_shape(self):
        """1D input raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = f"{tmpdir}/input.npy"
            output_path = f"{tmpdir}/output.npy"

            data = np.random.randn(400)
            np.save(input_path, data)

            with pytest.raises(ValueError, match="Expected 2D array"):
                process_npy(input_path, output_path)
