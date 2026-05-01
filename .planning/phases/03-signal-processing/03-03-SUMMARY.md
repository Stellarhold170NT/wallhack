# Phase 03 Plan 03: CsiProcessor Integration + CLI + Wiring Summary

**Phase:** 03-signal-processing  
**Plan:** 03  
**Subsystem:** Signal Processing  
**Duration:** ~15 min  
**Completed:** 2026-05-01

---

## What Was Built

Integrated signal processing into the asyncio pipeline:

- **`processor/main.py`** — `CsiProcessor` class
  - Asyncio task consuming from input Queue (D-06), producing to output Queue (D-13)
  - Per-node `SlidingWindow` state keyed by `node_id` (D-18)
  - Applies Hampel filter per subcarrier on full windows
  - Flattens feature dict to 1D array: mean_amp[64] + var_amp[64] + motion_energy + breathing_band
  - Configurable via dict from Aggregator (D-12)
  - Max nodes cap (default 16) to prevent unbounded growth (T-03-07)
  - Graceful `CancelledError` and `TimeoutError` handling (T-03-06)
- **`processor/__main__.py`** — Offline CLI entry point
  - `python -m processor --input x.npy --output y.npy`
  - Processes saved `.npy` amplitude arrays through identical pipeline
  - Configurable window_size, step_size
- **`aggregator/main.py`** — Wired CsiProcessor into event loop
  - Creates second Queue (`feature_queue`) for Phase 4 handoff
  - Optionally instantiates `CsiProcessor` with config dict
  - Graceful shutdown: cancels processor before server stop
  - `--processor-config` CLI arg for JSON config passthrough
  - Backward compatible: continues without processor if import fails
- **`tests/test_processor_integration.py`** — 7 integration tests
  - Async CsiProcessor: 400 frames → 3 feature vectors
  - Per-node isolation: alternating node IDs produce separate outputs
  - Cancellation handling
  - Max nodes cap
  - Offline CLI: .npy input → feature output
  - Edge cases: too few frames, invalid shape

## Deviations from Plan

- **Deviation [Rule 1 - Test expectation]:** Plan expected 400 frames → 2 feature vectors. Actual sliding window behavior with step_size=100: 400 frames → 3 vectors (at frames 200, 300, 400). Corrected test expectations.
- **Deviation [Rule 1 - Bug]:** Offline CLI passed `phases=[]` to CSIFrame, triggering `__post_init__` validation error. Fixed: pass `phases=[0.0] * n_subcarriers`.

## Key Files Created / Modified

| File | Lines | Purpose |
|------|-------|---------|
| `processor/main.py` | 143 | CsiProcessor asyncio task |
| `processor/__main__.py` | 86 | Offline CLI entry point |
| `aggregator/main.py` | 166 | Wired processor into event loop (+40 lines) |
| `tests/test_processor_integration.py` | 162 | Integration tests |

## Self-Check

- [x] All tests pass: `pytest tests/test_processor_integration.py` → **7 passed**
- [x] Import check: `python -c "from processor.main import CsiProcessor; print('OK')"` → OK
- [x] CLI help: `python -m processor --help` shows valid parser
- [x] Aggregator dry-run: `python -c "import aggregator.main; print('OK')"` → OK

## Requirements Completed

- SIG-05 (sliding window integration) ✓
- SIG-06 (feature extraction integration) ✓

## Next

Phase 3 execution complete. Ready for post-execution verification.
