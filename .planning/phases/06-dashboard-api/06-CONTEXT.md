# Phase 6: Dashboard & API - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Real-time web dashboard visualizing CSI amplitude heatmap, presence state, activity labels, and intrusion alerts. Serves at `http://localhost:8024` when enabled.

**Phase boundary:**
- IN: Presence state + alert stream from Phase 4 (alert_queue), activity labels from Phase 5 (activity_queue), raw CSI frames from Phase 2 (amplitude_queue)
- OUT: Complete web UI serving all sensing outputs via browser

**Requirements:** UI-01, UI-02, UI-03, UI-04, UI-05, API-01, API-02

</domain>

<decisions>
## Implementation Decisions

### Web Server Architecture
- **D-44:** FastAPI embedded in aggregator process, port 8024
  - FastAPI app runs in the same asyncio event loop as the aggregator (native async, no thread blocking)
  - Activated via `--dashboard` CLI flag: `python -m aggregator --dashboard`
  - When flag absent, no web server overhead — headless operation unchanged
  - Direct Queue access: dashboard task reads from alert_queue, activity_queue, and amplitude_queue without IPC overhead
  - Static files served from `dashboard/` directory via FastAPI `StaticFiles`

### Frontend Stack
- **D-45:** Vanilla HTML/JS + Canvas 2D, zero frontend dependencies
  - No React, Vue, Chart.js, or D3.js — keeps project lightweight and load instantaneous
  - Canvas 2D API for heatmap rendering (0.5s updates, smooth redraw)
  - Single `index.html` with inline CSS and `<script>` tags
  - All assets self-contained in `dashboard/` directory

### Real-time Transport
- **D-46:** WebSocket at fixed 2Hz interval (every 500ms)
  - Server pushes JSON bundle containing: heatmap slice, presence state, activity label + confidence, recent alerts, node health
  - Fixed interval keeps implementation simple and predictable
  - Client receives one message per tick with all panel data
  - WebSocket endpoint: `/ws`

### Dashboard Layout
- **D-47:** Single-page 5-panel grid layout
  - Panel 1 (top-left): CSI amplitude heatmap
  - Panel 2 (top-right): Presence status indicator (green=empty, red=occupied)
  - Panel 3 (bottom-left): Activity label with confidence bar
  - Panel 4 (bottom-right): Alert log panel (intrusion events with timestamp + node ID)
  - Panel 5 (inline/sidebar): Node health (FPS per node, stale/connected status)
  - Responsive CSS grid with min-width for each panel

### Heatmap Visualization
- **D-48:** Subcarrier (Y-axis, 52 rows) vs Time (X-axis, last N seconds)
  - Color scale: blue (low amplitude) → green → yellow → red (high amplitude)
  - Canvas 2D `fillRect` per cell for performance
  - Time window: agent discretion (suggest 10-20 seconds of history)
  - Updates every 0.5s as new CSI frames arrive

### REST API
- **D-50:** Two REST endpoints alongside WebSocket
  - `GET /status` → JSON with current presence, activity, node health (API-01)
  - `GET /alerts` → last 50 alerts as JSON array (API-02)
  - Both endpoints read from in-memory state (same data structures feeding WebSocket)

### the agent's Discretion
- Exact CSS styling, colors, and typography
- WebSocket reconnection logic (auto-reconnect with backoff)
- Alert panel formatting (timestamp locale, max visible entries, scroll behavior)
- Heatmap time window duration (how many seconds of history to display)
- Node health panel layout and refresh rate
- Whether to add a "pause updates" button for the user
- Error state display (disconnected WebSocket, no data from nodes)

</decisions>

<specifics>
## Specific Ideas

- "FastAPI nhúng trực tiếp trong aggregator, dùng chung event loop" — direct Queue access, no IPC
- "Vanilla JS + Canvas 2D để nhẹ như lông hồng" — zero frontend dependencies, instant load
- "WebSocket 2Hz làm dashboard sống động" — fixed 500ms push for smooth real-time feel
- "4 ô chính + node health" — command center layout
- Heatmap: "subcarrier theo chiều dọc, thờI gian theo chiều ngang, màu xanh→đỏ" — classic spectrum analyzer look
- Dashboard activated by `--dashboard` flag to keep headless mode lean

