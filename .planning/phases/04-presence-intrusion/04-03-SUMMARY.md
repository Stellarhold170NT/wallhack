# Phase 04 — Plan 03 Summary

## Objective
Wire the presence detection system into the aggregator event loop. Create the third Queue for Phase 6 handoff, instantiate CsiDetector with feature_queue and node health source, and ensure graceful shutdown order. Write end-to-end integration tests.

## Deliverables
- `aggregator/main.py` — Wired with `_load_detector()`, `alert_queue`, `CsiDetector` task, reverse shutdown order
- `tests/test_detector_integration.py` — 5 end-to-end tests

## Key Implementation Details
- **Third Queue**: `alert_queue = asyncio.Queue(maxsize=100)` created in `run_server()`.
- **Detector Wiring**: `CsiDetector(input_queue=feature_queue, output_queue=alert_queue, node_health_source=server.nodes)`.
- **Shutdown Order**: detector → processor → consumer → server (reverse pipeline order).
- **CLI**: Added `--detector-config` argument for JSON config passthrough.
- **Backward Compatibility**: If `detector` import fails, aggregator continues without it (same pattern as processor).

## Test Results
`pytest tests/test_detector_integration.py` — **5 passed**
`pytest tests/` — **90 passed** (full suite, no regressions)

## Bugs Fixed During Execution
1. `detector` module not found by pytest because `PYTHONPATH` didn't include project root. Fixed by setting `PYTHONPATH` at test runtime.
2. Integration test produced no alerts because default `window_size=200` required too many frames. Added `PROC_CONFIG = {"window_size": 20, "step_size": 10}` for tests.
3. Baseline was contaminated by transition window (constant→motion spike) because `_update_baseline` ran before `_advance_state`. Fixed in Plan 1 (presence.py) by reordering.
4. Integration test expected first alert to be intrusion, but queue contained a "clear" alert from CONFIRMING_OCCUPIED→EMPTY transition. Fixed by searching all alerts for intrusion type.

## Hardware Tuning (ESP32-S3 @ 10 fps)
Post-deployment tuning to improve reaction time and prevent baseline contamination:

### Changes Made
- **`detector/presence.py`**:
  - Added `baseline_skip_threshold_sigma=2.0` — rejects motion frames during initial baseline build so startup occupancy doesn't poison the noise-floor estimate.
  - Updated defaults for 10 fps hardware:
    - `enter_frames`: 3 → 2 (faster detection)
    - `exit_frames`: 5 → 3 (faster clear)
    - `min_baseline_frames`: 10 → 6 (shorter learning phase)
    - `baseline_alpha`: 0.1 → 0.15 (slightly faster adaptation)
- **`detector/fusion.py`**:
  - Added `baseline_skip_threshold_sigma` to config passthrough whitelist.

### Recommended CLI for ESP32-S3
```powershell
python -m aggregator --port 5005 --log-level INFO `
  --processor-config '{"window_size":30,"step_size":15}' `
  --detector-config '{"enter_frames":2,"exit_frames":3,"min_baseline_frames":6,"baseline_alpha":0.15,"baseline_skip_threshold_sigma":2.0}'
```
*With `window_size=30` at 10 fps, each feature represents ~3 s of data and arrives every 1.5 s, giving ~3–4.5 s reaction time.*

### Timing Math (10 fps CSI)
| Config | Window | Step | Feature Rate | enter_frames=2 | exit_frames=3 |
|--------|--------|------|-------------|----------------|---------------|
| Default (200/50) | 20 s | 5 s | 0.2 Hz | ~10 s | ~15 s |
| **Tuned (30/15)** | **3 s** | **1.5 s** | **0.67 Hz** | **~3 s** | **~4.5 s** |

### Test Results After Tuning
`pytest tests/test_detector.py tests/test_alerts.py tests/test_detector_integration.py` — **41 passed** (no regressions)

## Hardware Testing Results (Real ESP32-S3 @ ~10 fps)

### Test Environment
- Single ESP32-S3 node (node_id=1), 128 subcarriers
- Residential house with 3 rooms, other people present in adjacent rooms
- Baseline was frequently contaminated because room was not empty during startup

### Observations
1. **Baseline contamination is the #1 problem**: If the room is not truly empty during the first ~20s, baseline learns `mean=3000+, std=2000+` instead of `mean=~100-300, std=~10-50`. Once contaminated, thresholds become meaningless.
2. **Motion vs breathing sensitivity**: At `enter_threshold_sigma=2.5`, the system detects *any* motion (including typing, shifting in chair). Raising to `3.0-4.0` reduces false positives but may miss slow movement.
3. **Environmental noise dominates**: Fans, doors closing, people walking in adjacent rooms all create CSI multipath changes that look like "motion" to a single-sensor threshold system.
4. **Accuracy improves in quiet, controlled environments**: Theoretical accuracy is highest in apartments (few reflections, no pets, stable temperature) with multi-node triangulation.

### Lessons Learned
- The system is currently a **"change detector"**, not a true **"human detector"**. It cannot distinguish between:
  - Person walking vs door slamming
  - Breathing vs fan vibration
  - One person vs multiple people
- **Multi-node spatial fusion** is required for any real-world reliability.
- **Sensor fusion** (PIR, mmWave) would dramatically reduce false positives.
- Baseline should ideally be **manually triggered** (e.g., "press button when room is empty") rather than auto-learning.

### Recommended Next Steps (Phase 5+)
1. Add manual baseline reset command (CLI signal or HTTP endpoint)
2. Implement per-node spatial calibration (RSSI + amplitude variance maps)
3. Consider time-of-day baseline profiles
4. Add second ESP32-S3 node for triangulation / OR fusion

## Files Modified
- `detector/presence.py`
- `detector/fusion.py`
- `detector/alerts.py`
- `detector/main.py`
- `aggregator/main.py`
- `scripts/generate_synthetic_csi.py` (new)
- `scripts/test_e2e_synthetic.py` (new)
- `tests/test_detector.py`
- `tests/test_alerts.py`
- `tests/test_detector_integration.py`
