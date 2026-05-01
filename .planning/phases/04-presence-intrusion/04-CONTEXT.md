# Phase 4: Presence & Intrusion Detection - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Detect human presence from CSI feature vectors and emit intrusion alerts.

**Phase boundary:**
- IN: Feature vectors per 4-second window from Phase 3 (mean_amp, var_amp, motion_energy, breathing_band)
- OUT: Presence state (occupied/empty per node + fused) + intrusion alert stream with cooldown

**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04

</domain>

<decisions>
## Implementation Decisions

### Detection Algorithm
- **D-21:** Adaptive baseline learning for empty-room noise floor
  - System automatically updates baseline when room is confirmed empty
  - Baseline tracks mean + std of variance across subcarriers over time
  - Adapts to environmental changes (furniture moved, temperature, etc.) without manual recalibration
  - No fixed threshold — presence detected when current features deviate from learned baseline by N standard deviations
- **D-22:** Multi-feature combination for presence detection
  - Use both `motion_energy` (0.5-3 Hz) and `breathing_band` (0.1-0.5 Hz) from feature vector
  - Weighted combination: motion_energy is primary indicator, breathing_band confirms stationary person
  - `var_amp` (per-subcarrier variance) used for baseline adaptation, not direct detection
- **D-23:** Per-node independent detector
  - Each node runs its own presence detector with its own adaptive baseline
  - Baselines are not shared across nodes (different RF paths, different noise floors)

### State Machine & Hysteresis
- **D-24:** Hysteresis with asymmetric enter/exit thresholds
  - Enter threshold (Empty → Occupied): higher sensitivity — deviation from baseline > 2.5σ
  - Exit threshold (Occupied → Empty): lower sensitivity — deviation from baseline < 1.5σ
  - Prevents rapid state flipping when person stands at detection boundary
- **D-25:** Consecutive frame confirmation
  - Require **3 consecutive feature vectors** (≈6 seconds) above enter threshold before declaring "Occupied"
  - Require **10 seconds of silence** (≈5 feature vectors) below exit threshold before returning to "Empty"
  - These delays are intentional: enter needs quick response for intrusion alerts, exit needs stability to avoid false clears
- **D-26:** Alert cooldown (5 seconds)
  - After an intrusion alert fires, suppress subsequent alerts for 5 seconds
  - Cooldown is per-system (not per-node) — one alert covers the entry event
  - SEC-04 compliance

### Alert Output Format & Persistence
- **D-27:** Dual output: JSONL persistence + in-memory buffer
  - JSONL file: `data/alerts/alerts_YYYY-MM-DD.jsonl` — append-only, one line per alert
  - In-memory buffer: keeps last 100 alerts for API/WebSocket query (Phase 6 handoff)
  - Both outputs receive identical alert objects
- **D-28:** Alert object structure
  ```python
  {
      "timestamp": str,      # ISO-8601 UTC
      "node_id": int,
      "status": str,         # "occupied" | "empty"
      "confidence": float,   # 0.0-1.0 — normalized deviation from baseline
      "type": str,           # "intrusion" | "clear" | "heartbeat"
      "trigger_feature": str # "motion_energy" | "breathing_band" | "combined"
  }
  ```
  - `type="intrusion"`: fired on Empty→Occupied transition (only during cooldown-aware window)
  - `type="clear"`: fired on Occupied→Empty transition (optional, for logging)
  - `type="heartbeat"`: periodic status log every 30s for health monitoring
- **D-29:** Third Queue for Phase 6 handoff
  - Presence detector pushes alerts to a third `asyncio.Queue` (in addition to feature_queue)
  - Phase 6 consumer (WebSocket/API) pulls from this Queue for real-time updates
  - Queue bounded (maxsize=100) with drop-oldest on overflow

### Multi-Node Fusion & Node Health
- **D-30:** OR logic default for 2-node fusion
  - System presence = occupied if ANY healthy node reports occupied
  - Configurable via config dict: `"fusion_mode": "or" | "and"` (default "or")
  - AND mode requires ALL healthy nodes to agree — reduces false positives but increases false negatives
