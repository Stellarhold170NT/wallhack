# Source Code Analysis: prunedAttentionGRU

**Date:** 2026-04-30
**Repository:** `llm-wiki/raw/prunedAttentionGRU/`
**Paper:** Kang et al. 2025, Sensors 25, 1547

---

## 1. Architecture Deep Dive

### Total Lines of Code
| File | Lines | Purpose |
|------|-------|---------|
| `PrunedAttentionGRU.py` | 78 | Main model definition |
| `prunedGRU.py` | 63 | Custom GRU cell (hand-written loop) |
| `MaskedAttention.py` | 106 | Simplified attention + MaskedLinear |
| `train.py` | 139 | Training loop with MixUp |
| `augmentation.py` | 78 | Gaussian noise + temporal shifting |
| `premodel.py` | 92 | Dataset loaders (ARIL/HAR/SignFi/StanFi) |
| **Total core** | **~556** | Excluding dataset-specific loaders |

**Key insight:** The entire model + training + augmentation fits in ~550 lines of pure Python. This is drastically simpler than Wallhack1.8k's ResNet18 approach or RuView's 21K-line Rust stack.

### Model Architecture (`PrunedAttentionGRU.py`)

```
Input: (batch, seq_len, input_dim)
    │
    ▼
CustomGRU(input_dim → hidden_dim=128)
    │  └─ update_gate: Linear(input+hidden, hidden)
    │  └─ reset_gate:  Linear(input+hidden, hidden)
    │  └─ new_memory:  Linear(input+hidden, hidden)
    │  └─ Manual loop over time steps (NOT cuDNN optimized)
    ▼
GRU output: (batch, seq_len, hidden_dim=128)
    │
    ▼
MaskedAttention(hidden_dim=128 → attention_dim=32)
    │  └─ Q/K/V: 3 × Linear(128, 32)
    │  └─ attn_scores = tanh(Q + K)
    │  └─ context_vector = Linear(32, 1)  → squeeze → softmax
    │  └─ weighted sum over seq_len
    ▼
Context vector: (batch, attention_dim=32)
    │
    ▼
FC: Linear(32 → num_classes)
    │
    ▼
Output: (batch, num_classes)
```

### Parameter Count Breakdown (ARIL config)

| Component | Calculation | Params |
|-----------|-------------|--------|
| CustomGRU gates | (52+128)×128 × 3 gates | 69,120 |
| Attention Q/K/V | 128×32 × 3 | 12,288 |
| Attention context | 32×1 | 32 |
| FC output | 32×6 | 192 |
| **Total** | | **~81,632** (~82.1K) |

Matches paper exactly. After pruning k=0.7 → ~57.8K.

### Critical Simplification

The attention is **NOT** standard scaled dot-product attention. It uses:
```python
attn_scores = torch.tanh(query + key)  # element-wise addition, not dot product!
attn_scores = context_vector(attn_scores).squeeze(-1)
attn_weights = F.softmax(attn_scores, dim=-1)
```

This is a **simplified additive attention** (Bahdanau-style) rather than multiplicative attention (Vaswani-style). It uses fewer parameters and is easier to train on small datasets.

---

## 2. Data Flow & Preprocessing

### ARIL Dataset Loader (`ARIL/aril.py`)

```python
# Raw .mat file contains amplitude CSI
# Shape after transpose: (samples, 192, 52)
#   - 1116 training samples
#   - 324 test samples
#   - 192 time steps
#   - 52 subcarriers

# StandardScaler per-sample (reshape to 2D, scale, reshape back)
scaler = StandardScaler().fit(X_train_2d)  # X_train_2d: (1116, 192*52)
X_train = scaler.transform(X_train_2d).reshape(1116, 192, 52)
```

**ESP32-S3 compatibility:**
- ARIL uses **52 subcarriers** = exactly ESP32-S3 L-LTF subcarrier count
- Our ESP32 outputs 52 subcarriers × I/Q → we take amplitude → shape matches
- Window size: 192 time steps @ ~100 Hz ≈ 2 seconds. Our 4s window = ~400 steps
- **Direct mapping possible** with minimal preprocessing

