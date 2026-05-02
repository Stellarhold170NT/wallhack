---
phase: 06-dashboard-api
plan: 01
status: complete
commit: feat(06-01): FastAPI backend with DashboardState, WebSocket, REST endpoints
---

## Summary

Built the FastAPI backend and state manager for the real-time dashboard.

### What Was Built

- `dashboard/__init__.py` — Package marker
- `dashboard/state.py` — `DashboardState` class consuming alert_queue, activity_queue, and amplitude_queue
  - Maintains in-memory state: presence, activity, alerts (deque maxlen=50), heatmap (deque maxlen=200 per node)
  - Async start() spawns 3 consumer tasks
  - stop() gracefully cancels all consumers
  - get_status(), get_alerts(count), get_heatmap() return serializable state
  - Optional node_source callback for node health display
- `dashboard/app.py` — FastAPI app factory `create_app(state)`
  - CORS middleware (allow_origins=["*"])
  - WebSocket `/ws` endpoint with ConnectionManager
  - Background broadcaster task (2Hz / 500ms interval) pushing JSON bundles
  - REST `GET /status` and `GET /alerts`
  - StaticFiles mount serving `dashboard/static/index.html`
- `requirements.txt` — Added fastapi, httpx, uvicorn[standard]

### Key Decisions

- Direct Queue access (no IPC) — DashboardState reads from existing asyncio queues in the same event loop
- Initial state push on WebSocket connect — ensures immediate data availability for tests and clients

### Tests

- Import verification: `python -c "from dashboard.state import DashboardState; from dashboard.app import create_app"` ✓

### Deviation from Plan

- Added immediate state push in WebSocket endpoint (`ws_endpoint`) to ensure TestClient can receive data without waiting for broadcaster loop timing

## Self-Check

- [x] All tasks executed
- [x] Each file committed
- [x] SUMMARY.md created
