<!-- refreshed: 2026-05-01 -->
# Architecture

**Analysis Date:** 2026-05-01

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     SENSOR LAYER (ESP32-S3)                      │
│  `firmware/esp32-csi-node/`                                      │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐   │
│  │  NVS Config   │   │ CSI Collector │   │  UDP Stream Sender │   │
│  │ nvs_config.c  │──▶│ csi_collector │──▶│  stream_sender.c   │   │
│  └──────────────┘   └──────────────┘   └─────────┬──────────┘   │
│                                                   │              │
│                          WiFi CSI callback @~50Hz │              │
│                              ADR-018 binary frame │              │
└──────────────────────────────────────────────────┼──────────────┘
                                                     │
                                                     │ UDP datagrams
                                                     │ port 5005
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AGGREGATOR LAYER (Python asyncio)            │
│  `aggregator/`                                                   │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐   │
│  │  UDP Server   │──▶│  Frame Parser│──▶│   Node Buffer      │   │
│  │  server.py    │   │  parser.py   │   │   buffer.py        │   │
│  └──────────────┘   └──────────────┘   └─────────┬──────────┘   │
│                                                   │              │
│                                    asyncio.Queue handoff         │
│                                                   │              │
│                          ┌────────────────────────┴──────────┐  │
│                          ▼                                    ▼  │
│              ┌────────────────────┐              ┌────────────────────┐
│              │   CsiProcessor      │              │   NpyWriter         │
│              │   processor/main.py │              │   persistence.py    │
│              └─────────┬──────────┘              └─────────┬──────────┘
│                        │ asyncio.Queue (feature vectors)  │
│                        ▼                                    │
│               ┌────────────────────┐                        │
│               │   Phase 4 Consumer  │                        │
│               │   (presence detection)│                      │
│               └────────────────────┘                        │
└─────────────────────────────────────────────────────────────┼──┘
                                                     │
                                                     │ .npy + .json files
                                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                 │
│  `data/raw/<YYYY-MM-DD_HH-MM>/`                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  node_{id}_{ts}_{batch}.npy  (float32 amplitude matrix)   │    │
│  │  node_{id}_{ts}_{batch}.json (metadata)                   │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                                     ▲
                                                     │ (reads .npy)
                                                     │
┌─────────────────────────────────────────────────────────────────┐
│                   VISUALIZATION LAYER                            │
│  `scripts/view_csi.py`                                           │
│  matplotlib heatmap of per-subcarrier amplitude over time         │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Firmware main | Boot, WiFi connect, init subsystems | `firmware/esp32-csi-node/main/main.c` |
| CSI Collector | Register WiFi CSI callback, rate-limit to ~50Hz, serialize frames | `firmware/esp32-csi-node/main/csi_collector.c` |
| Stream Sender | UDP socket init, send datagrams, ENOMEM backoff | `firmware/esp32-csi-node/main/stream_sender.c` |
| NVS Config | Load WiFi/node config from NVS with defaults | `firmware/esp32-csi-node/main/nvs_config.c` |
| Provision Script | Write WiFi/IP/node_id to NVS via serial | `firmware/esp32-csi-node/provision.py` |
| CLI Entry Point | Parse args, create server/writer, run event loop | `aggregator/main.py` |
| UDP Server | Bind UDP port, receive datagrams, track nodes | `aggregator/server.py` |
| Frame Parser | Validate magic + length, extract I/Q → amplitude/phase | `aggregator/parser.py` |
| CSI Frame | Dataclass for parsed frame data | `aggregator/frame.py` |
| Node Buffer | Per-node ring buffer with drop-oldest semantics | `aggregator/buffer.py` |
| NpyWriter | Accumulate amplitudes, flush to .npy with auto-rotation | `aggregator/persistence.py` |
| CsiProcessor | Real-time signal processing: sliding window, Hampel filter, feature extraction | `processor/main.py` |
| SlidingWindow | Circular buffer for fixed-size windows with step-based emission | `processor/window.py` |
| Feature Extractor | Band power + per-subcarrier statistics from amplitude windows | `processor/features.py` |
| Viewer | Load .npy, render heatmap via matplotlib | `scripts/view_csi.py` |

## Pattern Overview

**Overall:** Pipeline architecture with async event-driven data flow.