</specifics>

<canonical_refs>
## Canonical References

### Requirements
- `.planning/REQUIREMENTS.md` — UI-01..UI-05, API-01..API-02
- `.planning/ROADMAP.md` — Phase 6 goal, success criteria, anti-features (no cloud, no mobile app)

### Prior Phase Contexts
- `.planning/phases/04-presence-intrusion/04-CONTEXT.md` — D-29 (alert_queue handoff), D-28 (Alert object structure: timestamp, node_id, status, confidence, type, trigger_feature)
- `.planning/phases/05-activity-recognition/05-CONTEXT.md` — D-39 (activity_queue handoff, parallel inference), ActivityLabel.to_dict() format
- `.planning/phases/03-signal-processing/03-CONTEXT.md` — D-16 (feature dict format), D-19 (subcarrier adaptation, dynamic 64/128/192)

### Existing Code
- `aggregator/main.py` — asyncio event loop, Queue wiring (raw_queue, feature_queue, alert_queue, amplitude_queue, activity_queue), graceful shutdown
- `detector/main.py` — CsiDetector alert emission pattern, Alert object structure
- `classifier/infer.py` — CsiClassifier output format (ActivityLabel.to_dict with label, confidence, class_probs)
- `aggregator/server.py` — NodeState.stale flag, per-node frame rate tracking

### External References
- `llm-wiki/raw/RuView/docs/adr/ADR-019-sensing-only-ui-mode.md` — sensing UI patterns (referenced in ROADMAP)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aggregator/main.py:run_server()` — asyncio event loop where dashboard task will be created alongside existing tasks (consumer, processor, detector, classifier)
- `aggregator/main.py:alert_queue` — `asyncio.Queue(maxsize=100)` already created, feeds alerts from CsiDetector
- `aggregator/main.py:activity_queue` — `asyncio.Queue(maxsize=100)` already created, feeds activity labels from CsiClassifier
- `aggregator/main.py:amplitude_queue` — `asyncio.Queue()` already created, feeds raw CSI frames for heatmap
- `detector/alerts.py:Alert.to_dict()` — structured alert output with timestamp, node_id, status, confidence, type, trigger_feature
- `classifier/infer.py:ActivityLabel.to_dict()` — structured activity output with timestamp, node_id, label, confidence, class_probs
- `aggregator/server.py:NodeState` — has `.stale`, `.last_seen`, `.frame_count` for node health display

### Established Patterns
- Asyncio task pattern: dashboard will run as `asyncio.create_task(dashboard.run())` in same event loop
- Queue-based producer/consumer: dashboard consumes from alert_queue, activity_queue, amplitude_queue
- Config dict passthrough: use `--dashboard-config` JSON string for dashboard settings (port, update_rate, etc.)
- Graceful shutdown: dashboard task cancelled in shutdown() alongside processor, detector, classifier
- `logging` module for all diagnostics

### Integration Points
- Phase 4 → Phase 6: `alert_queue` (existing) — dashboard task reads alerts for panel + REST API
- Phase 5 → Phase 6: `activity_queue` (existing) — dashboard task reads activity labels
- Phase 2 → Phase 6: `amplitude_queue` (existing) — dashboard task reads raw frames for heatmap
- Dashboard task created in `aggregator/main.py:run_server()` alongside other tasks
- FastAPI `app` instantiated in new `dashboard/` package, mounted when `--dashboard` flag present
- Static files served from `dashboard/static/` (HTML, CSS, JS)

</code_context>

<deferred>
## Deferred Ideas

- Mobile-responsive redesign — v1.1; current layout is desktop-first grid
- Dark/light theme toggle — v1.1; pick one theme for v1
- Alert sound/notification — v1.1; browser notification API
- Historical data replay (scrubber) — v2; requires data persistence layer
- Multi-dashboard (per-node view) — v2; requires URL routing
- Authentication on dashboard — v2; out of scope for local-only v1
- Config panel in UI (adjust thresholds live) — v2; requires two-way WebSocket control channel

</deferred>

---

*Phase: 06-dashboard-api*
*Context gathered: 2026-05-02*
