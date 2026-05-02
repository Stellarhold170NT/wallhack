from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np
import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.state import DashboardState


@dataclass
class MockFrame:
    node_id: int
    amplitudes: np.ndarray


@pytest.mark.asyncio
async def test_dashboard_state_queue_consumption() -> None:
    alert_q: asyncio.Queue = asyncio.Queue()
    activity_q: asyncio.Queue = asyncio.Queue()
    amplitude_q: asyncio.Queue = asyncio.Queue()

    state = DashboardState(
        alert_queue=alert_q,
        activity_queue=activity_q,
        amplitude_queue=amplitude_q,
    )

    task = asyncio.create_task(state.start())
    await asyncio.sleep(0.05)

    await alert_q.put({
        "timestamp": "2024-01-01T00:00:00Z",
        "node_id": 1,
        "status": "occupied",
        "confidence": 0.95,
        "type": "intrusion",
        "trigger_feature": "combined",
    })
    await activity_q.put({
        "timestamp": "2024-01-01T00:00:00Z",
        "node_id": 1,
        "label": "walking",
        "confidence": 0.92,
        "class_probs": {"walking": 0.92, "running": 0.08},
    })
    await amplitude_q.put(MockFrame(node_id=1, amplitudes=np.array([0.1, 0.2, 0.3])))

    await asyncio.sleep(0.1)

    status = state.get_status()
    assert status["presence"].get(1) == "occupied"
    assert status["activity"].get(1, {}).get("label") == "walking"

    alerts = state.get_alerts(50)
    assert len(alerts) >= 1
    assert alerts[0]["type"] == "intrusion"

    heatmap = state.get_heatmap()
    assert 1 in heatmap
    assert len(heatmap[1]) >= 1

    state.stop()
    await asyncio.wait_for(task, timeout=1.0)


def test_status_endpoint() -> None:
    state = DashboardState(
        alert_queue=asyncio.Queue(),
        activity_queue=asyncio.Queue(),
        amplitude_queue=asyncio.Queue(),
    )
    app = create_app(state)
    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "presence" in data
    assert "activity" in data
    assert "node_health" in data


@pytest.mark.asyncio
async def test_alerts_endpoint() -> None:
    alert_q: asyncio.Queue = asyncio.Queue()
    state = DashboardState(
        alert_queue=alert_q,
        activity_queue=asyncio.Queue(),
        amplitude_queue=asyncio.Queue(),
    )

    task = asyncio.create_task(state.start())
    await asyncio.sleep(0.05)

    for i in range(3):
        await alert_q.put({
            "timestamp": f"2024-01-01T00:00:0{i}Z",
            "node_id": 1,
            "status": "occupied",
            "confidence": 0.9,
            "type": "intrusion",
            "trigger_feature": "combined",
        })

    await asyncio.sleep(0.1)

    app = create_app(state)
    client = TestClient(app)
    response = client.get("/alerts?count=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2
    assert "timestamp" in data[0]

    state.stop()
    await asyncio.wait_for(task, timeout=1.0)


def test_websocket_endpoint() -> None:
    state = DashboardState(
        alert_queue=asyncio.Queue(),
        activity_queue=asyncio.Queue(),
        amplitude_queue=asyncio.Queue(),
    )
    app = create_app(state)
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert "presence" in data
        assert "activity" in data
        assert "alerts" in data
        assert "heatmap" in data
        assert "node_health" in data