**Key Characteristics:**
- **Asynchronous single-threaded** — aggregator uses `asyncio` with `DatagramProtocol` for UDP, no threading locks required
- **Binary protocol** — ADR-018 defines a fixed 20-byte header + I/Q payload with little-endian encoding, validated by magic number (`0xC5110001`)
- **Dynamic node discovery** — nodes register on first valid frame, no prior configuration needed
- **Bounded memory** — per-node ring buffer with configurable capacity (default 500), drop-oldest on overflow
- **Graceful degradation** — invalid/corrupt frames are logged and dropped, never crash the pipeline
- **File rotation** — NpyWriter auto-rotates every N frames (default 10,000) to limit memory and file size
- **No shared state across layers** — firmware and aggregator communicate only via UDP datagrams

## Layers

**Sensor Layer (ESP32-S3 Firmware):**
- Purpose: Capture WiFi CSI data from ESP32-S3 hardware, serialize to binary, stream over UDP
- Location: `firmware/esp32-csi-node/main/`
- Contains: 4 C modules — `main.c`, `csi_collector.c`, `stream_sender.c`, `nvs_config.c`
- Depends on: ESP-IDF SDK (`esp_wifi`, `lwip`, `nvs_flash`, `FreeRTOS`)
- Used by: Aggregator layer (receives UDP datagrams)
- Build: Docker-based ESP-IDF v5.2 cross-compilation via `build_firmware.ps1`/`build_firmware.bat`

**Aggregator Layer (Python asyncio):**
- Purpose: Receive, parse, buffer, and persist CSI frames from multiple ESP32-S3 nodes
- Location: `aggregator/`
- Contains: 7 Python modules — `__main__.py`, `main.py`, `server.py`, `parser.py`, `frame.py`, `buffer.py`, `persistence.py`
- Depends on: Python standard library (`asyncio`, `struct`, `argparse`), `numpy`
- Entry point: `python -m aggregator [--port 5005] [--output-dir data/raw]`

**Data Layer (numpy files on disk):**
- Purpose: Persist amplitude matrices for offline processing and ML dataset creation
- Location: `data/raw/<YYYY-MM-DD_HH-MM>/`
- Contains: `.npy` float32 arrays and `.json` metadata files, organized per node with automatic rotation
- Depends on: Output of NpyWriter in aggregator layer

**Visualization Layer (Python scripts):**
- Purpose: Load recorded sessions and render CSI amplitude heatmaps
- Location: `scripts/view_csi.py`
- Depends on: matplotlib, numpy

## Data Flow

### Primary Request Path (UDP datagram → processor + disk)

1. **ESP32-S3 captures CSI** — WiFi CSI callback fires per received packet, rate-limited to ~50Hz in `csi_collector.c:80-105`
2. **Serialize to ADR-018** — `csi_serialize_frame()` packs header + I/Q bytes in `csi_collector.c:34-78`
3. **UDP send** — `stream_sender_send()` transmits via lwIP UDP socket in `stream_sender.c:51-81`
4. **Asyncio receives datagram** — `CsiUdpServer.datagram_received()` in `server.py:78-118`
5. **Parse binary frame** — `parse_frame()` validates magic, length, extracts I/Q → amplitude/phase in `parser.py:21-98`
6. **Dynamic node discovery** — first frame from unknown node_id creates `NodeState` in `server.py:85-98`
7. **Per-node buffering** — frame pushed to `NodeBuffer` (deque with maxlen) in `server.py:113`
8. **Queue handoff** — frame put on `asyncio.Queue` for consumer in `server.py:116`
9. **Consumer loop** — `consumer()` task reads queue and calls `writer.write()` in `main.py:62-67`
10. **Accumulate & flush** — `NpyWriter.write()` appends amplitudes, auto-flushes at rotation_frames in `persistence.py:55-67`
11. **Processor task** — `CsiProcessor.run()` reads same Queue, builds per-node `SlidingWindow`, applies Hampel filter, extracts features in `processor/main.py:49-137`
12. **Feature emission** — `extract_features()` computes band power + statistics in `processor/features.py:10-64`; feature dict logged at INFO level (D-20)
13. **Phase 4 handoff** — feature dict pushed to second `asyncio.Queue` in `processor/main.py:131-135`