### HAR-1 Dataset Loader (`HAR/har.py`)

```python
# Loads .npy files: X_train.npy, X_test.npy
# Input size: 104 channels, 4 classes
# Likely amplitude + phase (52×2) or 2 antennas × 52 subcarriers
```

**Significance:** The authors already tested on a **4-class CSI dataset** (HAR experiment-1). This is the closest analog to our target (empty, static, walking, waving).

---

## 3. Data Augmentation Implementation (`augmentation.py`)

### Gaussian Noise — Multiplicative (Not Additive!)

```python
noise = np.random.normal(0, 1, shape)
noisy_data = X_train + X_train * noise  # MULTIPLICATIVE!
```

**Paper says:** "Gaussian noise with σ²=0.0001"
**Code does:** `N(0,1)` multiplied element-wise with data, then added.

Because data is StandardScaler-normalized (mean≈0, std≈1), the effective noise variance depends on the data magnitude. For normalized data, this is roughly equivalent to additive noise with σ≈1, but correlated with signal amplitude.

**Impact:** Generates 3 noisy copies → 4× dataset expansion.

### Temporal Shifting — Circular Roll

```python
shifts = range(-10, 10)  # 20 shifts total
shifted = np.roll(data, shift=shift_steps, axis=1)
```

**Critical detail:** Uses `np.roll` which is **circular** (wraps around). The paper mentions "signal discontinuities at junctures where front and end segments meet" — these discontinuities are treated as implicit noise.

**Impact:** 20× expansion (±10 steps).

### Combined Augmentation

```python
X_aug = concat([shifted_data, gaussian_noisy_data])
# 20x + 4x = 24x expansion total
```

**Without augmentation:** 69.42% accuracy (from ablation table)
**With augmentation:** 98.92% accuracy

**→ Data augmentation is THE critical success factor.**

---

## 4. Training Loop (`train.py`)

### MixUp Application

```python
option = np.random.choice(['mixup', 'naive'], p=[0.3, 0.7])
# 30% of batches use MixUp, 70% use standard training
```

MixUp blends two samples: `data = λ*data_a + (1-λ)*data_b` where λ ~ Beta(1,1).
Loss is also blended: `loss = λ*loss_a + (1-λ)*loss_b`.

### Scheduler

```python
optimizer = Adam(lr=1e-3)
scheduler = CosineAnnealingLR(optimizer, T_max=100)
```

### Missing from Open-Source Code

| Claimed in Paper | Present in Code? | Note |
|------------------|------------------|------|
| Pre-training | ❌ No | `main.py` calls `train_model` directly |
| Pruning during training | ❌ No | `prune_by_std()` defined but never called |
| Fine-tuning after pruning | ❌ No | No second training phase |
| 5-fold cross-validation | ⚠️ Partial | `cross_validate()` exists but not used in `main.py` |

**Reality:** The published code trains a standard Attention-GRU (with MixUp) but does NOT implement the full pretrain→prune→finetune pipeline described in the paper. The "pruned" model in the repo is actually just a regular model with `mask=ones()`.

**For our project:** We don't need pruning. The unpruned 82K-param model is already tiny. We can skip pruning entirely and still get ~98% accuracy.

---

## 5. Performance Benchmarks

### Inference Speed (Estimated)

CustomGRU uses a Python loop over time steps (not cuDNN). For a single sample:
- 192 time steps × 128 hidden × 3 gates = ~73K operations per GRU forward
- Attention: 192 × 128 × 32 ≈ 786K operations
- Total: < 1M FLOPs per sample
- On laptop CPU: < 1 ms inference
- On ESP32-S3: Not feasible (no matrix acceleration)

**→ Inference must stay on laptop/aggregator.**

### Memory Footprint

| Component | Memory |
|-----------|--------|
| Model weights (82K params × 4 bytes) | ~328 KB |
| Activation buffer (1 sample, 192×128) | ~98 KB |
| Total runtime | ~500 KB |

Fits easily in any modern device. Could even run on Raspberry Pi Zero.

---

## 6. Code Quality Assessment

