# Roadmap: ESP32-S3 CSI Wallhack

**Project:** ESP32-S3 CSI Wallhack
**Milestone:** v1.0 — Basic Sensing Pipeline
**Granularity:** Standard (6 phases)
**Mode:** Interactive

---

## Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Firmware & Flashing | Get both ESP32-S3 nodes streaming real CSI over UDP | HW-01..HW-04 | 4 |
| 2 | UDP Aggregator | Build Python asyncio server that ingests 2-node CSI streams | SIG-01..SIG-02 | 2 |
| 3 | Signal Processing | Clean and feature-extract CSI for presence detection | SIG-03..SIG-06 | 4 |
| 4 | Presence & Intrusion | Detect occupancy and emit alerts | SEC-01..SEC-04 | 4 |
| 5 | Activity Recognition | Collect data and train 4-class Attention-GRU classifier | ACT-01..ACT-05 | 5 |
| 6 | Dashboard & API | Real-time web UI with heatmap, status, alerts | UI-01..UI-05, API-01..API-02, ACT-06 | 8 |

**Total:** 6 phases | 27 requirements | 27 success criteria

---

## Phase Details

### Phase 1: Firmware & Flashing

**Goal:** Both ESP32-S3 nodes capture and stream CSI to aggregator.

**Requirements:** HW-01, HW-02, HW-03, HW-04

**Success Criteria:**
1. `idf.py build` succeeds for `firmware/esp32-csi-node/` producing `esp32-csi-node.bin`
2. `esptool.py flash` succeeds on both boards; boards boot and connect to WiFi
3. `provision.py` can set SSID, password, and target IP without recompiling
4. Wireshark/tcpdump captures UDP packets on port 5005 containing magic `0xC511_0001` from both node IDs

**Phase boundary:**
- IN: Source code, ESP-IDF v5.2, 2x ESP32-S3 boards
- OUT: Two nodes streaming validated binary CSI frames to aggregator IP

**Canonical refs:**
- `llm-wiki/raw/RuView/firmware/esp32-csi-node/` — reference firmware structure
- `llm-wiki/raw/RuView/docs/adr/ADR-018-esp32-dev-implementation.md` — binary frame format
- `llm-wiki/raw/RuView/docs/adr/ADR-012-esp32-csi-sensor-mesh.md` — mesh architecture

**Depends on:** None (first phase)

**Plans:** 3 plans

Plans:
- [ ] 01-01-PLAN.md — Project scaffolding and header files
- [ ] 01-02-PLAN.md — Core C modules (NVS config, CSI collector, UDP sender)
- [ ] 01-03-PLAN.md — Integration (main.c), provisioning tool, build scripts, verification

---

### Phase 2: UDP Aggregator

**Goal:** Python server receives, parses, and buffers CSI from both nodes.

**Requirements:** SIG-01, SIG-02

**Success Criteria:**
1. `python aggregator.py --port 5005` starts without errors
2. Receives UDP frames from 2 nodes concurrently at ≥20 Hz each
3. Parser validates magic and produces structured object with node_id, sequence, RSSI, noise_floor, amplitudes[N], phases[N] where N is dynamic (64/128/192)
4. Logs frame rate per node and detects packet loss via sequence gaps

**Phase boundary:**
- IN: Valid UDP stream from Phase 1
- OUT: Structured CSI frames in Python ready for DSP

**Canonical refs:**
- `llm-wiki/raw/RuView/docs/adr/ADR-028-esp32-capability-audit.md` §3.4 — data flow

**Depends on:** Phase 1

**Plans:** 3 plans

Plans:
- [ ] 02-01-PLAN.md — Frame dataclass and binary parser with unit tests
- [ ] 02-02-PLAN.md — Asyncio UDP server, dynamic discovery, and ring buffer
- [ ] 02-03-PLAN.md — CLI entry point, .npy persistence, and integration tests

---

### Phase 3: Signal Processing

**Goal:** Clean raw CSI and extract features for presence detection. For Activity Recognition, minimal preprocessing (amplitude + scaler) is sufficient per Kang et al. 2025 source code analysis.

**Requirements:** SIG-03, SIG-04, SIG-05, SIG-06