### Secondary Flow: Graceful Shutdown

1. **SIGINT/SIGTERM** handler triggers shutdown event
2. Consumer task is cancelled
3. `server.stop()` cancels FPS logger + stale checker tasks, closes transport
4. `writer.flush_all()` writes any remaining buffered frames to disk
5. All `.npy` files are safely flushed before exit

### Node Health Monitoring

1. **FPS logger** (`_fps_logger()`) logs per-node frames-per-second and sustained loss ratio every 1s
2. **Stale checker** (`_stale_checker()`) marks nodes stale after 10s of inactivity
3. **Sequence gap detection** tracks missing sequence numbers for loss computation

**State Management:**
- Firmware: Global static variables per module (e.g., `s_node_id`, `s_sequence`) — single-node, no concurrency
- Aggregator: `CsiUdpServer.nodes` dict keyed by `node_id` — all state in one asyncio event loop, no locks
- NpyWriter: Internal dicts per node_id for amplitude accumulators and write buffers

## Key Abstractions

**CSIFrame (dataclass):**
- Purpose: Represents a single parsed CSI frame with metadata and per-subcarrier arrays
- File: `aggregator/frame.py`
- Fields: `node_id`, `sequence`, `rssi`, `noise_floor`, `frequency_mhz`, `n_subcarriers`, `amplitudes`, `phases`
- Pattern: Immutable dataclass with `__post_init__` validation

**NodeBuffer (ring buffer):**
- Purpose: Bounded per-node storage with drop-oldest eviction
- File: `aggregator/buffer.py`
- Methods: `push()`, `get_all()`, `last_sequence()`
- Pattern: Wraps `collections.deque(maxlen=N)`, tracks `drop_count`

**NodeState (dataclass):**
- Purpose: Runtime tracking for each dynamically discovered ESP32-S3 node
- File: `aggregator/server.py`
- Fields: `node_id`, `addr`, `buffer`, `last_seen`, `frame_count`, `loss_count`, `last_sequence`, `stale`

**NpyWriter (file rotator):**
- Purpose: Accumulate amplitude arrays per node, flush to timestamped session directories
- File: `aggregator/persistence.py`
- Pattern: Internal `_buffers[node_id]` dict of lists; auto-rotation every N frames; `flush_all()` on shutdown
- Output: `node_{id}_{ts}_{batch:04d}.npy` + companion `.json` metadata per batch

**CsiProcessor (signal processing task):**
- Purpose: Real-time feature extraction from CSI amplitude streams
- File: `processor/main.py`
- Pattern: Asyncio task with per-node `SlidingWindow` state; handles variable subcarrier counts via crop/pad adaptation (D-19)
- Output: Feature dicts pushed to second `asyncio.Queue` for Phase 4 consumption

**nvs_config_t (C struct):**
- Purpose: WiFi credentials, aggregator target, and node identity loaded from NVM storage
- File: `firmware/esp32-csi-node/main/nvs_config.h`
- Fields: `wifi_ssid`, `wifi_password`, `target_ip`, `target_port`, `node_id`

## Entry Points

**Aggregator CLI:**
- Location: `aggregator/__main__.py` (delegates to `aggregator/main.py:main()`)
- Triggers: `python -m aggregator [options]`
- Arguments: `--port` (5005), `--output-dir` (data/raw), `--buffer-capacity` (500), `--rotation-frames` (10000), `--log-level` (INFO)
- Responsibilities: Parse args, create `CsiUdpServer` + `NpyWriter`, run asyncio event loop with graceful shutdown

**Firmware Main:**
- Location: `firmware/esp32-csi-node/main/main.c:app_main()`
- Triggers: ESP32-S3 boot
- Responsibilities: Init NVS, load config, connect WiFi, init CSI collector, start UDP stream sender

**Provision Script:**
- Location: `firmware/esp32-csi-node/provision.py:main()`
- Triggers: `python provision.py --port COM7 --ssid ...`
- Responsibilities: Build NVS CSV, generate binary, flash via esptool

**Data Viewer:**
- Location: `scripts/view_csi.py`
- Triggers: `python scripts/view_csi.py <session_dir>`
- Responsibilities: Load `.npy` files from session directory, render heatmap via matplotlib

