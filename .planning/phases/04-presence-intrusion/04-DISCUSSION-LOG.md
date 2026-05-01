# Phase 4: Presence & Intrusion Detection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-05-01
**Phase:** 04-presence-intrusion
**Mode:** discuss (interactive)
**Areas analyzed:** Detection algorithm, State machine, Alert output, Multi-node fusion

## Discussion Summary

### Area 1: Detection Algorithm
- **Q:** Threshold vs adaptive baseline for presence detection?
- **Selected:** Adaptive baseline with automatic empty-room noise floor learning
- **Rationale:** User wants system to adapt to environmental changes (furniture moved, temperature) without manual recalibration. Combines motion_energy + breathing_band.

### Area 2: State Machine & Hysteresis
- **Q:** How many frames to confirm state transitions? Cooldown behavior?
- **Selected:** Hysteresis with asymmetric thresholds (2.5σ enter, 1.5σ exit), 3 consecutive frames (≈6s) to declare Occupied, 10s silence to return Empty, 5s alert cooldown
- **Rationale:** User wants quick intrusion response but stable "empty" state. Prevents boundary flicker when person stands at detection edge.

### Area 3: Alert Output Format & Persistence
- **Q:** JSONL only, or also in-memory buffer for API? Alert structure?
- **Selected:** Dual output — JSONL persistence + in-memory buffer (last 100 alerts). Alert fields: timestamp, node_id, confidence, status, type, trigger_feature. Third Queue for Phase 6 handoff.
- **Rationale:** Phase 6 needs real-time API access, JSONL is for audit/history. Third Queue decouples detector from dashboard.

### Area 4: Multi-Node Fusion & Node Health
- **Q:** OR vs AND fusion? How to handle stale nodes?
- **Selected:** OR logic default, configurable AND mode. Auto-exclude stale nodes (>10s no frames) from fusion. Single-node gracefully degrades. Zero-node reports "unknown".
- **Rationale:** User emphasizes stale node exclusion as critical for multi-node reliability. OR logic reduces blind spots per SEC-03.

## Corrections Made

None — all user-provided decisions accepted as-is.

## Auto-Resolved

Not applicable (not in auto mode).

## External Research

None required — all decisions were user-directed.

---

*Log written: 2026-05-01*