**Success Criteria:**
1. Phase unwrapping removes 2π jumps; linear detrend reduces drift
2. Hampel filter reduces spike amplitude by >80% on synthetic spikes
3. 4-second sliding window (200 frames @ 50 Hz) produces amplitude matrix [N subcarriers × 200 time], where N is anchored to first frame (64/128/192)
4. Feature vector computed per window: mean_amp, variance, motion_energy (0.5-3 Hz band power), breathing_band (0.1-0.5 Hz)
5. Variable subcarrier counts (64/128/192) are handled gracefully via crop/pad adaptation without window resets or frame drops

**Phase boundary:**
- IN: Structured raw CSI frames
- OUT: Clean feature vectors per 4-second window

**Canonical refs:**
- `llm-wiki/raw/RuView/docs/adr/ADR-014-sota-signal-processing.md` — algorithms
- `llm-wiki/raw/wallhack1.8k/datasets.py` — amplitude extraction pattern
- `llm-wiki/raw/prunedAttentionGRU/ARIL/aril.py` — StandardScaler normalization proven sufficient for HAR

**Note:** Activity Recognition does NOT require phase unwrap, Hampel, or spectrogram. Raw amplitude + StandardScaler achieves 98.92% (ARIL). Advanced DSP is only required for presence/intrusion detection robustness.

**Depends on:** Phase 2

**Plans:** 3 plans

Plans:
- [x] 03-01-PLAN.md — Phase sanitization (unwrap, detrend) and Hampel outlier filter with tests
- [x] 03-02-PLAN.md — Sliding window buffer and feature extraction (mean, variance, band power)
- [x] 03-03-PLAN.md — Asyncio CsiProcessor task, per-node state, Queue wiring, offline CLI

---

### Phase 4: Presence & Intrusion

**Goal:** Detect human presence and emit intrusion alerts.

**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04

**Success Criteria:**
1. Presence detector reports "occupied" within 5 seconds of person entering room (≥90% true positive)
2. Empty room reports "empty" with ≤5% false positive over 10-minute test
3. 2-node fusion: presence reported if either node detects (configurable AND/OR)
4. Intrusion alert fires once per entry event with 5-second cooldown; logged to JSONL file

**Phase boundary:**
- IN: Feature vectors from Phase 3
- OUT: Presence state + alert stream

**Canonical refs:**
- `llm-wiki/raw/RuView/docs/adr/ADR-012-esp32-csi-sensor-mesh.md` §Sensing Capabilities — 1-node presence is "Good"

**Depends on:** Phase 3

**Plans:** 3 plans

Plans:
- [ ] 04-01-PLAN.md — Core detection engine (adaptive baseline, hysteresis, multi-node fusion)
- [ ] 04-02-PLAN.md — Alert system (cooldown, JSONL persistence, in-memory buffer) + CsiDetector async task
- [ ] 04-03-PLAN.md — Aggregator wiring (third Queue, node health handoff, graceful shutdown) + integration tests

---

### Phase 5: Activity Recognition

**Goal:** Train and deploy a 4-class activity classifier using proven Attention-GRU architecture. Architecture designed for multi-node scalability (supports 8-276 classes).

**Requirements:** ACT-01, ACT-02, ACT-03, ACT-04, ACT-05

**Success Criteria:**
1. Dataset contains ≥200 samples per class (walking, running, lying down, bending) collected in target environment.
2. Attention-GRU model adapted from Kang et al. 2025 source (`nn.GRU` 128 hidden + attention 32 hidden, ~82K params) trains successfully
3. Data augmentation implemented: `np.roll` shifting (±10 steps, 20×), MixUp (30% prob, α=1.0), multiplicative Gaussian noise (3×)
4. Model achieves ≥85% accuracy on held-out test set (5-fold cross-validation) with ESP32-S3 CSI. Architecture proven at 99.33% (StanFi 6-class) and 100% (Nexmon HAR 8-class) on research NICs.
5. Inference latency <10 ms per sample on laptop CPU (< 1M FLOPs)

**Phase boundary:**
- IN: Labeled CSI amplitude matrices `(samples, time_steps, N)` where N is the anchored subcarrier count (typically 52)
- OUT: Trained `model.pth` + real-time inference pipeline