**Processor Offline CLI:**
- Location: `processor/__main__.py`
- Triggers: `python -m processor --input x.npy --output y.npy`
- Responsibilities: Process saved `.npy` amplitude arrays through identical Hampel + feature extraction pipeline

## Architectural Constraints

- **Threading:** Single-threaded asyncio event loop in aggregator. No threading.Lock used anywhere. Firmware runs on FreeRTOS (dual-core ESP32-S3) but CSI callback and UDP send happen from the WiFi task context.
- **Global state:** Firmware uses module-level static globals for node_id, sequence counter, UDP socket, and send statistics (`csi_collector.c`, `stream_sender.c`). Aggregator has no global mutable state — all state lives in `CsiUdpServer.nodes`, `NpyWriter._buffers`, and local `asyncio.Queue`.
- **Circular imports:** None. Aggregator modules import in a clean DAG: `frame.py` (no deps) → `parser.py` (depends on frame) → `buffer.py` (depends on frame) → `server.py` (depends on parser, buffer, frame) → `persistence.py` (depends on frame) → `main.py` (depends on server, persistence).
- **UDP loss tolerance:** System is designed for unreliable transport — sequence gaps are tracked as loss metrics, invalid frames are dropped silently, buffer overflow drops oldest frames.
- **No back-pressure from disk i/o:** NpyWriter writes synchronously in the consumer task — this blocks the event loop during file writes.

## Anti-Patterns

### Synchronous file I/O in async consumer

**What happens:** `NpyWriter.write()` calls `np.save()` synchronously in the asyncio consumer task (`main.py:40`).
**Why it's wrong:** `np.save()` is a blocking call. On rotation (every 10,000 frames), it writes a ~2MB file, blocking the event loop. During that time, incoming UDP frames are buffered by the OS but not processed, increasing latency.
**Do this instead:** Offload file writes to a thread pool (`loop.run_in_executor()`) or use `aiofile` for async I/O.

### Duplicate test helper code

**What happens:** `test_parser.py`, `test_server.py`, and `test_integration.py` each define the identical `build_frame()` and `_make_64_iq()`/`_make_52_iq()` helpers.
**Why it's wrong:** Violates DRY. Adding a field to the frame format requires updating the helper in 3 places.
**Do this instead:** Move `build_frame()` and IQ helpers to a shared `tests/conftest.py` or a test utility module.

### Global static state in firmware

**What happens:** `csi_collector.c` and `stream_sender.c` use module-level static variables (`s_node_id`, `s_sequence`, `s_sock`, etc.).
**Why it's wrong:** Prevents multiple instances, makes unit testing difficult, and creates implicit coupling between modules.
**Do this instead:** Pass context structs through function parameters (already partially done with `nvs_config_t` for config).

## Error Handling

**Strategy:** Graceful degradation — never crash, always log and drop.

**Patterns:**
- `parse_frame()` returns `Optional[CSIFrame]` — None on any validation failure
- `CsiUdpServer.datagram_received()` checks `frame is None` and returns early for invalid frames
- `stream_sender_send()` has ENOMEM backoff with cooldown timer (100ms)
- `NpyWriter._flush_node()` handles inconsistent subcarrier lengths by filtering to most common length
- `CSIFrame.__post_init__()` raises `ValueError` for mismatched array lengths (caught during creation)

## Cross-Cutting Concerns

**Logging:** Python `logging` module with per-module loggers (`aggregator`, `server`, `parser`, `persistence`). ESP-IDF `ESP_LOG*` macros. All invalid frames logged at WARNING level. FPS and health logged at INFO level every 1s.

**Validation:** Binary protocol validation at parse time (magic number, frame length bounds). CLI args validated via `argparse` with choices and type constraints. `CSIFrame` dataclass validates array lengths in `__post_init__`.

**Serialization format (ADR-018):**
- Little-endian binary
- 4-byte magic (`0xC5110001`) for frame identification
- 20-byte header: node_id(1), antennas(1), n_subcarriers(2), frequency_mhz(4), sequence(4), rssi(1), noise_floor(1), reserved(2)
- Variable-length payload: interleaved int8 I/Q pairs per subcarrier
- Total frame = 20 + n_subcarriers × 2 bytes

---

*Architecture analysis: 2026-05-01*
