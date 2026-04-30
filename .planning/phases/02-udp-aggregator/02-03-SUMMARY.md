# Wave 3 Summary: CLI, Persistence, and Integration Tests

**Plan:** 02-03
**Executed:** 2026-04-30
**Status:** Complete — 5/5 tests pass

## Files Delivered

| File | Purpose | Lines |
|------|---------|-------|
| `aggregator/persistence.py` | `NpyWriter` — `.npy` amplitude persistence | 62 |
| `aggregator/main.py` | CLI entry point + asyncio orchestration | 58 |
| `aggregator/__main__.py` | `python -m aggregator` hook | 3 |
| `aggregator/test_integration.py` | End-to-end integration tests | 92 |
| `requirements.txt` | numpy, pytest, pytest-asyncio | 3 |

## Key Decisions Implemented

- **D-08:** Raw CSI persisted as `.npy` for Phase 5 dataset collection
  - Shape: `(frames, 52)`, dtype `np.float32`
  - Directory: `data/raw/YYYY-MM-DD_HH-MM/`
  - Companion `.json` metadata: node_id, start_time, frame_count, shape
  - Rotation at 10,000 frames per file (configurable)

- **D-06:** Asyncio Queue consumer in main event loop
  - Producer: `CsiUdpServer` pushes to queue
  - Consumer: `NpyWriter.write()` pulls from queue
  - Same loop, different tasks — clean separation

## Verification

- `python -m pytest aggregator/test_integration.py -x` → **5 passed**
- Full suite: `python -m pytest aggregator/ -x` → **35 passed in 0.78s**
- Tests cover: `.npy` shape/metadata, rotation, end-to-end UDP socket test, CLI arg parsing, graceful shutdown flush

## CLI Usage

```bash
python -m aggregator --port 5005 --output-dir data/raw --buffer-capacity 500 --rotation-frames 10000 --log-level INFO
```

## Notes

- Graceful shutdown on SIGINT/SIGTERM: cancel consumer, stop server, `flush_all()`
- `NpyWriter` accumulates per-node amplitude vectors and flushes on rotation or shutdown
- Only amplitudes written to `.npy` (not phases) per Phase 5 contract
