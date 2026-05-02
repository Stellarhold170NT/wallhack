# Phase 6: Dashboard & API - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 06-dashboard-api
**Areas discussed:** Web server integration, Frontend stack, Real-time transport, Dashboard layout, Heatmap visualization, REST API, Extra panels

---

## Web Server Integration

| Option | Description | Selected |
|--------|-------------|----------|
| FastAPI embedded | Shares asyncio event loop, direct Queue access, add uvicorn dep | ✓ |
| Separate Flask process | Lighter but needs IPC/HTTP bridge, blocks event loop | |
| Let the agent decide | — | |

**User's choice:** FastAPI embedded in aggregator process (Tích hợp trực tiếp)
**Notes:** User wants FastAPI "nhúng" directly in aggregator to share the asyncio event loop and access Queues without intermediate bridge. Port chosen: 8024. Activated via `--dashboard` flag to keep headless mode lean.

---

## Frontend Stack

| Option | Description | Selected |
|--------|-------------|----------|
| Vanilla JS + Canvas 2D | Zero deps, fast 0.5s heatmap redraws, lightweight | ✓ |
| Chart.js / D3.js | Easier charting but adds JS dependency | |
| Let the agent decide | — | |

**User's choice:** Vanilla JS + Canvas 2D (Nhẹ như lông hồng)
**Notes:** User explicitly wants zero frontend framework dependencies. Canvas 2D for heatmap rendering. Page should load instantly ("0.5s"). Single HTML file with inline CSS and JS.

---

## Real-time Transport

| Option | Description | Selected |
|--------|-------------|----------|
| WebSocket | Bidirectional, requirements specify WS at 2Hz | ✓ |
| Server-Sent Events | Unidirectional, simpler Python impl, auto-reconnect | |
| Let the agent decide | — | |

**User's choice:** WebSocket (WS) at fixed 2Hz interval
**Notes:** User considers WebSocket the "tiêu chuẩn vàng" (gold standard) for real-time dashboards. Fixed 500ms push interval chosen for predictable, smooth updates. Server pushes JSON bundle with all panel data each tick.

---

## Dashboard Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single-page 4-panel grid | Heatmap, presence, activity, alerts — command center view | ✓ |
| Tabbed/mobile-first | Simplified views, larger touch targets | |
| Let the agent decide | — | |

**User's choice:** Single-page 5-panel grid (4 main + node health)
**Notes:** User wants a "Trung tâm điều khiển" (command center). Layout:
- Top-left: Heatmap / real-time CSI wave chart
- Top-right: Presence status (Occupied/Empty)
- Bottom-left: Activity label (SITTING, WALKING, etc.)
- Bottom-right: Alert logs (e.g., "Phát hiện té ngã lúc 14:20")
- Extra: Node health panel (FPS, stale status) added by user request

---

## Heatmap Visualization

| Option | Description | Selected |
|--------|-------------|----------|
| Subcarrier vs Time, blue→red | Classic spectrum analyzer, 52 subcarriers Y-axis | ✓ |
| Subcarrier vs Time, black→white→red | Medical imaging style, higher contrast | |
| Let the agent decide | — | |

**User's choice:** Subcarrier (Y) vs Time (X), blue→red
**Notes:** User specified axes: "subcarrier theo chiều dọc, thờI gian theo chiều ngang, màu xanh→đỏ". Classic spectrum analyzer color scale.

---

## REST API

| Option | Description | Selected |
|--------|-------------|----------|
| Both REST + WebSocket | /status and /alerts endpoints alongside WS | ✓ |
| WebSocket only | Skip REST, all data over WS | |
| Let the agent decide | — | |

**User's choice:** Both REST endpoints + WebSocket
**Notes:** Requirements explicitly require GET /status and GET /alerts. REST endpoints read from same in-memory state as WebSocket. No separate discussion question needed — implicit from requirements.

---

## Extra Panels

| Option | Description | Selected |
|--------|-------------|----------|
| Node health panel | FPS per node, stale/connected status | ✓ |
| System latency panel | Inference latency, processing delay | |
| Just the 4 panels | Keep it simple | |
| Let the agent decide | — | |

**User's choice:** Node health panel (FPS, stale status)
**Notes:** User wants to see per-node frame rate and connection health alongside the 4 main panels.

---

## the agent's Discretion

- Exact CSS styling, colors, and typography
- WebSocket reconnection logic (auto-reconnect with backoff)
- Alert panel formatting (timestamp locale, max visible entries, scroll behavior)
- Heatmap time window duration (seconds of history to display)
- Node health panel layout and refresh rate
- Whether to add a "pause updates" button
- Error state display (disconnected WebSocket, no data from nodes)

## Deferred Ideas

- Mobile-responsive redesign — v1.1
- Dark/light theme toggle — v1.1
- Alert sound/notification — v1.1
- Historical data replay (scrubber) — v2
- Multi-dashboard (per-node view) — v2
- Authentication on dashboard — v2
- Config panel in UI (live threshold adjustment) — v2

---

*Log written: 2026-05-02*
