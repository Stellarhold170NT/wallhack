# Phase 03 Plan 02: Sliding Window + Feature Extraction Summary

**Phase:** 03-signal-processing  
**Plan:** 02  
**Subsystem:** Signal Processing  
**Duration:** ~10 min  
**Completed:** 2026-05-01

---

## What Was Built

Implemented sliding window buffering and feature extraction for CSI presence detection:

- **`processor/window.py`** — `SlidingWindow` class
  - Circular buffer of shape `(window_size, n_subcarriers)` using `np.roll`
  - Emits window every `step_size` frames once full (D-17: 200 frames, 50% overlap)
  - Validates frame amplitude length matches expected `n_subcarriers`
  - `is_full()` and `reset()` methods for state management
- **`processor/features.py`** — `extract_features()` function
  - Per-subcarrier mean and variance (64 + 64 = 128 features)
  - Motion energy: band power 0.5-3 Hz via FFT (1 feature)
  - Breathing band: band power 0.1-0.5 Hz via FFT (1 feature)
  - Optional `phase_variance` when `phase_window` provided
  - Total: 130 scalar features per window (D-16)
- **`tests/test_window.py`** — 8 tests covering emission timing, content accuracy, edge cases
- **`tests/test_features.py`** — 11 tests covering constant/sine inputs, band separation, shapes, errors

## Deviations from Plan

- **Deviation [Rule 1 - Bug]:** Plan expected 300 frames → 1 window, 400 frames → 2 windows. Actual behavior with step_size=100: 300 frames → 2 windows, 400 frames → 3 windows. Corrected test expectations to match correct mathematical sliding window behavior.
- **Deviation [Rule 1 - Bug]:** Test used 0.3 Hz sine wave for breathing band; FFT spectral leakage at 0.5 Hz boundary caused non-zero motion energy. Changed to 0.2 Hz (deeper in breathing band) and relaxed assertion to allow small leakage.

## Key Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `processor/window.py` | 89 | SlidingWindow circular buffer |
| `processor/features.py` | 95 | Feature extraction (130 features) |
| `tests/test_window.py` | 130 | Window buffer tests |
| `tests/test_features.py` | 117 | Feature extraction tests |

## Self-Check

- [x] All tests pass: `pytest tests/test_window.py tests/test_features.py` → **19 passed**
- [x] Import check passes
- [x] No pre-existing test failures introduced

## Requirements Completed

- SIG-05 (sliding window) ✓
- SIG-06 (feature extraction) ✓

## Next

Ready for Plan 03-03: CsiProcessor asyncio integration + offline CLI.
