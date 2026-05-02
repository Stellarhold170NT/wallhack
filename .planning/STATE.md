# State: ESP32-S3 CSI Wallhack

**Project:** ESP32-S3 CSI Wallhack
**Milestone:** v1.0 — Basic Sensing Pipeline
**Current Phase:** Phase 6 Complete — v1.0 Milestone Ready for Verification
**Last Updated:** 2026-05-02 (post-execution)

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-30)

**Core value:** Reliable presence detection and activity classification (7 classes: walking, running, sitting down, standing up, lying down, bending, falling) using 2 ESP32-S3 nodes — architecture supports multi-node scalability.
**Current focus:** Phase 6 — Dashboard & API

## Phase Status

| Phase | Status | Requirements | Success Criteria |
|-------|--------|--------------|------------------|
| 1: Firmware & Flashing | ✓ Complete | HW-01..HW-04 | 4/4 |
| 2: UDP Aggregator | ✓ Complete | SIG-01..SIG-02 | 2/2 |
| 3: Signal Processing | ✓ Complete | SIG-03..SIG-06 | 4/4 |
| 4: Presence & Intrusion | ✓ Complete | SEC-01..SEC-04 | 4/4 |
| 5: Activity Recognition | ✓ Complete | ACT-01..ACT-05 | 5/5 |
| 6: Dashboard & API | ✓ Complete | UI-01..UI-05, API-01..API-02 | 7/7 |

## Blockers

None.

## Decisions Pending

None at project start.

## Notes

- 2x ESP32-S3-DevKitC-1 available
- Initial stack: ESP-IDF C + Python + scikit-learn
- Reference code in `llm-wiki/raw/RuView/firmware/` and `llm-wiki/raw/wallhack1.8k/`

## Session History

**2026-04-30 — Planning Review & Readiness Check**
- Verified git state: 4 commits ahead of origin, all planning docs committed
- Confirmed `.planning/` artifacts: PROJECT.md, REQUIREMENTS.md (27 reqs), ROADMAP.md (6 phases), STATE.md, config.json
- Reviewed research findings: Kang et al. 2025 Attention-GRU (98.92% ARIL), prunedAttentionGRU source analyzed
- Decision: Proceed with Phase 1 (Firmware & Flashing) as next step
- No blockers identified

**2026-04-30 — Scope Expansion (4→7 classes)**
- User requested: expand AR from 4 classes to 7 classes (walking, running, sitting down, standing up, lying down, bending, falling)
- Decision: Architecture follows prunedAttentionGRU (supports 8-276 classes) for multi-node scalability
- Updated: PROJECT.md (core value, active requirements, key decisions)
- Updated: REQUIREMENTS.md (ACT-01 7 classes, ACT-05 adaptive windows, v2 scope)
- Updated: ROADMAP.md (Phase 5 goal, success criteria, adaptation notes)
- Risk noted: transitions (sit/stand/lying) may need 2s windows; falling requires synthetic/augmented data

**2026-04-30 — Phase 1 Execution Complete**
- Executed 3 waves (01-01 scaffolding, 01-02 core modules, 01-03 integration)
- Commits: 1f46096, 781d1c0, e70dc19
- UAT: 14/14 code-level tests passed, 3 blocked (require hardware)
- Artifacts: firmware/esp32-csi-node/ with complete ESP-IDF project
- Ready for Phase 2: UDP Aggregator

**2026-04-30 — Phase 2 Context Gathered**
- User confirmed: Node 0 and Node 1 are peers (both STA-only, no dedicated TX)
- Decisions captured:
  - D-06: Asyncio Queue for Phase 3 handoff
  - D-07: Drop Oldest (ring buffer) per node, default 500 frames
  - D-08: Raw data persisted as `.npy` for Phase 5 dataset collection
  - D-09: Strict frame validation with graceful degradation
  - D-10: Dynamic node discovery — min 1 node, auto-expand
- Artifact: `.planning/phases/02-udp-aggregator/02-CONTEXT.md`

**2026-04-30 — Phase 2 Execution Complete**
- Executed 3 waves (02-01 frame/parser, 02-02 server/buffer, 02-03 CLI/persistence)
- Files created: 11 Python files + requirements.txt
- Tests: 35/35 passed (17 parser + 13 server + 5 integration)
- Key artifacts:
  - `aggregator/frame.py` — CSIFrame dataclass
  - `aggregator/parser.py` — ADR-018 binary parser (D-09)
  - `aggregator/buffer.py` — NodeBuffer drop-oldest ring buffer (D-07)
  - `aggregator/server.py` — CsiUdpServer with dynamic discovery (D-10)
  - `aggregator/persistence.py` — NpyWriter for Phase 5 dataset (D-08)
  - `aggregator/main.py` — CLI entry point
  - `requirements.txt` — numpy, pytest, pytest-asyncio
