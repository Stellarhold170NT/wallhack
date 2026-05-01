# External Integrations

**Analysis Date:** 2026-05-01

## APIs & External Services

**No external web APIs, cloud services, or third-party REST/gRPC APIs are used.**

The system operates entirely locally: ESP32-S3 sensor nodes stream UDP packets directly to a Python aggregator process on the same LAN. There is no cloud dependency, no external API key, and no internet connectivity required at runtime.

## Data Storage

**Databases:**
- **None.** No relational or NoSQL database is used.

**File Storage:**
- **Local filesystem only.** CSI amplitude data is persisted as `.npy` files (NumPy binary format) in timestamped session directories under `data/raw/`.
  - Format: `data/raw/<YYYY-MM-DD_HH-MM>/node_<id>_<timestamp>_<batch>.npy`
  - Each `.npy` file contains a float32 matrix of shape `(frames, n_subcarriers)`
  - Companion `.json` metadata: `node_id`, `start_time`, `frame_count`, `shape`
  - Rotation: configurable via `--rotation-frames` (default 10,000 frames per file)
  - Implementation: `aggregator/persistence.py` — `NpyWriter` class

**File Storage (Firmware):**
- **ESP32-S3 NVS (Non-Volatile Storage)** — Stores WiFi credentials and aggregator target config.
  - Partition: offset `0x9000`, size `0x6000` (24KB)
  - Namespace: `csi_cfg`
  - Keys: `ssid` (string), `password` (string), `target_ip` (string), `target_port` (u16), `node_id` (u8)
  - Provisioned via serial using `esptool` + `nvs-partition-gen` by `provision.py`
  - Read at boot by `firmware/esp32-csi-node/main/nvs_config.c`

**Caching:**
- **None.** The aggregator uses an in-memory `asyncio.Queue` and per-node ring buffers (`NodeBuffer` with capacity 500 frames) for transient buffering, but no external caching layer.

## Authentication & Identity

**Auth Provider:**
- **None.** No user authentication, no API keys.

**Device Identity:**
- Nodes are identified by a `node_id` (uint8) set during provisioning. This ID is embedded in each CSI frame header (byte offset 4).

## Monitoring & Observability

**Error Tracking:**
- **None.** No Sentry, Datadog, or similar service.

**Logs:**
- **Python `logging` module** — Console logging with configurable levels (DEBUG/INFO/WARNING/ERROR). Format: `%(asctime)s %(levelname)s %(name)s: %(message)s`.
- **ESP-IDF `esp_log.h`** — Firmware logging over UART serial at 115200 baud.

**Health Metrics:**
- In-band: `CsiUdpServer` logs per-node FPS, total frames, dropped frames, and sequence loss every second.
- Stale node detection: marks nodes as stale after 10s of inactivity.
- Sustained loss alerts (>5% over 10s window) logged as WARNING.

## CI/CD & Deployment

**Hosting:**
- **None.** No cloud deployment. Runs on local hardware.

**CI Pipeline:**
- **None detected.** No GitHub Actions, GitLab CI, or similar configuration found.

**Firmware Build:**
- **Docker-based.** Uses `espressif/idf:v5.2` image. Build scripts: `build_firmware.ps1` (PowerShell) and `build_firmware.bat` (CMD).

## Environment Configuration

**Required env vars:**
- **None.** The aggregator uses CLI arguments only. Firmware uses NVS storage.

**Secrets location:**
- WiFi credentials are written to ESP32-S3 NVS flash via serial during provisioning (`provision.py`). They are not stored on disk long-term.

## Webhooks & Callbacks

**Incoming:**
- **None.**

**Outgoing:**
- **None.**

## Communication Protocol

**Node → Aggregator (Primary Data Path):**
- **Transport:** UDP (raw datagrams, no TCP)
- **Default port:** 5005
- **Rate:** ~50 Hz (20ms minimum interval enforced by firmware rate limiter)
- **Frame format:** Proprietary binary (ADR-018), little-endian:
  - 20-byte header: magic (`0xC5110001`), node_id, antennas, n_subcarriers, frequency_mhz, sequence, rssi, noise_floor, reserved
  - Payload: I/Q interleaved int8 pairs (2 bytes per subcarrier)
  - Total: 148 bytes for 64 subcarriers

**Aggregator → Disk:**
- `numpy.save()` called by `aggregator/persistence.py` writes float32 amplitude matrices as `.npy`
- Companion `.json` written with `json.dumps()`

## Hardware Integrations

**ESP32-S3-DevKitC-1:**
- WiFi CSI (Channel State Information) collection via `esp_wifi_set_csi_config()` / `esp_wifi_set_csi_rx_cb()`
- Promiscuous mode enabled to capture all WiFi frames on the channel
- Serial connection over CP210x USB-UART for flashing and provisioning
- Two nodes currently configured (COM5/COM6 as sample ports)

**Tooling Dependencies:**
- `esptool` — Firmware flashing and NVS partition writing over serial
- `esp-idf-nvs-partition-gen` — NVS binary generation from CSV
- `pyserial` — Python serial communication
- `miniterm` — Serial console monitoring (`python -m serial.tools.miniterm`)

## Networking

**WiFi:**
- **Mode:** STA (Station) — nodes connect to an existing WiFi access point
- **Auth:** WPA2-PSK (or open network with empty password)
- **CSI:** Channel State Information extracted from received WiFi packets on the connected channel
- **No Wireshark/tcpdump integration** built-in, but recommended for debugging

**IP/UDP:**
- IPv4 only (No IPv6 support detected)
- UDP is connectionless — node sends to aggregator IP:port via `sendto()`
- Aggregator binds `0.0.0.0` to listen on all interfaces

## Docker

**Usage:** Build-time only
- Image: `espressif/idf:v5.2` — ESP-IDF build environment
- Volume: mounts `firmware/esp32-csi-node/` as `/project`
- Command: `idf.py set-target esp32s3 && idf.py build`
- Not used at runtime.

## Visualization

**Matplotlib:**
- Post-processing heatmap visualization of `.npy` session data via `scripts/view_csi.py`
- Displays amplitude matrices with `imshow()` using `cmap='jet'`
- Called manually, not part of the live pipeline

**Legacy Web Dashboard (Prototype only — `firmware/esp32-csi-node/test/web_aggregator.py`):**
- Flask + Flask-SocketIO web server on port 8080
- Real-time RSSI charting via Chart.js + Socket.IO client
- NOT part of production pipeline

---

*Integration audit: 2026-05-01*
