---
phase: 06-dashboard-api
plan: 03
status: complete
commit: feat(06-03): Wire dashboard into aggregator CLI with --dashboard flag and integration tests
---

## Summary

Wired the dashboard into the aggregator CLI and validated complete integration with tests.

### What Was Built

- `aggregator/main.py` — Dashboard integration
  - Added `--dashboard` flag (default False)
  - Added `--dashboard-port` flag (default 8024)
  - Added `--dashboard-config` flag
  - DashboardState created with alert_queue, activity_queue, amplitude_queue, node_source
  - Uvicorn server started in same asyncio event loop when --dashboard present
  - Graceful shutdown: uvicorn stopped before classifier/detector/processor/consumer cancellation
- `tests/test_dashboard.py` — 4 integration tests
  - test_dashboard_state_queue_consumption: verifies queue consumption and state updates
  - test_status_endpoint: verifies GET /status returns presence, activity, node_health
  - test_alerts_endpoint: verifies GET /alerts with count parameter
  - test_websocket_endpoint: verifies /ws returns JSON with all required keys

### Key Decisions

- Dashboard shutdown happens before pipeline task cancellation — prevents data loss and ensures clean disconnect
- ImportError guard for dashboard dependencies — aggregator works without dashboard deps installed

### Tests

- `pytest tests/test_dashboard.py -v` — 4/4 passed in 1.26s
- Post-wave regression: `pytest tests/test_*.py` — 93/93 passed

## Self-Check

- [x] All tasks executed
- [x] Each change committed
- [x] SUMMARY.md created
