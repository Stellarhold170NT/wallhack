# Codebase Concerns

**Analysis Date:** 2026-05-01

## Tech Debt

### No Root `.gitignore` File

- **Issue:** The repository root at `E:\nt170\wallhack\` has no `.gitignore` file. Only the firmware subdirectory (`firmware/esp32-csi-node/.gitignore`) has one. This means Python `__pycache__/`, `.pytest_cache/`, compiled `.pyc` files, and build artifacts under `firmware/esp32-csi-node/build/` are all tracked by git.
- **Files:** Root directory
- **Impact:** Commits may include unwanted artifacts. The `.pytest_cache/` directory is committed.
- **Fix approach:** Add a root `.gitignore` with Python, build, IDE, and OS entries.

### Hardcoded Firmware Defaults Present in Two Places

- **Issue:** Default WiFi SSID (`"wifi-densepose"`) and target IP (`"192.168.1.100"`) are hardcoded in both `firmware/esp32-csi-node/main/nvs_config.c` (lines 7-11) and `firmware/esp32-csi-node/main/stream_sender.c` (line 8). These are compiled into every firmware binary, and the device silently falls back to these defaults if NVS is empty.
- **Files:** `firmware/esp32-csi-node/main/nvs_config.c`, `firmware/esp32-csi-node/main/stream_sender.c`
- **Impact:** A device without NVS provisioning will try to connect to `"wifi-densepose"` network and stream to `192.168.1.100:5005` — no indication this is the wrong target. This is both a security concern and a debugging headache.
- **Fix approach:** Remove compiled defaults and fast-fail if NVS provisioning hasn't been done. Or use distinct placeholder values that are clearly invalid.

### Signal Handler Silent Failure on Windows

- **Issue:** The `_sigint_handler` in `aggregator/main.py` wraps `loop.add_signal_handler()` in try/except `NotImplementedError`. On Windows, `add_signal_handler` raises `NotImplementedError`, which is silently caught with `pass`. This means **graceful shutdown via Ctrl+C does not work on Windows** — the primary development platform per README.
- **Files:** `aggregator/main.py` (lines 61-72)
- **Impact:** On Windows, Ctrl+C kills the process abruptly. The `finally:` block in `run_server()` runs `await shutdown()`, but since signal handlers aren't registered, the event loop keeps running until the process is force-killed. Data is lost.
- **Fix approach:** Use `loop.add_signal_handler()` on Unix and install a `try/finally` or handler via `asyncio.Event` for Windows (e.g., catching `KeyboardInterrupt` in the main thread).

### `timestamp_ms` Always Zero

- **Issue:** The `CSIFrame.timestamp_ms` field exists in the dataclass (`aggregator/frame.py`, line 34) but is **always set to 0** by `parser.py` (line 87). The firmware never sends a timestamp, and the reserved bytes at offsets 18-19 in the binary header are unused. Every frame's timestamp_ms = 0.
- **Files:** `aggregator/frame.py` (line 34), `aggregator/parser.py` (line 87), `firmware/esp32-csi-node/main/csi_collector.c` (lines 72-73)
- **Impact:** No frame-level timing information is available. Temporal analysis, frame rate calculations, and synchronization across nodes rely on the host-side arrival time rather than actual capture time.
- **Fix approach:** Either (a) populate reserved header bytes with a 16-bit millisecond counter from the ESP timer in `csi_collector.c` and parse it in `parser.py`, or (b) remove the unused field.

### Test `build_frame` Helper Duplicated Across Three Files

- **Issue:** The identical `build_frame()` and `_make_*_iq()` helper functions are copied into `test_parser.py`, `test_server.py`, and `test_integration.py`. Any change to the binary format requires updating all three.
- **Files:** `aggregator/test_parser.py` (lines 10-34), `aggregator/test_server.py` (lines 17-32), `aggregator/test_integration.py` (lines 21-36)
- **Impact:** Maintenance burden. Binary format changes risk test inconsistencies.
- **Fix approach:** Extract helpers into a shared `tests/conftest.py` or `aggregator/test_helpers.py`.

### No Python Lock File or `pyproject.toml`

- **Issue:** `requirements.txt` uses loose version pins (`numpy>=1.24.0`, `pytest>=7.0.0`). There is no `pyproject.toml`, `setup.py`, `setup.cfg`, or lock file (e.g., `requirements.lock`, `Pipfile.lock`).
- **Files:** `requirements.txt`
- **Impact:** Non-reproducible builds. CI and different developer machines may resolve different dependency versions, leading to inconsistent behavior.
- **Fix approach:** Add `pyproject.toml` or generate a lock file. Consider `pip freeze > requirements.lock` as a minimal fix.

### Vietnamese Comments in Scripts

- **Issue:** `scripts/view_csi.py` and `firmware/esp32-csi-node/test/test_udp.py` use Vietnamese for user-facing messages and inline comments.
- **Files:** `scripts/view_csi.py` (lines 13, 20, 23, 41, 47, 52-53), `firmware/esp32-csi-node/test/test_udp.py` (line 11)
- **Impact:** Mixed-language codebase reduces accessibility for non-Vietnamese contributors. The README is also in Vietnamese.
- **Fix approach:** Normalize user-facing messages to English in code; README language choice is acceptable given the target audience.

## Known Bugs

### `provision.py` Password Check Always True

- **Issue:** In `firmware/esp32-csi-node/provision.py` line 28, the condition is `if args.password is not None`. However, `--password` has `default=""` (line 82), so `args.password` is **never** `None` — it's always an empty string `""`. The conditional is always true, meaning a blank password entry is always written to NVS.
- **Files:** `firmware/esp32-csi-node/provision.py` (lines 28, 82)
- **Impact:** The `password` key is always written to NVS, even when connecting to an open network. This is mostly cosmetic — no functional bug — but violates the documented behavior ("empty for open network").
- **Fix approach:** Change the default to `None` and check `is not None` as intended, or switch to `if args.password`.

### No NVS Write Verification in `provision.py`

- **Issue:** `provision.py` calls `esptool write_flash` for the NVS binary but never verifies the write was successful or that the ESP32-S3 can read the config back.
- **Files:** `firmware/esp32-csi-node/provision.py` (lines 63-75)
- **Impact:** A failed or partial write goes undetected. The ESP32-S3 would fall back to compiled defaults silently, and the user would see no error.
- **Fix approach:** Add a read-back verification step after flashing, or at minimum check the esptool exit code explicitly.

### Graceful Shutdown Race Condition

- **Issue:** In `aggregator/main.py`, the `shutdown()` function (lines 44-57) checks `if shutdown_event.is_set(): return` at the top for idempotency. However, `shutdown()` is called both from the signal handler (`_sigint_handler`, line 62) AND from the `finally:` block (line 80). If the signal fires, `shutdown()` runs before `finally:` runs `await shutdown()` again. Due to the `shutdown_event` guard, the second call is a no-op, but the consumer task cancellation in the first call may leave frames in the queue unflushed.
- **Files:** `aggregator/main.py` (lines 44-57, 62, 80)
- **Impact:** Potential data loss if shutdown is triggered a second time — the writer won't flush remaining queued frames.
- **Fix approach:** Ensure `flush_all()` is always called exactly once, regardless of how many times shutdown is invoked.

## Security Considerations

### Unencrypted UDP CSI Stream

- **Issue:** CSI frames (containing WiFi channel measurements correlated to physical environment) are sent as **unencrypted UDP datagrams**. The aggregator binds to `0.0.0.0:5005` with no authentication, no encryption, and no access control. Anyone on the network can send fake frames or eavesdrop.
- **Files:** `aggregator/server.py` (line 124), `firmware/esp32-csi-node/main/stream_sender.c`
- **Current mitigation:** None. The protocol uses a magic byte (`0xC5110001`) for basic frame identification, which provides no security.
- **Recommendations:** At minimum, add an allowlist of trusted source IPs on the aggregator side. For production, consider DTLS or a simple shared-secret HMAC on frame payloads.

### WiFi Credentials in Plaintext NVS

- **Issue:** WiFi SSID and password are stored in plaintext in the ESP32-S3 NVS flash partition. They can be read by anyone with physical access to the device via UART or by dumping flash.
- **Files:** `firmware/esp32-csi-node/main/nvs_config.c`, `firmware/esp32-csi-node/provision.py`
- **Current mitigation:** NVS is a proprietary binary format, but it is not encrypted.
- **Recommendations:** Use ESP32-S3 flash encryption if deployed outside a controlled environment. Acceptable for prototyping/research.

### WiFi Password Passed as CLI Argument

- **Issue:** `provision.py` accepts `--password` as a CLI argument. On most systems, CLI arguments are visible to other users via `ps`/`Process Explorer`.
- **Files:** `firmware/esp32-csi-node/provision.py` (line 82)
- **Current mitigation:** None.
- **Recommendations:** Read password from stdin or an environment variable for shared/CI environments.

### Server Binds to All Interfaces

- **Issue:** The aggregator binds to `0.0.0.0` (`aggregator/server.py`, line 124), accepting UDP packets from any network interface.
- **Files:** `aggregator/server.py` (line 124)
- **Current mitigation:** None. The user must firewall the port externally.
- **Recommendations:** Add a `--bind` CLI argument to restrict to a specific interface. Default should stay `0.0.0.0` for development convenience but be configurable.

### Web Aggregator Prototype Has Open CORS

- **Issue:** The prototype `web_aggregator.py` sets `cors_allowed_origins="*"` (line 14), allowing any website to communicate with it.
- **Files:** `firmware/esp32-csi-node/test/web_aggregator.py` (line 14)
- **Current mitigation:** This is a test/debug tool, not production code.
- **Recommendations:** Tag the file as `# PROTOTYPE ONLY — not for production use`. Consider removing open CORS when promoting to production.