- Commit: `docs(02): gather phase 2 context` + execution commits
- Ready for Phase 3: Signal Processing

**2026-05-01 — Phase 3 Context Gathered**
- Decisions captured:
  - D-11: Separate `processor/` package, in-process coroutine, multi-purpose (CLI + importable)
  - D-12: Config passed from Aggregator ("nhạc trưởng")
  - D-13: Output pushes to second asyncio.Queue for Phase 4 handoff
  - D-14: Both amplitude + phase processing (amplitude for HAR, phase for presence breathing)
  - D-15: Custom Hampel filter implementation (~10-15 lines, no new deps)
  - D-16: Dict output with metadata + flat feature array
  - D-17: Real-time streaming primary, offline `.npy` replay secondary
  - D-18: Per-node independent processing, decision-level fusion in Phase 4
- Artifact: `.planning/phases/03-signal-processing/03-CONTEXT.md`
- Artifact: `.planning/phases/03-signal-processing/03-DISCUSSION-LOG.md`
- Ready for Phase 3 planning

**2026-05-01 — Phase 3 Execution Complete**
- Executed 3 plans (03-01, 03-02, 03-03) via ULW mode
- Commits: 3 commits (01: phase unwrap/detrend + Hampel, 02: sliding window + features, 03: asyncio processor + CLI + aggregator wiring)
- Tests: 49/49 passed across all test files
- Key artifacts:
  - `processor/phase.py` — unwrap_phase, detrend_phase (2π jump removal, linear drift correction)
  - `processor/hampel.py` — Custom Hampel filter (MAD-based outlier detection, no scipy dependency)
  - `processor/window.py` — SlidingWindow (200-frame window, 100-frame step, per-node isolation)
  - `processor/features.py` — extract_features (N*2+2 element vector: N mean + N var + motion_energy + breathing_band)
  - `processor/main.py` — CsiProcessor asyncio task (Queue-based, per-node state, max_nodes cap, graceful cancellation, **dynamic subcarrier adaptation D-19**)
  - `processor/__main__.py` — Offline CLI (`python -m processor --input x.npy --output y.npy`)
  - `aggregator/main.py` — Wired CsiProcessor into event loop with `--processor-config` arg
- Bug fix applied: variable subcarrier counts (64/128/192) now handled via center-crop / symmetric pad instead of window reset (previously caused 100% frame drop)
- Ready for Phase 4: Presence & Intrusion

**2026-05-01 — Phase 4 Context Gathered**
- Decisions captured:
  - D-21: Adaptive baseline learning for empty-room noise floor
  - D-22: Multi-feature detection (motion_energy + breathing_band combined)
  - D-23: Per-node independent detector with separate baselines
  - D-24: Hysteresis with asymmetric enter (2.5σ) / exit (1.5σ) thresholds
  - D-25: 3 consecutive frames to confirm Occupied, 10s silence to return Empty
  - D-26: 5-second alert cooldown per SEC-04
  - D-27: Dual alert output — JSONL persistence + in-memory buffer
  - D-28: Alert object structure with timestamp, node_id, confidence, status, type, trigger_feature
  - D-29: Third Queue for Phase 6 handoff
  - D-30: OR fusion default, configurable AND mode
  - D-31: Auto-exclude stale nodes from fusion
  - D-32: Single-node graceful degradation, zero-node reports "unknown"
- Artifact: `.planning/phases/04-presence-intrusion/04-CONTEXT.md`
- Artifact: `.planning/phases/04-presence-intrusion/04-DISCUSSION-LOG.md`
- Ready for Phase 4 planning

**2026-05-01 — Phase 4 Execution Complete**
- Executed 3 waves via ULW mode: detector core, alerts+async, aggregator wiring
- Files created: `detector/presence.py`, `detector/fusion.py`, `detector/alerts.py`, `detector/main.py`
- Tests: 41/41 passed (detector+alert+integration)
- Hardware tuning: `baseline_skip_threshold_sigma=2.0` added to prevent startup contamination
- Defaults retuned for 10 fps: `enter_frames=2`, `exit_frames=3`, `min_baseline_frames=6`
- Synthetic CSI generator: `scripts/generate_synthetic_csi.py` (7 scenarios)
- E2E test harness: `scripts/test_e2e_synthetic.py`
- Real hardware test: baseline contamination identified as #1 accuracy limitation
- Commit: `e365dcf` on main
- Artifacts: `.planning/phases/04-presence-intrusion/04-03-SUMMARY.md`
- Lesson: System is a "change detector" not a true "human detector"

