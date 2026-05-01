# Phase 04 — Plan 01 Summary

## Objective
Build the core presence detection engine: per-node adaptive baseline learning, multi-feature hysteresis state machine, and multi-node fusion logic.

## Deliverables
- `detector/presence.py` — `PresenceDetector` with adaptive baseline and hysteresis
- `detector/fusion.py` — `FusionEngine` with OR/AND modes and stale-node exclusion
- `tests/test_detector.py` — 22 unit tests

## Key Implementation Details
- **Baseline**: Welford's algorithm for initial build (first 10 frames), then EMA updates only when state is EMPTY/CONFIRMING_EMPTY. This prevents motion spikes from contaminating the noise floor.
- **State Machine**: EMPTY → CONFIRMING_OCCUPIED → OCCUPIED → CONFIRMING_EMPTY → EMPTY, with configurable frame counters (3 enter, 5 exit) and sigma thresholds (2.5σ enter, 1.5σ exit).
- **Fusion**: OR mode default, AND configurable. Auto-excludes stale nodes; zero healthy nodes returns "unknown".

## Test Results
`pytest tests/test_detector.py` — **22 passed**

## Bugs Fixed During Execution
1. `_build_baseline` initially used EMA for all frames, causing slow convergence (mean=0.878 after 20 frames). Replaced initial phase with Welford's online mean/variance.
2. 2D array input caused `TypeError` in `float(fv[2*N])`. Added `fv.ndim != 1` validation before parsing.
3. `_build_result` returned raw enum values ("confirming_occupied"). Fixed to map to "occupied"/"empty" for consumer compatibility.
4. Baseline update was performed before state machine advancement, allowing spikes to contaminate baseline. Moved baseline update to after `_advance_state()`.

## Files Modified
- `detector/__init__.py`
- `detector/presence.py`
- `detector/fusion.py`
- `tests/test_detector.py`
