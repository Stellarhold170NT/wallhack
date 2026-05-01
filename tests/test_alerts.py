"""Tests for detector/alerts.py and detector/main.py."""

import asyncio
from dataclasses import dataclass

import numpy as np
import pytest

from detector.alerts import Alert, AlertManager
from detector.main import CsiDetector


def make_feature_dict(
    node_id: int, motion: float, breathing: float, n_subcarriers: int = 64
) -> dict:
    N = n_subcarriers
    fv = np.zeros(N * 2 + 2, dtype=np.float64)
    fv[2 * N] = motion
    fv[2 * N + 1] = breathing
    return {
        "node_id": node_id,
        "window_start_ms": 0,
        "window_end_ms": 0,
        "features": fv,
    }


class TestAlertManager:
    @pytest.mark.asyncio
    async def test_intrusion_alert_emitted(self, tmp_path):
        mgr = AlertManager(log_dir=str(tmp_path))
        alert = Alert(
            timestamp="2024-01-01T00:00:00Z",
            node_id=1,
            status="occupied",
            confidence=0.95,
            type="intrusion",
            trigger_feature="combined",
        )
        assert await mgr.emit(alert)

    @pytest.mark.asyncio
    async def test_cooldown_blocks_second_intrusion(self, tmp_path):
        mgr = AlertManager(cooldown_seconds=5.0, log_dir=str(tmp_path))
        alert = Alert(
            timestamp="2024-01-01T00:00:00Z",
            node_id=1,
            status="occupied",
            confidence=0.95,
            type="intrusion",
            trigger_feature="combined",
        )
        assert await mgr.emit(alert)
        assert not await mgr.emit(alert)

    @pytest.mark.asyncio
    async def test_cooldown_allows_after_interval(self, tmp_path):
        mgr = AlertManager(cooldown_seconds=0.1, log_dir=str(tmp_path))
        alert = Alert(
            timestamp="2024-01-01T00:00:00Z",
            node_id=1,
            status="occupied",
            confidence=0.95,
            type="intrusion",
            trigger_feature="combined",
        )
        assert await mgr.emit(alert)
        await asyncio.sleep(0.15)
        assert await mgr.emit(alert)

    @pytest.mark.asyncio
    async def test_clear_alert_bypasses_cooldown(self, tmp_path):
        mgr = AlertManager(cooldown_seconds=5.0, log_dir=str(tmp_path))
        intrusion = Alert(
            timestamp="2024-01-01T00:00:00Z",
            node_id=1,
            status="occupied",
            confidence=0.95,
            type="intrusion",
            trigger_feature="combined",
        )
        clear = Alert(
            timestamp="2024-01-01T00:00:01Z",
            node_id=1,
            status="empty",
            confidence=0.2,
            type="clear",
            trigger_feature="combined",
        )
        assert await mgr.emit(intrusion)
        assert await mgr.emit(clear)

    @pytest.mark.asyncio
    async def test_jsonl_file_created(self, tmp_path):
        mgr = AlertManager(log_dir=str(tmp_path))
        alert = Alert(
            timestamp="2024-01-01T00:00:00Z",
            node_id=1,
            status="occupied",
            confidence=0.95,
            type="intrusion",
            trigger_feature="combined",
        )
        await mgr.emit(alert)
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].suffix == ".jsonl"

    @pytest.mark.asyncio
    async def test_jsonl_append(self, tmp_path):
        mgr = AlertManager(cooldown_seconds=0.0, log_dir=str(tmp_path))
        for i in range(3):
            alert = Alert(
                timestamp=f"2024-01-01T00:00:0{i}Z",
                node_id=1,
                status="occupied",
                confidence=0.95,
                type="intrusion",
                trigger_feature="combined",
            )
            await mgr.emit(alert)
        files = list(tmp_path.iterdir())
        lines = files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3

    @pytest.mark.asyncio
    async def test_buffer_drop_oldest(self, tmp_path):
        mgr = AlertManager(
            cooldown_seconds=0.0, buffer_size=5, log_dir=str(tmp_path)
        )
        for i in range(7):
            alert = Alert(
                timestamp=f"2024-01-01T00:00:0{i}Z",
                node_id=1,
                status="occupied",
                confidence=0.95,
                type="intrusion",
                trigger_feature="combined",
            )
            await mgr.emit(alert)
        assert mgr.get_buffer_size() == 5

    @pytest.mark.asyncio
    async def test_get_recent_returns_newest_first(self, tmp_path):
        mgr = AlertManager(
            cooldown_seconds=0.0, buffer_size=10, log_dir=str(tmp_path)
        )
        for i in range(3):
            alert = Alert(
                timestamp=f"2024-01-01T00:00:0{i}Z",
                node_id=1,
                status="occupied",
                confidence=0.95,
                type="intrusion",
                trigger_feature="combined",
            )
            await mgr.emit(alert)
        recent = mgr.get_recent(2)
        assert len(recent) == 2
        assert recent[0]["timestamp"] == "2024-01-01T00:00:02Z"

    @pytest.mark.asyncio
    async def test_heartbeat_emitted_periodically(self, tmp_path):
        mgr = AlertManager(
            heartbeat_interval=0.1, log_dir=str(tmp_path)
        )
        assert await mgr.maybe_heartbeat(0, "empty", 0.5)
        assert not await mgr.maybe_heartbeat(0, "empty", 0.5)
        await asyncio.sleep(0.15)
        assert await mgr.maybe_heartbeat(0, "empty", 0.5)