## Performance Bottlenecks

### Per-Subcarrier Math in Python Parser

- **Problem:** `aggregator/parser.py` (lines 74-82) loops over every subcarrier and computes `math.sqrt()` and `math.atan2()` for each. At 50 Hz × 2 nodes × ~64 subcarriers = 6,400 trig operations/second in Python.
- **Files:** `aggregator/parser.py` (lines 74-82)
- **Cause:** Pure Python per-frame math with no vectorization.
- **Improvement path:** For high-data-rate scenarios, use `numpy` vectorization on the I/Q bytes directly, or precompute amplitudes with `numpy.frombuffer` + reshape. Alternatively, defer phase calculation to on-demand (it's not persisted — see `persistence.py`).

### Memory Accumulation in `NpyWriter`

- **Problem:** `NpyWriter` (lines 55-66 in `persistence.py`) appends every frame's amplitude list to an in-memory Python list `self._buffers[node_id]`. For a 10,000-frame rotation at 64 subcarriers, this holds ~5 MB of Python float objects in memory — plus Python object overhead (~8×), so ~40 MB.
- **Files:** `aggregator/persistence.py` (lines 40, 63)
- **Cause:** No pre-allocated numpy array. Frames are accumulated as Python lists of lists, then converted to `np.array` at flush time.
- **Improvement path:** Pre-allocate a `numpy.ndarray` of shape `(rotation_frames, n_subcarriers)` and fill by index. This also eliminates the flush-time conversion overhead.

### Firmware Rate Limiting Is Fixed

- **Problem:** The ESP32-S3 firmware rate-limits CSI callbacks to ~50 Hz using a simple monotonic timer (`CSI_MIN_SEND_INTERVAL_US = 20000` in `csi_collector.c`, line 19). There is no adaptive rate control, and dropped callbacks are silently discarded.
- **Files:** `firmware/esp32-csi-node/main/csi_collector.c` (lines 19, 86-89)
- **Cause:** Simple time-based gate without queueing.
- **Improvement path:** Consider a small ring buffer on the firmware side to capture bursts. Alternatively, make the rate configurable via NVS.

### No UDP Backpressure Mechanism

- **Problem:** When the aggregator's queue is full (`asyncio.QueueFull` in `server.py`, line 118), frames are dropped silently with only a warning log. The firmware has no way to know the aggregator is saturated.
- **Files:** `aggregator/server.py` (lines 115-118), `firmware/esp32-csi-node/main/stream_sender.c`
- **Cause:** UDP is inherently fire-and-forget.
- **Improvement path:** Log frame drops with a rate-limited counter. For higher reliability, consider a feedback mechanism (e.g., a lightweight TCP status endpoint or ICMP-based detection).

## Fragile Areas

### Inconsistent Subcarrier Count Handling

- **Component:** `NpyWriter._flush_node()`
- **Files:** `aggregator/persistence.py` (lines 92-108)
- **Why fragile:** When frames within a buffer have inconsistent subcarrier counts, the writer filters to the most common length — silently **discarding frames** that don't match. This masks firmware bugs or WiFi configuration issues that cause variable subcarrier counts. The warnings are at `WARNING` level and may go unnoticed.
- **Safe modification:** When adding new metrics or changing dimensions, ensure the most-common-length filter doesn't discard valid data. Add explicit logging of discarded frame count.
- **Test coverage:** No test covers the inconsistent-subcarrier path.

### `strncpy` Usage in Firmware (Truncation Risk)

- **Component:** `nvs_config.c` and `main.c`
- **Files:** `firmware/esp32-csi-node/main/nvs_config.c` (lines 16, 19, 22), `firmware/esp32-csi-node/main/main.c` (lines 66-68)
- **Why fragile:** `strncpy` does **not** null-terminate the destination buffer if the source is longer than the destination. The code manually adds `\0` at `[NVS_CFG_*_MAX - 1]` as a safeguard, but if `nvs_get_str` writes exactly `NVS_CFG_SSID_MAX` bytes (33), the null terminator at index 32 is outside the usable range since `strncpy` already wrote up to 32 chars and the explicit null is at position 32. This is a well-known C footgun.

  Specifically in `main.c` line 66:
  ```c
  strncpy((char *)wifi_config.sta.ssid, g_nvs_config.wifi_ssid,
          sizeof(wifi_config.sta.ssid) - 1);
  ```
  This copies at most 31 bytes (since `wifi_config.sta.ssid` is 32 bytes). If `g_nvs_config.wifi_ssid` is exactly 32 chars, the destination is NOT null-terminated.
- **Safe modification:** Replace `strncpy` with `snprintf` or `memcpy` + explicit manual null termination at the last position. Or use `strlcpy` if available in ESP-IDF.
- **Test coverage:** No firmware unit tests at all.

### No Firmware Unit Tests

- **Component:** Entire firmware
- **Files:** `firmware/esp32-csi-node/main/` (all .c and .h files)
- **Why fragile:** All 395 lines of C firmware code have **zero unit tests**. The Python integration tests (`aggregator/test_integration.py`) test the aggregator's handling of UDP data, but cannot test firmware behavior (frame assembly, rate limiting, NVS integration, WiFi reconnection).
- **Safe modification:** Every firmware change requires physical deployment to verify. No regression safety net.
- **Test coverage:** Zero. All firmware C code is untested.

### `NodeBuffer` Not Thread-Safe (Design Assumption)

- **Component:** `NodeBuffer`
- **Files:** `aggregator/buffer.py` (lines 11-53)
- **Why fragile:** The docstring on line 3-4 explicitly states "runs within a single asyncio event loop, so no locks are needed." This is correct for current usage, but if any background task or future thread touches the buffer, there will be data races. The design makes a deliberate single-thread assumption.
- **Safe modification:** If adding concurrent access (e.g., a webserver endpoint that reads buffer state), wrap `self._deque` operations with a lock or switch to `asyncio.Lock`.
- **Test coverage:** Covered by `test_server.py` tests, but no thread-safety stress tests.

### `csi_collector_init()` Can Silently Degrade

- **Component:** `csi_collector_init()`
- **Files:** `firmware/esp32-csi-node/main/csi_collector.c` (lines 107-143)
- **Why fragile:** Three `esp_wifi` calls in succession: `set_promiscuous`, `set_csi_config`, `set_csi_rx_cb`, `set_csi`. If any fails, the function either logs a warning and continues (`set_promiscuous`, line 113) or logs an error and returns early (`set_csi_config`, line 128; or `set_csi_rx_cb`, line 133). A partial init state (e.g., promiscuous on but CSI off) is possible.
- **Safe modification:** Ensure the caller checks the return status or the module tracks its initialization state.
- **Test coverage:** Not tested (no firmware tests).

## Scaling Limits

### Single-Host Aggregator

- **Current capacity:** The aggregator runs as a single Python process on one host. It binds one UDP socket, queues frames via one `asyncio.Queue`, and writes to a local filesystem.
- **Limit:** Approximately 2-4 ESP32-S3 nodes at 50 Hz each (assuming ~150-200 µs per frame parse + queue push). Beyond that, Python's single-threaded event loop becomes the bottleneck.
- **Scaling path:** Distribute nodes across multiple aggregator instances by port or use a more efficient parser (C extension or pre-allocated numpy buffers).

### `asyncio.Queue` Default Capacity

- **Current capacity:** The queue in `server.py` (line 57) uses `maxsize=0`, meaning unbounded. Under sustained high frame rates, this can grow without bound and exhaust system memory.
- **Limit:** Depends on memory. A burst of 100,000 frames × ~1 KB each = ~100 MB of Python objects (more with overhead).
- **Scaling path:** Set a finite `maxsize` consistent with the buffer capacity, and log/persist dropped frames.

## Dependencies at Risk

### `espressif/idf:v5.2` Docker Image

- **Risk:** Pinned to a specific tag (`v5.2`). If the image is deprecated or removed from Docker Hub, firmware builds break.
- **Impact:** Cannot build firmware. No documented alternative build path.
- **Migration plan:** Document manual ESP-IDF installation as a fallback. Pin to a specific image SHA digest in addition to the tag.

### `esp-idf-nvs-partition-gen` Python Module

- **Risk:** This module (`provision.py`, lines 45-55) is tried under two names (`esp_idf_nvs_partition_gen` and `nvs_partition_gen`). Neither is in `requirements.txt`. Missing this dependency fails silently — the user only gets an error at provision time.
- **Impact:** Provisioning fails. The user must manually `pip install nvs-partition-gen`.
- **Migration plan:** Add `nvs-partition-gen` to `requirements.txt`. The current code tries two module names, which suggests the package API has changed across versions — this is itself a risk.

### No Version Pin for `esptool`

- **Risk:** `esptool` is mentioned in the README with `pip install esptool` but not in `requirements.txt` (it's a dev dependency). Different esptool versions may have incompatible CLI flags.
- **Impact:** Flashing/provisioning commands break with newer esptool versions.
- **Migration plan:** Add `esptool` to a `dev-requirements.txt` with a loose pin.

## Missing Critical Features

### No Health Check or Telemetry

- **Problem:** The aggregator has no HTTP health endpoint, no metrics export, and no way to programmatically query its status (uptime, frame rates per node, drop counts, queue depth).
- **Blocks:** Automated monitoring, integration with orchestration, remote debugging.
- **Priority:** Medium

### No Data Validation Pipeline

- **Problem:** The only data validation is the parser-level format check (magic byte + length). There is no validation of data ranges, no outlier detection, and no sanity check on amplitude values before persistence.
- **Blocks:** Trustworthy datasets for ML training. Corrupted frames propagate through the pipeline undetected.
- **Priority:** Medium

### No Crash Recovery / Restart Logic

- **Problem:** If the aggregator crashes mid-session, in-memory frame buffers are lost. There is no journal, WAL, or checkpoint mechanism.
- **Blocks:** Long-duration data collection runs.
- **Priority:** Low (acceptable for research/prototype phase)

### No Firmware Over-the-Air (OTA) Update

- **Problem:** Firmware only supports serial flashing. No OTA update mechanism.
- **Blocks:** Deploying firmware updates to deployed nodes without physical access.
- **Priority:** Low (acceptable for lab/research use)

## Test Coverage Gaps

### Missing Tests for `NpyWriter` Inconsistent Subcarrier Handling

- **What's not tested:** The `_flush_node` method's fallback path when subcarrier counts are inconsistent (lines 92-108 in `persistence.py`).
- **Files:** `aggregator/persistence.py` (lines 92-108)
- **Risk:** Frame data is silently dropped when subcarrier counts vary. If this logic has a bug, datasets are silently corrupted.
- **Priority:** Medium

### Missing Tests for CLI Argument Combinations

- **What's not tested:** The `test_integration.py` CLI test (`TestCLI`) only tests one argument combination. Edge cases (missing args, invalid values, --rotation-frames=0) are not tested.
- **Files:** `aggregator/main.py` (lines 83-122), `aggregator/test_integration.py` (lines 158-176)
- **Risk:** Invalid CLI args could crash the process silently.
- **Priority:** Low

### Missing Tests for Signal Handling

- **What's not tested:** The `SIGINT`/`SIGTERM` handling and graceful shutdown sequence.
- **Files:** `aggregator/main.py` (lines 59-80)
- **Risk:** Graceful shutdown is fragile on Windows and untested on Unix.
- **Priority:** Medium

### No Firmware Tests

- **What's not tested:** All C firmware code (395 lines) — frame serialization, NVS config loading, rate limiting, UDP streaming, WiFi reconnection logic.
- **Files:** All files in `firmware/esp32-csi-node/main/`
- **Risk:** Every firmware change must be tested manually on hardware. No regression safety.
- **Priority:** High

---

*Concerns audit: 2026-05-01*
