# Phase 3: Signal Processing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-05-01
**Phase:** 03-signal-processing
**Mode:** discuss (interactive)
**Areas analyzed:** Module organization, Algorithm approach, Windowing strategy, Multi-node processing

## Discussion Summary

### Area 1: Module Organization
- **Q1 (integration pattern):** In-process co-routine vs subprocess pipe vs standalone CLI
  - **Selected:** In-process co-routine (Option 1) — lowest latency, simplest deployment
- **Q2 (package visibility):** Separate package with CLI vs importable only vs both
  - **Selected:** Multi-purpose package — CLI for offline testing, importable for online
- **Q3 (config passing):** Config dict from aggregator vs self-read config vs hybrid
  - **Selected:** Config passed from Aggregator ("nhạc trưởng")
- **Q4 (output handoff):** Second Queue vs direct call vs both
  - **Selected:** Push to second asyncio.Queue

### Area 2: Algorithm Approach
- **Q5 (phase processing):** Amplitude only vs both amplitude + phase
  - **Selected:** Both — amplitude for HAR (Phase 5), phase unwrap + detrend for presence breathing sensitivity (Phase 4)
  - User analogy: "Amplitude = hình dáng sóng, Phase = vị trí chính xác"
- **Q6 (Hampel filter):** Custom implementation vs scipy vs skip
  - **Selected:** Custom implementation (~10-15 lines), no new dependency
  - User analogy: "NgườI bảo vệ bắt tín hiệu nhảy vọt"
- **Q7 (feature format):** Flat array vs dict vs both
  - **Selected:** Dict with metadata + flat feature array inside
  - User analogy: "Hộp quà" (dict) wrapping "Dãy số" (array)

### Area 3: Windowing Strategy
- **Q8 (real-time vs offline):** Real-time primary vs offline primary vs both
  - **Selected:** Real-time streaming primary, offline `.npy` replay secondary
  - Rationale: Dashboard needs live updates; offline mode useful for tuning without hardware

### Area 4: Multi-Node Processing
- **Q9 (fusion level):** Signal-level vs feature-level vs decision-level fusion
  - **Selected:** Decision-level fusion in Phase 4 (per-node independent processing in Phase 3)
  - User analogy: "2 ngườI bảo vệ báo cáo riêng, trung tâm tổng hợp"
  - Rationale: Avoids clock drift, scalable, fault-tolerant

## Corrections Made

None — all initial assumptions confirmed by user.

## Auto-Resolved

Not applicable (not in auto mode).

## External Research

None required — codebase references (ADR-014, Kang et al. 2025 source) provided sufficient evidence.

---

*Log written: 2026-05-01*
