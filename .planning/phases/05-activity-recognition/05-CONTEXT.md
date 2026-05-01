# Phase 5: Activity Recognition - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Train and deploy a 4-class activity classifier using proven Attention-GRU architecture. Start with static activities; transitions and falling deferred to v1.1.

**Phase boundary:**
- IN: Raw CSI amplitude frames from Phase 2 (UDP aggregator) + labeled dataset from collection tool
- OUT: Trained `model.pth` + real-time inference pipeline emitting activity labels with confidence

**Requirements:** ACT-01, ACT-02, ACT-03, ACT-04, ACT-05

**Scope limit:** 4 classes for v1 (walking, running, lying down, bending). Transitions (sit down, stand up) and falling are deferred.

</domain>

<decisions>
## Implementation Decisions

### Data Strategy
- **D-33:** Hybrid data approach — HAR pre-train + ESP32 fine-tune
  - Download HAR dataset (~1000 samples, 6 classes) for pre-training
  - Collect ~50-100 samples per class from ESP32-S3 for fine-tuning
  - HAR provides generic motion feature learning; ESP32 data adapts to target environment
  - Balances speed (don't need 1400 manual samples) with accuracy (domain-adapted)

### Input Format & Preprocessing
- **D-34:** Raw amplitude windows + StandardScaler (following paper)
  - Input shape: `(batch, time_steps, 52)` — time-series amplitude matrix
  - No Hampel filter, no phase unwrap, no spectrogram for AR path
  - StandardScaler normalization per subcarrier (fit on training data, persist scaler)
  - Separate preprocessing path from Phase 3 (presence uses features, AR uses raw amplitude)

### Class Scope (v1)
- **D-35:** Start with 4 static classes: walking, running, lying down, bending
  - Static poses/actions are easier to collect and label consistently
  - Transitions (sitting down, standing up) need 2s windows and precise timing — deferred to v1.1
  - Falling is hard to collect safely — deferred to v1.1 with synthetic/augmented data
  - Architecture supports 8-276 classes natively for future expansion

### Model Input Dimensions
- **D-36:** Center-crop subcarriers to 52 (HAR-compatible)
  - ESP32-S3 sends 64/128/192 subcarriers; crop center 52 to match HAR format
  - Core subcarriers preserved; edge subcarriers (often noisy) discarded
  - Enables direct HAR pre-training weight transfer

### Window Size
- **D-37:** 50-frame windows (~5 seconds at 10 fps)
  - Paper uses 200 frames @ 50 Hz = 4s; adapted to ESP32-S3's ~10 fps
  - Long enough to capture activity pattern, short enough for responsive UI
  - Sliding window with 25-frame step (~2.5s overlap) for continuous classification

### Project Structure
- **D-38:** `classifier/` package with dedicated modules
  - `classifier/train.py` — training loop with early stopping, validation split
  - `classifier/infer.py` — real-time inference task (asyncio-friendly)
  - `classifier/dataset.py` — ESP32 dataset loader + HAR adapter
  - `classifier/collect.py` — CLI data collection tool
  - `classifier/model.py` — Attention-GRU architecture (nn.GRU + attention)

### Inference Integration
- **D-39:** Fork after server — raw frames to both processor and classifier
  - UDP server pushes frames to `raw_queue` (existing) AND new `amplitude_queue`
  - `CsiProcessor` consumes `raw_queue` → presence detection (Phase 4)
  - `classifier/infer.py` consumes `amplitude_queue` → activity labels
  - Both run as parallel asyncio tasks in aggregator event loop
  - Classifier emits activity dict to new `activity_queue` for Phase 6 handoff

### Data Collection Workflow
- **D-40:** CLI tool for structured collection
  - Command: `python -m classifier.collect --label walking --duration 30 --output data/activities/`
  - Records UDP frames for specified duration, saves as `.npy` with metadata
  - Each recording: `data/activities/{label}/{timestamp}_{node_id}.npy`
  - Metadata JSON sidecar: label, duration, node_id, subcarrier_count, sample_count
  - Later converted to training dataset via `classifier/dataset.py`

### HAR Pre-training Strategy
- **D-41:** Generic pre-training on all 6 HAR classes
  - Use all HAR classes (walk, stand, sit, lie, run, clean) for pre-training
  - Goal: learn general CSI motion patterns, not exact label mapping
  - Fine-tune on ESP32-S3 data with correct 4-class labels
  - Transfer learning: first layer features transfer, final FC layer retrained

### Model Architecture
- **D-42:** Adapted from Kang et al. 2025 with simplifications
  - Replace `CustomGRU` with `nn.GRU` (cuDNN optimized, 10× speedup)
  - Hidden dim: 128, Attention dim: 32 (paper defaults)
  - Skip pruning for v1 — unnecessary at our scale
  - Output dim: 4 (v1 classes)
  - ~82K parameters, <10ms inference on laptop CPU

### Training Pipeline
- **D-43:** Offline training with augmentation
  - Data augmentation: `np.roll` shifting (±10 steps, 20×), multiplicative Gaussian noise (3×)
  - MixUp optional (30% prob, α=1.0) — implement if baseline accuracy <80%
  - Validation split: 20% held-out test set
  - Early stopping: patience=10 epochs on validation loss
  - 5-fold cross-validation for final accuracy report

### the agent's Discretion
- Exact HAR download and parsing implementation
- Scaler persistence format (pickle, JSON, or numpy)
- Activity Queue format and bounded size
- Whether to include confidence thresholding (emit "unknown" if max confidence < 0.5)
- Learning rate schedule details
- Batch size (paper uses 128; may reduce for smaller dataset)

</decisions>

<specifics>
## Specific Ideas

- "Dùng HAR để pre-train rồi fine-tune trên ESP32-S3 của mình — nhanh hơn thu thập 1400 mẫu" — hybrid data strategy
- "Raw amplitude + StandardScaler là đủ, paper đạt 98.92% không cần DSP phức tạp" — keep preprocessing simple
- "4 class tĩnh trước, transitions và falling sau" — phased class rollout
- "Fork sau server để classifier chạy song song detector, không làm chậm pipeline" — parallel inference
- "CLI collect để dễ dàng thu thập data trong nhà" — simple data collection

</specifics>

<canonical_refs>
## Canonical References

### Model Architecture
- `llm-wiki/raw/prunedAttentionGRU/PrunedAttentionGRU.py` — 78-line model (CustomGRU + MaskedAttention)
- `llm-wiki/raw/prunedAttentionGRU/MaskedAttention.py` — Self-attention module (32-dim context vector)
- `llm-wiki/raw/prunedAttentionGRU/train.py` — Training loop with MixUp reference
- `llm-wiki/raw/prunedAttentionGRU/augmentation.py` — np.roll shift + noise augmentation

### Dataset Reference
- `llm-wiki/raw/prunedAttentionGRU/HAR/har.py` — HAR dataset loader (52 subcarriers)
- `llm-wiki/raw/prunedAttentionGRU/premodel.py` — Dataset selection and loader setup
- HAR download: https://ieee-dataport.org/open-access/csi-human-activity

### Existing Pipeline
- `aggregator/server.py` — UDP server, NodeBuffer, frame distribution
- `aggregator/main.py` — Event loop wiring, Queue creation
- `processor/window.py` — SlidingWindow (200-frame, 100-step) — AR uses separate 50-frame window
- `.planning/phases/04-presence-intrusion/04-CONTEXT.md` — D-30 (OR fusion), D-31 (stale exclusion)

### Requirements
- `.planning/REQUIREMENTS.md` — ACT-01..ACT-05

### Architecture Decision
- `.planning/ROADMAP.md` §Phase 5 — Adaptation notes (CustomGRU→nn.GRU, skip pruning, esp32_dataset.py)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aggregator/server.py:datagram_received` — already pushes frames to Queue; can push to second Queue for classifier
- `aggregator/persistence.py:NpyWriter` — `.npy` serialization pattern for dataset collection
- `processor/window.py:SlidingWindow` — circular buffer pattern; classifier needs similar but 50-frame window
- `detector/main.py:CsiDetector` — asyncio task pattern for real-time inference; mirror for classifier
- `scripts/generate_synthetic_csi.py` — UDP injection pattern for testing classifier without hardware

### Established Patterns
- Asyncio task in aggregator event loop (CsiProcessor, CsiDetector) — classifier follows same pattern
- Per-node state dict keyed by `node_id` — classifier maintains per-node SlidingWindow
- Queue-based producer/consumer — classifier consumes from amplitude_queue, emits to activity_queue
- Config dict passthrough via CLI `--detector-config` — use `--classifier-config` for model params

### Integration Points
- Phase 2 → Phase 5: New `amplitude_queue` created in `aggregator/main.py`, filled by server
- Phase 5 → Phase 6: New `activity_queue` for real-time activity labels + confidence
- Phase 5 data → Phase 5 training: `classifier/collect.py` writes to `data/activities/`, `classifier/dataset.py` loads
- Phase 3 and Phase 5 are parallel consumers of raw frames — no dependency between them

</code_context>

<deferred>
## Deferred Ideas

- **Transitions (sitting down, standing up)** — v1.1; need 2s windows and precise timing
- **Falling detection** — v1.1; hard to collect safely, may need synthetic data or accelerometer ground truth
- **Model pruning** — v2; skip for v1 per ROADMAP adaptation notes
- **On-device inference (ESP32-S3)** — v2; model is 328KB, SRAM is 520KB, theoretically feasible but requires C port
- **Multi-node activity fusion** — v2; fuse activity labels from 2 nodes for spatial coverage
- **Auto-labeling via presence detector** — future; use Phase 4 to auto-segment active periods for labeling
- **Cross-dataset evaluation (StanFi, SignFi)** — research extension; focus on HAR + ESP32 for v1

</deferred>

---

*Phase: 05-activity-recognition*
*Context gathered: 2026-05-01*
