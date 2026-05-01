# Plan 05-02 Summary — Training Pipeline & Data Collection

**Completed:** 2026-05-01
**Status:** All tasks complete, 20/20 tests pass, no LSP diagnostics

## Files Created

| File | Purpose |
|------|---------|
| `classifier/augment.py` | Data augmentation: shift (21×), noise (4×), MixUp, augment_dataset |
| `classifier/train.py` | Training loop, early stopping, ARIL pre-training, ESP32 fine-tuning, 5-fold CV, checkpoint save/load, CLI |
| `classifier/collect.py` | CLI tool for recording labeled CSI activity data via UDP |
| `tests/test_train.py` | 9 tests covering convergence, early stopping, checkpoint I/O, cross-validation, output shapes, CLI |
| `tests/test_collect.py` | 11 tests covering init, label validation, file naming, metadata JSON, CLI |

## Files Modified

| File | Change |
|------|--------|
| `classifier/__init__.py` | Added exports from augment.py and train.py |

## Verification Results

```
$env:PYTHONPATH="."; python -m pytest tests/test_train.py tests/test_collect.py -x -v
20 passed in 23.29s
```

- shift_augment: 10 samples → 210 (21×) ✓
- noise_augment: 10 samples → 40 (4×) ✓
- mixup_augment: 4 samples → (4, 4) one-hot soft targets ✓
- Training convergence: loss decreases over 5 epochs ✓
- Early stopping: triggers with patience=2 ✓
- Checkpoint save/load roundtrip: weights match ✓
- Cross-validation: 2 folds produce valid accuracies ✓
- ARIL 6-class: model.fc.out_features == 6 ✓
- ESP32 4-class: model.fc.out_features == 4 ✓
- CLI train --help: shows all expected args ✓
- CLI collect --help: shows all expected args ✓
- CsiCollector label validation: rejects unknown labels ✓
- CsiCollector file naming: timestamp + node_id pattern ✓
- JSON metadata: all required fields present ✓
- No regressions: 20 existing classifier tests still pass ✓

## Key Decisions Implemented

- **D-33:** ARIL pre-train (6-class) + ESP32 fine-tune (4-class) via `pretrain_aril()` / `finetune_esp32()`
- **D-37:** 50-frame windows with 25-frame step in collect.py sliding window
- **D-40:** `python -m classifier.collect --label walking --duration 30 --output data/activities/`
- **D-41:** Pre-training on all 6 ARIL classes
- **D-43:** Offline training with shift+noise augmentation, 20% validation split, early stopping (patience=10), 5-fold CV
