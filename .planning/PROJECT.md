# ESP32-S3 CSI Wallhack

## What This Is

A practical WiFi CSI sensing system built on ESP32-S3 that detects human presence, classifies basic activities, and streams real-time Channel State Information — without cameras or wearables. Designed for a 2-node deployment, it avoids unreliable features (heart rate, people counting) that require research-grade hardware or dense mesh arrays.

## Core Value

Reliable presence detection and activity classification (7 classes: walking / running / sitting down / standing up / lying down / bending / falling) using 2 ESP32-S3 nodes and a laptop aggregator — architecture designed for multi-node scalability.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] CSI realtime streaming from 2 ESP32-S3 nodes via UDP
- [ ] Presence and intrusion detection with low false-positive rate
- [ ] Activity recognition for 7 classes (walking, running, sitting down, standing up, lying down, bending, falling) — architecture supports 8-276 classes for future multi-node expansion
- [ ] Real-time web dashboard showing CSI heatmap + alerts
- [ ] Signal processing pipeline (phase sanitize, Hampel filter, spectrogram)

### Out of Scope

- **People counting** — Requires 3-6+ nodes for spatial diversity; 2 nodes yield marginal accuracy (ADR-012).
- **Heart rate / breathing analysis** — ESP32-S3 CSI SNR is insufficient for consistent cardiac extraction (ADR-021, ADR-028). Breathing is possible but placement-sensitive and unreliable.
- **Pose estimation / DensePose** — Needs multi-node mesh (4-6 nodes) + trained transformer/GNN models.
- **Multi-person tracking** — Single-TX-RX pair cannot separate individuals.
- **Edge ML inference on ESP32** — On-device inference is not implemented even in mature projects like RuView (ADR-028 audit).
- **Through-wall depth estimation** — Fresnel modeling requires calibrated antenna arrays.

## Context

- **Hardware**: 2x ESP32-S3-DevKitC-1 (~$20 total)
- **Aggregator**: Laptop/PC running Python (Windows/Linux/macOS)
- **Stack**: ESP-IDF C (firmware) → Python asyncio (aggregator) → numpy/scipy (DSP) → PyTorch (GRU+Attention HAR) → Flask/FastAPI + WebSocket (dashboard)
- **Reference projects**:
  - RuView (Rust, ~21k LOC, 65 WASM modules — too heavy for 2-node hobby setup)
  - Wallhack1.8k (PyTorch dataloader, 3-class ResNet18)
  - **Kang et al. 2025** (GRU+Attention, 57.8K params, 98.92% on ARIL in paper — **source code analyzed and confirmed runnable**; we use HAR dataset for pre-training)
- **CSI format**: ESP-IDF `wifi_csi_info_t`, 52-56 subcarriers, I/Q pairs, 20-100 Hz sampling
- **Model input**: `(batch, time_steps, 52)` amplitude matrix — directly compatible with HAR dataset format

## Constraints

- **Hardware**: Only 2 ESP32-S3 nodes. No Intel 5300 / Atheros NICs. No Cognitum Seed.
- **Accuracy ceiling**: ESP32-S3 consumer-grade CSI is noisier than research NICs. We accept "good enough" for presence/motion, not medical/clinical precision.
- **Time**: 6 weeks target for v1.
- **ML data**: No custom dataset yet. Kang et al. 2025 source code (analyzed) proves the model is only **78 lines** and uses raw amplitude + StandardScaler — no complex DSP needed for HAR. Model achieves 99.33% on 6-class StanFi dataset. Data collection (6 classes × 200 samples) is the only remaining bottleneck.
- **Compute**: Inference on laptop (< 1ms CPU). On-device inference (ESP32-S3, 520KB SRAM) theoretically possible (328KB model) but deferred to v2.
- **Activity Recognition risk**: **Low** — codebase exists, 52-subcarrier match, 7-class daily activities + transitions (StanFi/HAR style) feasible. Model supports 8-276 classes natively for multi-node expansion.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python backend (not Rust) | Faster iteration, rich DSP/ML libraries, team familiarity | — Pending |
| GRU+Attention model (not ResNet18/SVM) | Kang et al. 2025 source code analyzed: 78-line model, 82K params, raw amplitude + StandardScaler input. 52 subcarriers match ESP32-S3 exactly. 7-class daily activities + transitions (StanFi/HAR). Model supports 8-276 classes natively. Replaces Wallhack1.8k's ResNet18. | — Pending |
| 2-node feature-level fusion (not signal-level) | Clock drift (~20-50 ppm) makes cross-node phase alignment impossible. Fuse decisions/features, not raw I/Q (ADR-012). | — Pending |
| Skip heart rate & people counting | ADR-012 and ADR-021 explicitly mark these as unreliable on ESP32-S3. Avoid wasted effort. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-30 after scope expansion (4→6 classes)*
