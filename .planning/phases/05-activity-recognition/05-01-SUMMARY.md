## EXECUTION COMPLETE — Plan 05-01

**Phase:** 05-activity-recognition
**Plan:** 05-01 — Model Architecture + Dataset Infrastructure
**Status:** All 3 tasks complete, 20/20 tests passing

### Commits

| Commit | Message | Files |
|--------|---------|-------|
| `5f33359` | `feat(05): add AttentionGRU model with nn.GRU + additive attention` | `classifier/__init__.py`, `classifier/model.py` |
| `1059a8e` | `feat(05): add ESP32/HAR dataset loaders with scaler persistence and tests` | `classifier/dataset.py`, `tests/test_classifier.py` |

### Artifacts

| File | Purpose | Status |
|------|---------|--------|
| `classifier/__init__.py` | Package init, exports model + dataset | Done |
| `classifier/model.py` | AttentionGRU (nn.GRU + additive attention, 74,564 params) | Done |
| `classifier/dataset.py` | Esp32Dataset, HarDataset, scaler save/load | Done |
| `tests/test_classifier.py` | 20 unit tests (model, dataset, scaler, integration) | Done |

### Decisions Implemented

| Decision | Description | Implementation |
|----------|-------------|---------------|
| D-34 | Raw amplitude + StandardScaler per subcarrier | `fit_scaler()`, scaler applied in `__getitem__` with 2D reshape |
| D-36 | Center-crop to 52 subcarriers | `_center_crop_1d()` in dataset.py, symmetric pad if < 52 |
| D-37 | 50-frame windows | Padding / truncation via `_center_crop_1d()` on time axis |
| D-38 | `classifier/` package structure | Package with `__init__.py`, `model.py`, `dataset.py` |
| D-41 | HAR dataset loader for pre-training | `HarDataset` loads CSV files, maps 5 labels |
| D-42 | nn.GRU + attention, hidden=128, attention=32, ~75K params | `AttentionGRU` with `nn.GRU` + `nn.Sequential` attention |

### Verification Results

```
20 passed in 6.68s
- Model forward: (batch, 50, 52) → (batch, 4) ✓
- Parameter count: 74,564 (in range 74K-90K) ✓
- Gradients flow through all layers ✓
- Attention weights sum to 1 (softmax) ✓
- No pruning code present ✓
- Esp32Dataset loads .npy files, crops/pads correctly ✓
- Scaler save/load JSON roundtrip ✓
- Model consumes dataset output end-to-end ✓
```

### Architectural Notes

- **nn.GRU** replaces CustomGRU (~10× cuDNN speedup)
- **Additive attention** (tanh + linear + softmax) replaces MaskedAttention
- **FC layer** projects from hidden_dim (128) not attention_dim, since context = weighted sum of GRU outputs
- Parameter count (74,564) is slightly under the original 82K estimate because the simplified attention uses fewer linear layers than the paper's query+key+value structure
- No pruning, no masks — all standard PyTorch modules for maximum compatibility

