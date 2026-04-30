# Phase 2: UDP Aggregator - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Python asyncio server dynamically discovers, receives, parses, validates, and buffers binary CSI UDP frames from ≥2 ESP32-S3 nodes. Supports runtime node expansion without restart. Outputs structured CSI objects ready for signal processing (Phase 3) and optionally persists raw data for Phase 5 dataset collection.

**Phase boundary:**
- IN: Valid UDP stream from Phase 1 (binary frames on port 5005)
- OUT: Structured CSI frames in Python ready for DSP + optional `.npy` dataset files

</domain>

<decisions>
## Implementation Decisions

### Node Topology (updated from Phase 1)
- **D-05-updated:** Both Node 0 and Node 1 are peers — both operate as STA only
  - No dedicated TX node; both capture ambient WiFi traffic (beacons, broadcast, cross-traffic)
  - Both stream captured CSI to aggregator independently
  - Rationale: User confirmed this is acceptable; simplifies firmware (no custom TX traffic generation)

### Dynamic Node Discovery
- **D-10:** Aggregator dynamically discovers nodes at runtime — no hardcoded node list
  - Discovery source: UDP source IP + embedded `node_id` in frame header
  - Minimum: 2 nodes required for system to operate (enforced at startup or health check)
  - Supports expansion: new nodes auto-register on first valid frame; node table is a `dict` keyed by `node_id`
  - Node removal: if no frames received for 10 seconds, mark node as stale but retain slot (don't collapse IDs)
  - Rationale: User explicitly requested "tối thiểu 2 node để chạy và có thể mở rộng"; aligns with prunedAttentionGRU multi-node scalability
  - Rejected: Hardcoded node list (inflexible), static config file (requires restart)

### Data Handoff to Phase 3
- **D-06:** Asyncio Queue as inter-phase handoff mechanism
  - Parsed CSI frames are pushed into an `asyncio.Queue` as structured dataclasses
  - Phase 3 consumer runs in same event loop, pulling frames from queue
  - Decouples UDP receiver from DSP pipeline; supports backpressure naturally
  - Alternative rejected: stdout pipe (fragile), direct function call (tight coupling)

### Buffering & Backpressure
- **D-07:** Drop Oldest (ring buffer) strategy with configurable per-node capacity
  - Default: 500 frames per node (~10 seconds @ 50 Hz)
  - When full, oldest frame is dropped to make room for newest — prioritizes recency
  - Rationale: Real-time sensing cares about latest data; prevents memory unbounded growth
  - Rejected: Block-and-backpressure (would stall UDP and cause packet loss upstream), grow-unbounded (memory risk)

### Raw Data Persistence
- **D-08:** Persist raw CSI to `.npy` files for Phase 5 dataset collection
  - Format: NumPy binary `.npy` with shape `(frames, 52)` amplitude or `(frames, 52, 2)` I/Q
  - One file per recording session; auto-rotated by timestamp
  - Also logs metadata JSON alongside each `.npy` (node_id, timestamps, labels if available)
  - Rationale: `.npy` is fast, compact, and directly consumable by PyTorch dataloader in Phase 5
  - Rejected: `.csv` (slow parsing, large files), `.bin` (requires custom parser), HDF5 (overkill for v1)

### Frame Parser Behavior
- **D-09:** Strict validation with graceful degradation
  - Validate magic `0xC511_0001` — drop frame if mismatch
  - Validate length (121 bytes) — drop if wrong size
  - Extract: node_id, sequence, timestamp_ms, RSSI, noise_floor, 52× amplitudes, 52× phases
  - Log parse errors at WARNING level but never crash
  - Track per-node sequence gaps to detect packet loss

### Claude's Discretion
- Exact asyncio.Queue maxsize (within 200-1000 range)
- Internal dataclass structure for parsed frames
- Logging verbosity levels
- `.npy` file naming convention and rotation threshold

</decisions>

<specifics>
## Specific Ideas

- "Node 1 và node 2 có vai trò ngang nhau" — both are STA-only, capture ambient traffic
- Aggregator should log frame rate per node every second for health monitoring
- Packet loss detection via sequence gap analysis (alert if >5% loss sustained)
- `.npy` files organized by `data/raw/YYYY-MM-DD_HH-MM/`

</specifics>

<canonical_refs>
## Canonical References

### Phase 1 frame format (input contract)
- `firmware/esp32-csi-node/main/csi_collector.c` — frame serialization (ADR-018 format)
- `firmware/esp32-csi-node/main/stream_sender.c` — UDP sender implementation
- `.planning/phases/01-firmware/01-CONTEXT.md` — D-04 frame format specification

### Downstream consumers
- `llm-wiki/raw/RuView/docs/adr/ADR-014-sota-signal-processing.md` — Phase 3 DSP algorithms
- `llm-wiki/raw/wallhack1.8k/datasets.py` — amplitude extraction pattern for Phase 5
- `llm-wiki/raw/prunedAttentionGRU/ARIL/aril.py` — 52-subcarrier input format match

### Requirements
- `.planning/REQUIREMENTS.md` — SIG-01, SIG-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `firmware/esp32-csi-node/main/csi_collector.c` — binary frame structure is the parser's input contract
- `firmware/esp32-csi-node/main/stream_sender.c` — UDP transmission logic (receiver mirrors this)

### Established Patterns
- Binary frame with magic header + metadata + I/Q payload (52 subcarriers)
- Per-node sequence numbers for loss detection
- Little-endian byte order

### Integration Points
- Phase 3 reads from `asyncio.Queue` (same process, different task)
- Phase 5 reads `.npy` files from disk (offline training)
- All nodes share UDP socket; distinguished by source IP + embedded `node_id`
- Node registry (`dict[node_id, NodeState]`) consumed by Phase 4 (presence fusion) and Phase 6 (dashboard health)

</code_context>

<deferred>
## Deferred Ideas

- WebSocket streaming to browser (Phase 6 Dashboard)
- Real-time `.npy` visualization during collection
- Multi-aggregator clustering (out of v1 scope)

</deferred>

---

*Phase: 02-udp-aggregator*
*Context gathered: 2026-04-30*
