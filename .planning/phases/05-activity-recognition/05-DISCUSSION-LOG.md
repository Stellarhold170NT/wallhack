# Phase 5: Activity Recognition - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-05-01
**Phase:** 05-activity-recognition
**Mode:** default (interactive)
**Areas discussed:** Data Strategy, Input Format, Class Scope, Subcarrier Count, Window Size, Project Structure, Inference Integration, Data Collection, HAR Mapping, Model Architecture

## Discussion Summary

### Data Strategy
- **Question:** How to get labeled training data? Paper datasets are placeholders.
- **Options:** Collect real ESP32-S3 data / Download HAR + adapt / Hybrid pre-train + fine-tune
- **Selected:** Hybrid: HAR pre-train + ESP32 fine-tune
- **Rationale:** Balances speed (don't need 1400 manual samples) with accuracy (domain-adapted to ESP32-S3 environment)

### Input Format
- **Question:** Feed classifier raw amplitude or Phase 3 features?
- **Options:** Raw amplitude windows / Phase 3 features / Hybrid both
- **Selected:** Raw amplitude windows (like paper) + StandardScaler
- **Rationale:** Paper achieves 98.92% with raw amplitude + StandardScaler. No complex DSP needed for HAR.

### Class Scope (v1)
- **Question:** All 7 classes at once or phased rollout?
- **Options:** 4 static classes / All 7 / 5 static classes
- **Selected:** Start with 4 static classes (walk, run, lie, bend)
- **Rationale:** Easiest to collect and label. Get end-to-end working first. Transitions and falling deferred.

### Subcarrier Count
- **Question:** How to standardize 64/128/192 subcarriers from ESP32-S3?
- **Options:** Crop to 52 (HAR) / 64 (ESP32 default) / Dynamic
- **Selected:** Center-crop to 52 (HAR-compatible)
- **Rationale:** Enables direct HAR pre-training weight transfer. Core subcarriers preserved.

### Window Size
- **Question:** Window size for 10 fps ESP32-S3? Paper uses 200 frames @ 50 Hz.
- **Options:** 50 frames (~5s) / 30 frames (~3s) / Dual 30+60
- **Selected:** 50 frames (~5s @ 10 fps)
- **Rationale:** Long enough to capture activity pattern, short enough for responsive UI.

### Project Structure
- **Question:** Where does training code live?
- **Options:** `classifier/` package / Single script / Jupyter notebook
- **Selected:** `classifier/` package (train.py, infer.py, dataset.py, collect.py)
- **Rationale:** Clean separation from signal processing. Follows PyTorch conventions.

### Inference Integration
- **Question:** How to wire classifier into real-time pipeline?
- **Options:** Parallel task on raw Queue / Reuse processor / Fork after server
- **Selected:** Fork after server — raw frames to both processor and classifier
- **Rationale:** Both run in parallel, no dependency, most flexible.

### Data Collection
- **Question:** Workflow for collecting labeled ESP32-S3 fine-tuning data?
- **Options:** CLI tool / Post-hoc labeling / Presence-triggered auto-segment
- **Selected:** CLI tool: `python -m classifier.collect --label walking --duration 30`
- **Rationale:** Simple, scriptable, easy to use in home environment.

### HAR Mapping
- **Question:** HAR has 5 classes, we need 4. How to map for pre-training?
- **Options:** 4 matching classes only / Map stand/sit→bend / Generic pre-training
- **Selected:** Generic pre-training on all 5 HAR classes
- **Rationale:** Learn general CSI motion patterns, not exact label mapping. Fine-tune with correct 4-class labels.

### Model Architecture
- **Decision:** Replace CustomGRU with nn.GRU, skip pruning, hidden=128, attention=32, output=4
- **Rationale:** Per ROADMAP adaptation notes. ~82K params, <10ms CPU inference.

## Deferred Ideas

- Transitions (sitting down, standing up) — v1.1
- Falling detection — v1.1 (needs synthetic data)
- Model pruning — v2
- On-device inference — v2

---

*Discussion completed: 2026-05-01*