class TestCsiDetector:
    @pytest.mark.asyncio
    async def test_detector_consumes_features(self):
        in_q = asyncio.Queue()
        out_q = asyncio.Queue()
        det = CsiDetector(input_queue=in_q, output_queue=out_q)
        task = asyncio.create_task(det.run())
        for i in range(10):
            in_q.put_nowait(make_feature_dict(0, 1.0, 1.0))
        await asyncio.sleep(0.1)
        det.stop()
        await task

    @pytest.mark.asyncio
    async def test_state_transition_emits_alert(self):
        in_q = asyncio.Queue()
        out_q = asyncio.Queue()
        det = CsiDetector(input_queue=in_q, output_queue=out_q)
        task = asyncio.create_task(det.run())
        for _ in range(10):
            in_q.put_nowait(make_feature_dict(0, 1.0, 1.0))
        for _ in range(3):
            in_q.put_nowait(make_feature_dict(0, 50.0, 50.0))
        await asyncio.sleep(0.2)
        det.stop()
        await task
        assert out_q.qsize() >= 1

    @pytest.mark.asyncio
    async def test_stale_sync_excludes_node(self):
        @dataclass
        class FakeNode:
            stale: bool = False

        nodes = {0: FakeNode(stale=False), 1: FakeNode(stale=True)}
        in_q = asyncio.Queue()
        det = CsiDetector(
            input_queue=in_q,
            node_health_source=nodes,
        )
        task = asyncio.create_task(det.run())
        for _ in range(10):
            in_q.put_nowait(make_feature_dict(0, 1.0, 1.0))
            in_q.put_nowait(make_feature_dict(1, 50.0, 50.0))
        await asyncio.sleep(0.1)
        det.stop()
        await task
        assert det.fusion._node_stale.get(1, False)

    @pytest.mark.asyncio
    async def test_graceful_cancellation(self):
        in_q = asyncio.Queue()
        det = CsiDetector(input_queue=in_q)
        task = asyncio.create_task(det.run())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.done()

    @pytest.mark.asyncio
    async def test_max_nodes_cap(self):
        in_q = asyncio.Queue()
        det = CsiDetector(input_queue=in_q, config={"max_nodes": 2})
        task = asyncio.create_task(det.run())
        for i in range(5):
            in_q.put_nowait(make_feature_dict(i, 1.0, 1.0))
        await asyncio.sleep(0.1)
        det.stop()
        await task
        assert len(det.fusion._detectors) == 2
