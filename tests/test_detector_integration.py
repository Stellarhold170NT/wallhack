"""End-to-end integration tests for the full detection pipeline."""

import asyncio

import numpy as np
import pytest

from aggregator.frame import CSIFrame
from detector.fusion import FusionMode
from detector.main import CsiDetector
from processor.main import CsiProcessor


def make_frame(
    node_id: int, sequence: int, amplitudes: list[float]
) -> CSIFrame:
    return CSIFrame(
        node_id=node_id,
        sequence=sequence,
        n_subcarriers=len(amplitudes),
        amplitudes=amplitudes,
        phases=[0.0] * len(amplitudes),
    )


def make_constant_frames(
    node_id: int, count: int, amplitude: float, n_subcarriers: int = 64, start_seq: int = 0
):
    return [
        make_frame(node_id, start_seq + i, [amplitude] * n_subcarriers)
        for i in range(count)
    ]


def make_motion_frames(
    node_id: int, start_seq: int, count: int, n_subcarriers: int = 64
):
    frames = []
    for i in range(count):
        amp = 10.0 + np.sin(i * 0.5) * 5.0
        frames.append(make_frame(node_id, start_seq + i, [float(amp)] * n_subcarriers))
    return frames


PROC_CONFIG = {"window_size": 20, "step_size": 10}


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_empty_room_no_alerts(self):
        raw_q = asyncio.Queue()
        feature_q = asyncio.Queue()
        alert_q = asyncio.Queue(maxsize=100)
        processor = CsiProcessor(
            input_queue=raw_q, output_queue=feature_q, config=PROC_CONFIG
        )
        detector = CsiDetector(
            input_queue=feature_q, output_queue=alert_q
        )
        proc_task = asyncio.create_task(processor.run())
        det_task = asyncio.create_task(detector.run())
        for frame in make_constant_frames(0, 300, 1.0):
            raw_q.put_nowait(frame)
        await asyncio.sleep(0.5)
        detector.stop()
        processor.stop()
        await det_task
        await proc_task
        assert alert_q.qsize() == 0

    @pytest.mark.asyncio
    async def test_motion_triggers_intrusion_alert(self):
        raw_q = asyncio.Queue()
        feature_q = asyncio.Queue()
        alert_q = asyncio.Queue(maxsize=100)
        processor = CsiProcessor(
            input_queue=raw_q, output_queue=feature_q, config=PROC_CONFIG
        )
        detector = CsiDetector(
            input_queue=feature_q, output_queue=alert_q
        )
        proc_task = asyncio.create_task(processor.run())
        det_task = asyncio.create_task(detector.run())
        for frame in make_constant_frames(0, 300, 1.0):
            raw_q.put_nowait(frame)
        for frame in make_motion_frames(0, 300, 300):
            raw_q.put_nowait(frame)
        await asyncio.sleep(1.0)
        detector.stop()
        processor.stop()
        await det_task
        await proc_task
        assert alert_q.qsize() >= 1
        alerts = [alert_q.get_nowait() for _ in range(alert_q.qsize())]
        intrusion_alerts = [a for a in alerts if a["type"] == "intrusion"]
        assert len(intrusion_alerts) >= 1
        assert "timestamp" in intrusion_alerts[0]
        assert "confidence" in intrusion_alerts[0]

    @pytest.mark.asyncio
    async def test_two_node_fusion_or_mode(self):
        raw_q = asyncio.Queue()
        feature_q = asyncio.Queue()
        alert_q = asyncio.Queue(maxsize=100)
        processor = CsiProcessor(
            input_queue=raw_q, output_queue=feature_q, config=PROC_CONFIG
        )
        detector = CsiDetector(
            input_queue=feature_q,
            output_queue=alert_q,
            config={"fusion_mode": "or"},
        )
        proc_task = asyncio.create_task(processor.run())
        det_task = asyncio.create_task(detector.run())
        for frame in make_constant_frames(0, 300, 1.0):
            raw_q.put_nowait(frame)
        for frame in make_constant_frames(1, 300, 1.0):
            raw_q.put_nowait(frame)
        for frame in make_motion_frames(0, 300, 300):
            raw_q.put_nowait(frame)
        for frame in make_constant_frames(1, 300, 1.0, start_seq=300):
            raw_q.put_nowait(frame)
        await asyncio.sleep(1.0)
        detector.stop()
        processor.stop()
        await det_task
        await proc_task
        fused = detector.fusion.fuse()
        assert fused["status"] == "occupied"
        assert fused["fusion_mode"] == "or"

    @pytest.mark.asyncio
    async def test_stale_node_exclusion(self):
        from dataclasses import dataclass

        @dataclass
        class FakeNode:
            stale: bool = False

        nodes = {0: FakeNode(stale=False), 1: FakeNode(stale=True)}
        raw_q = asyncio.Queue()
        feature_q = asyncio.Queue()
        alert_q = asyncio.Queue(maxsize=100)
        processor = CsiProcessor(
            input_queue=raw_q, output_queue=feature_q, config=PROC_CONFIG
        )
        detector = CsiDetector(
            input_queue=feature_q,
            output_queue=alert_q,
            node_health_source=nodes,
        )
        proc_task = asyncio.create_task(processor.run())
        det_task = asyncio.create_task(detector.run())
        for frame in make_constant_frames(0, 300, 1.0):
            raw_q.put_nowait(frame)
        for frame in make_constant_frames(1, 300, 1.0):
            raw_q.put_nowait(frame)
        for frame in make_motion_frames(0, 300, 300):
            raw_q.put_nowait(frame)
        for frame in make_constant_frames(1, 300, 1.0, start_seq=300):
            raw_q.put_nowait(frame)
        await asyncio.sleep(1.0)
        detector.stop()
        processor.stop()
        await det_task
        await proc_task
        fused = detector.fusion.fuse()
        assert fused["status"] == "occupied"

    @pytest.mark.asyncio
    async def test_alert_queue_bounded(self):
        alert_q = asyncio.Queue(maxsize=5)
        for i in range(10):
            try:
                alert_q.put_nowait({"id": i})
            except asyncio.QueueFull:
                break
        assert alert_q.qsize() == 5