**Canonical refs:**
- `llm-wiki/raw/prunedAttentionGRU/PrunedAttentionGRU.py` — model architecture (78 lines)
- `llm-wiki/raw/prunedAttentionGRU/train.py` — training loop with MixUp
- `llm-wiki/raw/prunedAttentionGRU/augmentation.py` — shifting + noise augmentation
- `llm-wiki/raw/prunedAttentionGRU/ARIL/aril.py` — 52-subcarrier input format
- `llm-wiki/raw/prunedAttentionGRU/HAR/har.py` — 4-class dataset loader reference

**Adaptation notes:**
- Replace `CustomGRU` (slow hand-written loop) with `nn.GRU` (10× speedup, cuDNN optimized)
- Skip pruning code — unnecessary for our scale (v1). Architecture supports 8-276 classes natively for multi-node expansion.
- Center-crop to 52 subcarriers for ARIL compatibility
- 50-frame windows (~5s at 10 fps)
- Add validation split + early stopping (missing from original code)

**Depends on:** Phase 2 (data collection can start as soon as aggregator works; minimal preprocessing needed)

**Plans:** 3 plans

Plans:
- [ ] 05-01-PLAN.md — Model architecture (AttentionGRU) + dataset infrastructure (ESP32 + ARIL loaders + StandardScaler)
- [ ] 05-02-PLAN.md — Training pipeline (augmentation + ARIL pre-train + ESP32 fine-tune + cross-validation) + CLI data collection tool
- [ ] 05-03-PLAN.md — Real-time inference (CsiClassifier asyncio task) + aggregator wiring + offline inference CLI

---

### Phase 6: Dashboard & API

**Goal:** Real-time web dashboard visualizing CSI, presence, activity, and alerts.

**Requirements:** UI-01..UI-05, API-01..API-02

**Success Criteria:**
1. Browser loads dashboard at `http://localhost:8080` and shows CSI amplitude heatmap updating every 0.5s
2. Presence indicator changes color within 2 seconds of state change
3. Activity label updates with confidence bar; matches classifier output
4. Alert panel displays intrusion events with timestamp and node ID
5. WebSocket delivers updates to browser at 2 Hz without lag
6. `GET /status` returns JSON with presence, activity, node health
7. `GET /alerts` returns last 50 alerts

**Phase boundary:**
- IN: Presence state, activity labels, alert stream
- OUT: Complete web UI serving all sensing outputs

**Canonical refs:**
- `llm-wiki/raw/RuView/docs/adr/ADR-019-sensing-only-ui-mode.md` — sensing UI patterns

**Depends on:** Phase 4, Phase 5

---

## Dependency Graph

```
Phase 1 (Firmware)
    │
    ▼
Phase 2 (Aggregator)
    │
    ▼
Phase 3 (Signal Processing)
    │
    ├──▶ Phase 4 (Presence & Intrusion)
    │         │
    │         ▼
    │    Phase 6 (Dashboard)
    │
    └──▶ Phase 5 (Activity Recognition)
              │
              ▼
         Phase 6 (Dashboard)
```

**Parallelizable:**
- Phase 4 and Phase 5 data collection can overlap (both need Phase 3 features)
- Phase 6 frontend mockup can start once Phase 4/5 APIs are defined

---

## Anti-Features (Deliberately Not Built)

To prevent scope creep, these are explicitly out of v1:

- No cloud connectivity — all local
- no on-device inference for v1 — ESP32 streams raw CSI only. On-device feasible in v2 (328KB model < 520KB SRAM) but requires C port.
- No heart rate / breathing BPM display — unreliable on ESP32-S3
- No people counter — needs 3-6 nodes minimum
- No pose skeleton — needs DensePose model + camera ground truth
- No mobile app — web dashboard only

---

## Evolution

This roadmap evolves:
- After each phase: update REQUIREMENTS.md traceability
- After v1.0 milestone: review Out of Scope, consider v2 features if hardware expands

---
*Roadmap created: 2026-04-30*
*Last updated: 2026-05-01 after Phase 3 completion + subcarrier adaptation bugfix*
