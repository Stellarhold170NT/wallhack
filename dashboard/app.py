from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from dashboard.state import DashboardState

logger = logging.getLogger("dashboard.app")


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)
        logger.info("WebSocket client connected (total: %d)", len(self.connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)
        logger.info("WebSocket client disconnected (total: %d)", len(self.connections))

    async def broadcast(self, message: str) -> None:
        closed: list[WebSocket] = []
        for ws in self.connections:
            if ws.client_state != WebSocketState.CONNECTED:
                closed.append(ws)
                continue
            try:
                await ws.send_text(message)
            except RuntimeError:
                closed.append(ws)
            except Exception:
                closed.append(ws)
        for ws in closed:
            if ws in self.connections:
                self.connections.remove(ws)


def create_app(state: DashboardState) -> FastAPI:
    app = FastAPI(title="ESP32-S3 CSI Dashboard")
    manager = ConnectionManager()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup() -> None:
        asyncio.create_task(_broadcaster())

    async def _broadcaster() -> None:
        while True:
            await asyncio.sleep(0.5)
            try:
                status = state.get_status()
                payload = json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "presence": status["presence"],
                        "activity": status["activity"],
                        "alerts": state.get_alerts(10),
                        "node_health": status["node_health"],
                        "heatmap": state.get_heatmap(),
                    },
                    default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o),
                )
                await manager.broadcast(payload)
            except Exception:
                logger.exception("Broadcaster error")

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(websocket)

    @app.get("/status")
    async def get_status() -> dict:
        return state.get_status()

    @app.get("/alerts")
    async def get_alerts(count: int = 50) -> list[dict]:
        return state.get_alerts(count)

    app.mount(
        "/",
        StaticFiles(directory="dashboard/static", html=True),
        name="static",
    )

    return app