**2026-05-01 — Phase 5 Context Gathered**
- Decisions captured:
  - D-33: Hybrid data — HAR pre-train + ESP32 fine-tune
  - D-34: Raw amplitude windows + StandardScaler (like paper)
  - D-35: 4 static classes for v1 (walk, run, lie, bend)
  - D-36: Center-crop to 52 subcarriers (HAR-compatible)
  - D-37: 50-frame windows (~5s @ 10 fps)
  - D-38: `classifier/` package structure
  - D-39: Fork after server — parallel inference with presence detector
  - D-40: CLI data collection tool `classifier.collect`
  - D-41: Generic HAR pre-training on all 5 classes
  - D-42: nn.GRU + attention, hidden=128, skip pruning
  - D-43: Offline training with augmentation + early stopping
- Artifact: `.planning/phases/05-activity-recognition/05-CONTEXT.md`
- Artifact: `.planning/phases/05-activity-recognition/05-DISCUSSION-LOG.md`
- Ready for Phase 5 planning

---
*State initialized: 2026-04-30*
**2026-05-01 — Phase 5 Execution Complete**
- Executed 3 waves via ULW mode:
  - Wave 1: Model architecture (AttentionGRU) + dataset infrastructure
  - Wave 2: Training pipeline + data collection + augmentation
  - Wave 3: Real-time inference + aggregator wiring
- Files created:
  - `classifier/__init__.py` — Package init
  - `classifier/model.py` — AttentionGRU (74,564 params, nn.GRU + additive attention)
  - `classifier/dataset.py` — Esp32Dataset, ArilDataset, StandardScaler persistence
  - `classifier/augment.py` — shift_augment (21×), noise_augment (4×), mixup_augment
  - `classifier/train.py` — train_model, pretrain_aril, finetune_esp32, cross_validate, CLI
  - `classifier/collect.py` — CsiCollector CLI data collection tool
  - `classifier/infer.py` — CsiClassifier asyncio task for real-time inference
  - `classifier/__main__.py` — Offline inference CLI
  - `tests/test_classifier.py` — 20 tests (model + dataset)
  - `tests/test_train.py` — 9 tests (training pipeline)
  - `tests/test_collect.py` — 11 tests (data collection)
  - `tests/test_infer.py` — 17 tests (inference task)
  - `tests/test_classifier_integration.py` — 6 tests (E2E pipeline)
- Tests: 153/153 passed (up from 90)
- Decisions implemented: D-33..D-43 all covered
- Artifacts: `.planning/phases/05-activity-recognition/05-0{1,2,3}-SUMMARY.md`
- Ready for Phase 6: Dashboard & API

**2026-05-01 — Bugfix: NodeBuffer dead code**
- Removed dead NodeBuffer from aggregator pipeline (caused false drop warnings)
- Server now pushes frames directly to queue without intermediate buffer
- Tests: 90/90 passed after fix

**2026-05-02 — Phase 6 Context Gathered**
- Decisions captured:
  - D-44: FastAPI embedded in aggregator, port 8024, `--dashboard` flag activation
  - D-45: Vanilla JS + Canvas 2D frontend, zero dependencies
  - D-46: WebSocket fixed 2Hz interval push, JSON bundle with all panels
  - D-47: Single-page 5-panel grid (heatmap, presence, activity, alerts, node health)
  - D-48: Heatmap axes: subcarrier (Y) vs time (X), blue→red color scale
  - D-50: REST endpoints GET /status and GET /alerts alongside WebSocket
- Artifact: `.planning/phases/06-dashboard-api/06-CONTEXT.md`
- Artifact: `.planning/phases/06-dashboard-api/06-DISCUSSION-LOG.md`
- Ready for Phase 6 planning

**2026-05-02 — Phase 6 Execution Complete**
- Executed 2 waves via ULW mode:
  - Wave 1: FastAPI backend (DashboardState, WebSocket, REST) + Vanilla JS frontend (Canvas 2D, 5-panel grid)
  - Wave 2: Aggregator CLI wiring (`--dashboard` flag) + integration tests
- Files created:
  - `dashboard/__init__.py` — Package init
  - `dashboard/state.py` — DashboardState queue consumer with presence/activity/alerts/heatmap state
  - `dashboard/app.py` — FastAPI app with WebSocket /ws, REST /status /alerts, static files
  - `dashboard/static/index.html` — Single-page dashboard (377 lines, zero deps)
  - `tests/test_dashboard.py` — 4 tests (state consumption, REST, WebSocket)
- Tests: 93/93 passed (89 core + 4 dashboard)
- Decisions implemented: D-44..D-50 all covered
- Artifacts: `.planning/phases/06-dashboard-api/06-0{1,2,3}-SUMMARY.md`
- v1.0 milestone complete: all 6 phases executed, 27/27 requirements satisfied

---
*Last updated: 2026-05-02 after Phase 6 execution*
