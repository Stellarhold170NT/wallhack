# State: ESP32-S3 CSI Wallhack

**Project:** ESP32-S3 CSI Wallhack
**Milestone:** v1.0 — Basic Sensing Pipeline
**Current Phase:** Planning Complete — Ready for Phase 1
**Last Updated:** 2026-04-30

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-30)

**Core value:** Reliable presence detection and activity classification (7 classes: walking, running, sitting down, standing up, lying down, bending, falling) using 2 ESP32-S3 nodes — architecture supports multi-node scalability.
**Current focus:** Phase 1 — Firmware & Flashing

## Phase Status

| Phase | Status | Requirements | Success Criteria |
|-------|--------|--------------|------------------|
| 1: Firmware & Flashing | 🔴 Not started | HW-01..HW-04 | 0/4 |
| 2: UDP Aggregator | 🔴 Not started | SIG-01..SIG-02 | 0/2 |
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

---
*State initialized: 2026-04-30*
*Last updated: 2026-04-30 after scope expansion (4→7 classes)*
