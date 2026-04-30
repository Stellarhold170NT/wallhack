# State: ESP32-S3 CSI Wallhack

**Project:** ESP32-S3 CSI Wallhack
**Milestone:** v1.0 — Basic Sensing Pipeline
**Current Phase:** Phase 2 Complete — Ready for Phase 3
**Last Updated:** 2026-04-30

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-30)

**Core value:** Reliable presence detection and activity classification (7 classes: walking, running, sitting down, standing up, lying down, bending, falling) using 2 ESP32-S3 nodes — architecture supports multi-node scalability.
**Current focus:** Phase 2 — UDP Aggregator

## Phase Status

| Phase | Status | Requirements | Success Criteria |
|-------|--------|--------------|------------------|
| 1: Firmware & Flashing | ✓ Complete | HW-01..HW-04 | 4/4 |
| 2: UDP Aggregator | ✓ Complete | SIG-01..SIG-02 | 2/2 |
| 3: Signal Processing | 🔴 Not started | SIG-03..SIG-06 | 0/4 |
| 4: Presence & Intrusion | 🔴 Not started | SEC-01..SEC-04 | 0/4 |
| 5: Activity Recognition | 🔴 Not started | ACT-01..ACT-05 | 0/5 |
| 6: Dashboard & API | 🔴 Not started | UI-01..UI-05, API-01..API-02 | 0/7 |

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

---
*State initialized: 2026-04-30*
*Last updated: 2026-04-30 after Phase 1 execution*