- **D-31:** Auto-exclude stale nodes from fusion
  - Nodes marked stale by `aggregator/server.py` stale_checker (>10s no frames) are excluded from fusion
  - Stale nodes do not vote "empty" — they are simply ignored
  - When node recovers, it rejoins fusion after 3 valid feature vectors (same as D-25 enter confirmation)
- **D-32:** Single-node degradation
  - If only 1 node is healthy, fusion falls back to that node's decision (no change in behavior)
  - If 0 nodes are healthy, system reports "unknown" status with last known state timestamp

### the agent's Discretion
- Exact baseline adaptation rate (EMA alpha for baseline updates)
- Presence confidence normalization method (sigmoid vs linear scaling)
- Whether to include `var_amp` in detection (currently used only for baseline)
- Alert log rotation policy (daily vs by size)
- Whether heartbeat alerts are needed or just on state change

</decisions>

<specifics>
## Specific Ideas

- "Adaptive baseline giúp không phải cấu hình lại mỗi khi thay đổi vị trí đồ đạc trong phòng" — adaptive baseline avoids recalibration
- "Hysteresis & cooldown giúp thông báo không bị nhảy loạn xạ khi ngườI đứng ở mép vùng nhận diện" — hysteresis prevents boundary flicker
- "Stale node exclusion cực kỳ quan trọng khi dùng nhiều node, tránh 1 node hỏng làm hỏng cả kết quả" — auto-exclude stale nodes for reliability
- Dashboard needs presence indicator (green=empty, red=occupied) — Phase 6

</specifics>

<canonical_refs>
## Canonical References

### Signal processing output
- `processor/main.py` — `CsiProcessor` class, feature vector emission log (D-20)
- `processor/features.py` — Feature vector format: mean_amp, var_amp, motion_energy, breathing_band (D-16)
- `.planning/phases/03-signal-processing/03-CONTEXT.md` — D-13 (Queue handoff), D-16 (feature format), D-18 (per-node fusion), D-19 (subcarrier adaptation)

### Aggregator node health
- `aggregator/server.py` — `NodeState.stale` flag, `_stale_checker()` marks nodes stale after 10s
- `aggregator/main.py` — Event loop wiring, `feature_queue` creation for Phase 4 handoff

### Requirements
- `.planning/REQUIREMENTS.md` — SEC-01..SEC-04

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — Data flow diagram showing Phase 3 → Phase 4 Queue handoff

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aggregator/server.py:NodeState.stale` — stale node detection already implemented, reuse for fusion exclusion (D-31)
- `aggregator/main.py:feature_queue` — second Queue already exists for Phase 4 handoff; need third Queue for alert handoff to Phase 6 (D-29)
- `processor/features.py` — Feature extraction already produces motion_energy and breathing_band; no changes needed in Phase 3
- Python `logging` module — use `logging.handlers.RotatingFileHandler` or manual rotation for JSONL alert log

### Established Patterns
- Asyncio task pattern: Phase 4 detector runs as asyncio task in same event loop (same as CsiProcessor in Phase 3)
- Per-node state dict keyed by `node_id` — reuse pattern from `processor/main.py` and `aggregator/server.py`
- Queue-based producer/consumer — feature vectors arrive on Queue, alerts emitted to Queue
- Dataclass output — feature dict pattern from Phase 3; alerts should follow similar structured dict pattern

### Integration Points
- Phase 3 → Phase 4: `feature_queue` (already created in `aggregator/main.py`)
- Phase 4 → Phase 6: New alert Queue needs to be created in `aggregator/main.py` and wired to presence detector
- Presence detector needs access to `CsiUdpServer.nodes` dict for stale node information — may need to pass server reference or stale state snapshot
- Alert JSONL persistence — new module `detector/persistence.py` or inline in detector task

</code_context>

<deferred>
## Deferred Ideas

- Subcarrier-level presence (which subcarriers detected motion) — out of scope, could be Phase 6 visualization enhancement
- Time-of-day adaptive thresholds (different sensitivity at night vs day) — Phase 6 scheduling feature
- Alert notification via email/SMS/Slack — new capability, separate phase
- Presence confidence heatmap over time — Phase 6 dashboard feature
- Breathing rate estimation from breathing_band — v2 advanced signal processing (SIG-12)

</deferred>

---

*Phase: 04-presence-intrusion*
*Context gathered: 2026-05-01*
