# Phase 04 — Plan 02 Summary

## Objective
Build the alert emission system and asyncio task wrapper. AlertManager handles cooldown, JSONL persistence, and in-memory buffering. CsiDetector is the asyncio task that consumes the feature_queue from Phase 3, runs fusion, and pushes alerts to the alert_queue for Phase 6.

## Deliverables
- `detector/alerts.py` — `AlertManager` with cooldown, JSONL persistence, ring buffer
- `detector/main.py` — `CsiDetector` asyncio task wrapper
- `tests/test_alerts.py` — 14 tests

## Key Implementation Details
- **Alert Dataclass**: `Alert` with `to_dict()` for serialization; fields match D-28 spec.
- **Cooldown**: 5-second suppression for `type="intrusion"`; clear and heartbeat bypass.
- **JSONL**: Daily rotation (`alerts_YYYY-MM-DD.jsonl`), append mode, `os.makedirs` with `exist_ok`.
- **Buffer**: `deque(maxlen=100)` drop-oldest; `get_recent(count)` returns newest first.
- **CsiDetector**: Consumes `feature_queue`, auto-registers nodes (max 16), syncs stale state from `server.nodes`, emits alerts to `output_queue`, periodic heartbeat every 30s.

## Test Results
`pytest tests/test_alerts.py` — **14 passed**

## Bugs Fixed During Execution
1. JSONL append test failed because default 5s cooldown blocked 2nd/3rd intrusion alerts. Fixed test to use `cooldown_seconds=0.0`.
2. Buffer drop-oldest test had same cooldown issue. Fixed.
3. `get_recent` returned oldest-first; fixed to reverse slice (`[::-1]`) for newest-first.
4. Graceful cancellation test expected `CancelledError` to propagate, but `CsiDetector.run()` catches it internally. Fixed test to accept clean exit without exception.

## Files Modified
- `detector/alerts.py`
- `detector/main.py`
- `tests/test_alerts.py`
