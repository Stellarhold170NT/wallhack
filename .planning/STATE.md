# State: ESP32-S3 CSI Wallhack

**Project:** ESP32-S3 CSI Wallhack
**Milestone:** v1.0 — Basic Sensing Pipeline
**Current Phase:** Not started
**Last Updated:** 2026-04-30

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-30)

**Core value:** Reliable presence detection and simple activity classification using 2 ESP32-S3 nodes — shipped within 6 weeks.
**Current focus:** Phase 1 — Firmware & Flashing

## Phase Status

| Phase | Status | Requirements | Success Criteria |
|-------|--------|--------------|------------------|
| 1: Firmware & Flashing | 🔴 Not started | HW-01..HW-04 | 0/4 |
| 2: UDP Aggregator | 🔴 Not started | SIG-01..SIG-02 | 0/2 |
| 3: Signal Processing | 🔴 Not started | SIG-03..SIG-06 | 0/4 |
| 4: Presence & Intrusion | 🔴 Not started | SEC-01..SEC-04 | 0/4 |
| 5: Activity Recognition | 🔴 Not started | ACT-01..ACT-04 | 0/4 |
| 6: Dashboard & API | 🔴 Not started | UI-01..UI-05, API-01..API-02 | 0/7 |

## Blockers

None.

## Decisions Pending

None at project start.

## Notes

- 2x ESP32-S3-DevKitC-1 available
- Initial stack: ESP-IDF C + Python + scikit-learn
- Reference code in `llm-wiki/raw/RuView/firmware/` and `llm-wiki/raw/wallhack1.8k/`

---
*State initialized: 2026-04-30*