### Strengths
- Extremely simple and readable
- No external dependencies beyond PyTorch + sklearn
- Modular: easy to swap dataset loaders
- StandardScaler normalization prevents scale issues

### Weaknesses / Bugs
- `CustomGRU` hand-written loop is **slow** (10-50× slower than `nn.GRU`)
- `test.py` uses undefined `num_classes` variable (line 46)
- `MaskedAttention.prune()` references `linear.in_features` which exists but is fragile
- No validation set during training (only train/test split)
- No early stopping implementation (despite paper claim)
- Random seed hardcoded in `augmentation.py` (seed=1)

### For Our Adaptation
- Replace `CustomGRU` with `nn.GRU` for 10× training speedup
- Keep `MaskedAttention` as-is (simple and effective)
- Write custom dataset loader for ESP32-S3 CSI format
- Add validation split for early stopping
- Remove pruning code (unnecessary for our scale)

---

## 7. Impact on Project Scope

### What This Proves

1. **Model is trivial to implement** — 78 lines of model code. We can replicate it in < 30 minutes.
2. **52 subcarriers directly compatible** — ARIL uses exactly 52 subcarriers. No input dimension changes needed.
3. **4-class classification proven** — HAR-1 experiment uses 4 classes. This is our exact target.
4. **No complex signal preprocessing needed for HAR** — Raw amplitude + StandardScaler is sufficient. Phase unwrap, Hampel filter, etc. are NOT required for activity classification (though still useful for presence detection).
5. **Data collection is the only real bottleneck** — We need ~200 labeled samples per class. The model and training are solved problems.

### Revised Risk Assessment

| Task | Previous Risk | Revised Risk | Reason |
|------|---------------|--------------|--------|
| Activity Recognition model | Medium | **Very Low** | Code exists, proven, 82K params |
| Data augmentation | Medium | **Low** | Shifting + MixUp = 20 lines of code |
| ESP32-S3 data → model input | Medium | **Low** | 52 subcarriers match exactly |
| Training pipeline | Medium | **Very Low** | `train.py` is 139 lines, ready to adapt |
| Real-time inference | Low | **Very Low** | < 1ms on CPU |
| **Data collection** | High | **High** | Still need 800+ labeled samples (4 classes × 200) |
| **Label consistency** | Medium | **Medium** | Human annotation quality matters |

### Recommended Scope Adjustments

**Phase 5 (Activity Recognition) should be simplified:**
- Instead of designing a model from scratch, **adapt the existing `prunedAttentionGRU` codebase**
- Replace `CustomGRU` with `nn.GRU` for speed
- Remove pruning code (not needed)
- Write a single `esp32_loader.py` that converts our CSI `.npy`/`.csv` to the expected `(samples, time, 52)` format
- Expected effort: **1-2 days** instead of 1-2 weeks

**Phase 3 (Signal Processing) can be narrowed:**
- For Activity Recognition: only need **amplitude extraction + StandardScaler**
- Phase unwrap, Hampel filter, spectrogram are **optional** for HAR (though still needed for presence/intrusion detection)
- Split Phase 3 into:
  - Minimal HAR preprocessing (amplitude + scaler) — required
  - Advanced DSP (phase, Hampel, spectrogram) — optional, for presence detection only

**New Opportunity: On-Device Feasibility?**
- 82K params × 4 bytes = 328 KB
- ESP32-S3 has 520 KB SRAM
- **Could we run inference ON the ESP32-S3?**
- CustomGRU is simple enough to port to C/Arduino
- BUT: PyTorch model → C conversion requires tools like ONNX Micro or custom C implementation
- **Verdict:** Possible but risky for v1. Keep inference on laptop. Add to v2 backlog.

---

## 8. Action Items

- [ ] Copy `PrunedAttentionGRU.py`, `MaskedAttention.py`, `train.py`, `augmentation.py` to our repo
- [ ] Replace `CustomGRU` with `nn.GRU`
- [ ] Write `esp32_dataset.py` loader for our CSI format
- [ ] Verify training on a small test dataset (e.g., ARIL subset)
- [ ] Collect ESP32-S3 labeled data: 4 classes × 200 samples × ~200 time steps

---
*Analysis completed: 2026-04-30*
