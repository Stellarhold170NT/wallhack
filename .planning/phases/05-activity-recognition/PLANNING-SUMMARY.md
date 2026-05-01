## PLANNING COMPLETE

**Phase:** 05-activity-recognition
**Plans:** 3 plan(s) in 3 wave(s)

### Wave Structure

| Wave | Plans | Autonomous |
|------|-------|------------|
| 1 | 05-01-PLAN.md | yes |
| 2 | 05-02-PLAN.md | yes |
| 3 | 05-03-PLAN.md | yes |

### Plans Created

| Plan | Objective | Tasks | Files |
|------|-----------|-------|-------|
| 05-01 | Model architecture (AttentionGRU) + dataset infrastructure | 3 | classifier/__init__.py, classifier/model.py, classifier/dataset.py, tests/test_classifier.py |
| 05-02 | Training pipeline + data collection + augmentation | 4 | classifier/train.py, classifier/collect.py, classifier/augment.py, tests/test_train.py, tests/test_collect.py |
| 05-03 | Real-time inference + aggregator wiring | 4 | classifier/infer.py, classifier/__main__.py, aggregator/main.py, tests/test_infer.py, tests/test_classifier_integration.py |

### Requirements Coverage

| Requirement | Plan(s) |
|-------------|---------|
| ACT-01 (Collect labeled dataset) | 05-02 (collect.py) |
| ACT-02 (Attention-GRU model) | 05-01 (model.py) |
| ACT-03 (Data augmentation) | 05-02 (augment.py) |
| ACT-04 (Input preprocessing) | 05-01 (dataset.py) |
| ACT-05 (Real-time inference) | 05-03 (infer.py) |

### Decision Traceability

All locked decisions from 05-CONTEXT.md are covered:
- **D-33** Hybrid data (HAR + ESP32) → Plan 02
- **D-34** Raw amplitude + StandardScaler → Plan 01
- **D-35** 4 classes (walk, run, lie, bend) → Plan 01
- **D-36** Center-crop to 52 subcarriers → Plan 01, Plan 03
- **D-37** 50-frame windows → Plan 01, Plan 03
- **D-38** classifier/ package → All plans
- **D-39** Fork after server → Plan 03
- **D-40** CLI collect tool → Plan 02
- **D-41** HAR pre-training → Plan 02
- **D-42** nn.GRU + attention, hidden=128 → Plan 01
- **D-43** Offline training with augmentation → Plan 02

### Deferred Ideas (NOT in plans)

- Transitions (sitting down, standing up) — v1.1
- Falling detection — v1.1
- Model pruning — v2
- On-device inference (ESP32-S3) — v2
- Multi-node activity fusion — v2

### Next Steps

Execute: `/gsd-execute-phase 05`

<sub>`/clear` first - fresh context window</sub>

---

*Phase 5 planning completed: 2026-05-01*
*3 plans created, 0 gaps found*
