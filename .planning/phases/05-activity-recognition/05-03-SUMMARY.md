# 05-03 SUMMARY — Real-time Activity Classification Inference

**Plan:** 05-03-PLAN.md
**Phase:** 05-activity-recognition (Wave 3)
**Completed:** 2026-05-01

## Files Created/Modified

| File | Action | Lines |
|------|--------|-------|
| `classifier/infer.py` | Created | 303 |
| `classifier/__main__.py` | Created | 216 |
| `aggregator/main.py` | Modified | +45 |
| `tests/test_infer.py` | Created | 327 |
| `tests/test_classifier_integration.py` | Created | 255 |

## Implementation Summary

### Task 1: `classifier/infer.py` — Real-time inference task
- **ActivityLabel** dataclass with timestamp, node_id, label, confidence, class_probs, `to_dict()` serialization
- **SlidingWindowBuffer** per-node circular accumulator with 50-frame window, 25-frame step, center-crop/pad to 52 subcarriers (D-36, D-37)
- **CsiClassifier** asyncio task following CsiDetector pattern:
  - Loads AttentionGRU from checkpoint via `classifier.train.load_checkpoint`
  - Loads StandardScaler from JSON (D-34)
  - Normalizes windows: flatten → transform → reshape
  - Runs inference with `torch.no_grad()`
  - Softmax probabilities → label selection with confidence threshold
  - 4 classes: walking, running, lying, bending (D-35)
  - Emits `ActivityLabel.to_dict()` to output queue
  - Graceful shutdown via asyncio.Event

### Task 2: `aggregator/main.py` — Pipeline integration (D-39)
- Added `_load_classifier()` dynamic import (same pattern as processor/detector)
- Created `amplitude_queue` (fan-out from raw frames) and `activity_queue` (for Phase 6)
- Consumer fans out frames to both raw_queue (existing) and amplitude_queue (new)
- Classifier task started alongside processor and detector
- Shutdown cancels classifier before detector, after processor
- `--classifier-config` CLI argument for model/scaler path overrides

### Task 3: `classifier/__main__.py` — Offline CLI
- Supports `--input` (file or directory), `--model`, `--scaler`, `--output`, `--batch-size`, `--confidence-threshold`, `--device`
- Processes 3D .npy files (samples, timesteps, subcarriers)
- JSON or CSV output formats
- `python -m classifier --help` works

### Task 4: Tests (23 tests, all passing)
- **test_infer.py (17 tests):** ActivityLabel serialization, SlidingWindowBuffer accumulation/overlap/crop/pad/per-node isolation, CsiClassifier model loading, output shape, queue emission, confidence threshold, graceful shutdown, max_nodes cap, inference latency <10ms
- **test_classifier_integration.py (6 tests):** End-to-end pipeline, multiple windows, parallel processor+classifier, no-blocking, checkpoint round-trip, JSON serializability

## Design Decisions Applied
- **D-34:** Raw amplitude + StandardScaler (same preprocessing as training)
- **D-35:** 4 classes: walking, running, lying, bending
- **D-37:** 50-frame windows with 25-frame step
- **D-39:** Fork after server — consumer fans out to both raw_queue and amplitude_queue

## Verification
```
python -c "from classifier.infer import CsiClassifier, ActivityLabel"  ✓
python -m classifier --help                                           ✓
python -m aggregator --help | grep classifier-config                  ✓
pytest tests/test_infer.py tests/test_classifier_integration.py -v    ✓ (23 passed)
```
