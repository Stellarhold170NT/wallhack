# Wave 2 Summary: Asyncio UDP Server and Ring Buffer

**Plan:** 02-02
**Executed:** 2026-04-30
**Status:** Complete — 13/13 tests pass

## Files Delivered

| File | Purpose | Lines |
|------|---------|-------|
| `aggregator/buffer.py` | `NodeBuffer` — drop-oldest ring buffer | 35 |
| `aggregator/server.py` | `CsiUdpServer` + `NodeState` — asyncio UDP protocol | 118 |
| `aggregator/test_server.py` | Unit tests (buffer, server, queue, gaps, stale) | 115 |

## Key Decisions Implemented

- **D-10:** Dynamic node discovery — no hardcoded node list
  - New nodes auto-register on first valid frame
  - `nodes: dict[int, NodeState]` tracks IP, last_seen, frame_count, loss_count
  - Stale after 10s inactivity; slot retained (not collapsed)

- **D-07:** Drop Oldest ring buffer per node
  - `collections.deque` with configurable capacity (default 500)
  - When full, `popleft()` evicts oldest; `drop_count` tracked
  - No locks needed (single asyncio event loop)

- **D-06:** Asyncio Queue inter-phase handoff
  - Parsed frames pushed to `asyncio.Queue` for Phase 3 consumption
  - Unbounded queue (`maxsize=0`) — backpressure handled by buffer

## Verification

- `python -m pytest aggregator/test_server.py -x` → **13 passed**
- Tests cover: buffer eviction, get_all ordering, drop counting, server start/stop, node registration, queue push, sequence gap detection (seq 1→5 → loss=3), stale marking

## Notes

- `CsiUdpServer` inherits `asyncio.DatagramProtocol`
- Background tasks: `_fps_logger()` (1s interval) and `_stale_checker()` (1s interval)
- Frame rate and loss logged at INFO level
