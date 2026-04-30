# Research: WiFi CSI Human Activity Recognition — Key Findings

**Date:** 2026-04-30
**Source:** `llm-wiki/raw/Human_Activity_Recognition_Through_Augmented_WiFi_.pdf`
**Paper:** Kang, H.; Kim, D.; Toh, K.-A. "Human Activity Recognition Through Augmented WiFi CSI Signals by Lightweight Attention-GRU", Sensors 2025, 25, 1547.

---

## 1. Core Architecture (Extremely Lightweight)

| Component | Config | Parameters |
|-----------|--------|------------|
| GRU | 1 layer, hidden dim 128 | ~69.7K |
| Self-Attention | Hidden dim 32 | ~12.4K |
| FC Output | 6 classes (ARIL) | ~0.8K |
| **Total (before pruning)** | | **~82.1K** |
| **Total (after pruning k=0.7)** | | **~57.8K** |

**Key insight:** A single-layer GRU + attention module outperforms deep CNNs, Bi-LSTMs, and even Transformers — while being 4000x smaller than SOTA (CSITime: 252.1M params).

## 2. Results Across 4 Datasets

| Dataset | Activities | Accuracy | Our Model (GFLOPs/Params) | SOTA Baseline |
|---------|-----------|----------|---------------------------|---------------|
| **ARIL** | 6 hand gestures | **98.92%** | 0.01 / 0.058M | CSITime: 98.20% (18.06 / 252.1M) |
| **StanFi** | 6 daily activities | **99.33%** | 0.0083 / 0.068M | STC-NLSTMNet: 99.88% (0.044 / 0.087M) |
| **Sign-Fi** | 276 sign gestures | **99.32%** | 0.005 / 0.282M | CSITime: 99.22% (18.06 / 252.1M) |
| **Nexmon HAR** | 8 activities | **100%** | 0.15 / 0.157M | LSTM: 98.95% (3.72 / 0.248M) |

**Critical observation:** The model achieves >98% accuracy on datasets with 6-8 common activities (ARIL, StanFi, HAR) and even 276 sign gestures (Sign-Fi). This validates that **4-class activity recognition (empty, static, walking, waving) is well within reach**.

## 3. Data Augmentation — The Secret Sauce

Without augmentation, baseline accuracy drops to **69.42%**. With augmentation: **98.92%**.

| Technique | Individual Impact | Optimal Setting |
|-----------|------------------|-----------------|
| **Temporal Shifting** | Most critical (88.49% → 98.92%) | ±10 steps |
| **MixUp** | Second most important (89.93% without) | α=1.0, r=0.7 |
| **Gaussian Noise** | Subtle but helpful (94.61% alone) | σ² = 0.0001 |

**Shifting implementation:** Circular shift sequence forward/back by n steps (n=1..10). The discontinuity at wrap-around acts as implicit noise injection.

## 4. Pruning Strategy

- Weight pruning: set weights below threshold s to zero
- Optimal: keep ratio k=0.7, threshold s=0.9
- Result: **29.5% parameter reduction** (82.1K → 57.8K) with **accuracy maintained** (69.42% → 69.42% after fine-tuning)
- Fine-tuning after pruning is essential (lower LR)

## 5. Input Format

- Shape: `(batch, sequence_length, channels)` where channels = subcarriers
- ARIL: 192 time steps × 52 channels
- StanFi: 500 time steps × 30 channels
- **ESP32-S3 mapping:** ~200-400 time steps (4s window @ 50-100Hz) × 52 subcarriers → directly compatible

## 6. Implications for Our Project

### What This Proves
1. **Activity Recognition is highly feasible** — 4-class classification should easily achieve >95% accuracy with proper data collection and augmentation.
2. **Model can be extremely lightweight** — 57.8K params runs inference in milliseconds on any laptop.
3. **Data augmentation is non-optional** — Shifting alone gives +10% accuracy.
4. **No need for deep CNNs or Transformers** — Single GRU + attention is sufficient.

### What Remains Challenging
1. **Dataset collection** — Paper uses research NICs (Intel 5300). ESP32-S3 CSI is noisier. We need to collect our own labeled dataset in target environment.
2. **Label consistency** — Hand gesture datasets (ARIL, Sign-Fi) have clean boundaries. Real-world "walking" vs "static" can be ambiguous.
3. **Cross-domain generalization** — Models trained in one room may degrade in another (different multipath). Paper does not test cross-room.

### Recommended Adaptation
- Replace ResNet18 (Wallhack1.8k) with **GRU+Attention** (this paper)
- Implement shifting augmentation (±10 steps) as top priority
- Add MixUp and Gaussian noise for robustness
- Prune to ~50K params for sub-millisecond inference
- Target: 4 classes → expect ~95-98% accuracy with 200+ samples/class

## 7. Comparison with Wallhack1.8k

| Aspect | Wallhack1.8k | Attention-GRU (This Paper) |
|--------|--------------|---------------------------|
| Model | ResNet18 (11M params) | GRU+Attention (57K params) |
| Classes | 3 (empty, walk, wave) | 6-276 (gestures + activities) |
| Dataset | LOS/NLOS directional antennas | Omni research NICs |
| Augmentation | None | Shifting + MixUp + Noise |
| Best accuracy | ~90% (estimated) | 98.92% (ARIL) |
| Our choice | ❌ Overkill | ✅ Lightweight + proven |

## 8. Action Items

- [ ] Implement `AttentionGRU` model in PyTorch (~50 lines)
- [ ] Implement `ShiftAugment` transform (circular shift ±1..10 steps)
- [ ] Implement `MixUp` augmentation for CSI sequences
- [ ] Collect ESP32-S3 labeled dataset for 4 classes (target: 200 samples/class)
- [ ] Add pruning + fine-tuning pipeline after initial training

---
*Research synthesized: 2026-04-30*
