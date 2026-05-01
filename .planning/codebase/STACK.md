# Technology Stack

**Analysis Date:** 2026-05-01

## Languages

**Primary:**
- **C (C11)** - ESP32-S3 firmware (`firmware/esp32-csi-node/main/`), 4 source files (`main.c`, `csi_collector.c`, `stream_sender.c`, `nvs_config.c`). Compiled with `idf.py` (ESP-IDF v5.2 toolchain). No unit test framework in C; testing is done via Python integration tests.
- **Python 3.10+** - Aggregator backend (`aggregator/`), provisioning script (`firmware/esp32-csi-node/provision.py`), visualization (`scripts/view_csi.py`), and test utilities (`firmware/esp32-csi-node/test/`).

**Secondary:**
- **JavaScript/HTML** - Legacy web dashboard prototype in `firmware/esp32-csi-node/test/web_aggregator.py` (embedded HTML template with Chart.js, not part of main application).

## Runtime

**Environment:**
- **ESP32-S3** (Xtensa LX7 dual-core) - Firmware target, runs FreeRTOS as the RTOS layer.
- **CPython 3.10+** - Aggregator runs on host machine (Windows/Linux/macOS).

**Package Manager:**
- **pip** - Python dependencies manager
- Lockfile: **None** (bare `requirements.txt` without version pinning — only minimum versions)

**Build Tool:**
- **ESP-IDF v5.2** (Espressif IoT Development Framework) - CMake-based build system for firmware
- **Docker** - `espressif/idf:v5.2` image used for firmware builds (`build_firmware.ps1`)
- **esptool** - Flashing firmware and provisioning NVS partitions to ESP32-S3 via serial

## Frameworks

**Embedded:**
- **ESP-IDF v5.2** - Core framework providing WiFi, LWIP TCP/IP stack, NVS flash storage, FreeRTOS task scheduler, event loops, and hardware abstraction.
- **FreeRTOS** - Real-time OS for ESP32-S3, provides tasks, event groups, and timers.

**Python Core:**
- **asyncio** - Async I/O framework for the UDP aggregator server (`aggregator/server.py`, `aggregator/main.py`). Single-threaded event loop with cooperative multitasking.

**Testing:**
- **pytest 7.0+** - Python test runner (`aggregator/test_*.py`). Used for unit, integration, and fuzz testing.
- **pytest-asyncio 0.21+** - Async test support for asyncio-based server tests.

**Data & Visualization:**
- **NumPy 1.24+** - Data persistence (`.npy` files) and array manipulation (`aggregator/persistence.py`, `scripts/view_csi.py`).
- **Matplotlib** - Heatmap visualization in `scripts/view_csi.py`.

**Provisioning:**
- **esptool** - Flashing firmware and NVS partition to ESP32-S3 via UART.
- **esp-idf-nvs-partition-gen** - Generating NVS binary blobs from CSV descriptions (`provision.py`).

## Key Dependencies

**Critical:**
- `espressif/idf:v5.2` (Docker image) — Required to build firmware. No alternative build path.
- `esptool` — Required for flashing and provisioning. No alternative.
- `numpy>=1.24.0` — Required for data persistence. No alternative.
- `pyserial` — Serial communication with ESP32-S3 for firmware upload and NVS provisioning.

**Infrastructure:**
- `lwip` (ESP-IDF component) — TCP/IP stack on ESP32-S3, provides UDP sockets.
- `esp_wifi` (ESP-IDF component) — WiFi STA mode and CSI data collection.
- `nvs_flash` (ESP-IDF component) — Non-volatile storage for device configuration.
- `freertos` (ESP-IDF component) — Task scheduling and event synchronization.

## Configuration

**Environment:**
- Firmware configured via **NVS** (Non-Volatile Storage) written by `provision.py` over serial.
  - NVS partition at offset `0x9000`, size `0x6000` (24KB)
  - Stored under namespace `csi_cfg`: `ssid`, `password`, `target_ip`, `target_port`, `node_id`
  - Connects to WiFi as STA, streams CSI UDP packets to `target_ip:target_port`
- Python aggregator configured via **CLI arguments**:
  - `--port` (default: 5005)
  - `--buffer-capacity` (default: 500 frames)
  - `--output-dir` (default: `data/raw`)
  - `--rotation-frames` (default: 10000)
  - `--log-level` (default: INFO)

**Build:**
- Firmware: `CMakeLists.txt` (ESP-IDF component registration), `sdkconfig.defaults` (target + CSI + WiFi enabled), `partitions.csv` (NVS/PHY/APP flash layout)
- Python: No build step, no `setup.py` or `pyproject.toml`

## Platform Requirements

**Development:**
- **Windows** (primary dev environment per README — PowerShell, COM ports)
- Python 3.10+ with `esptool`, `pyserial`, `esp-idf-nvs-partition-gen`, `numpy`, `matplotlib`
- Docker Desktop (for firmware builds via `espressif/idf:v5.2`)
- ESP32-S3-DevKitC-1 board(s) with CP210x USB-UART driver
- Serial ports (e.g., COM5, COM6) for firmware flashing and provisioning

**Production:**
- Deployment target: **Local** — ESP32-S3 nodes + host machine running Python aggregator
- No cloud infrastructure, no container orchestration, no CI/CD pipeline detected

## Project File Layout

```
wallhack/
├── aggregator/                        # Python asyncio UDP aggregator
│   ├── __init__.py
│   ├── __main__.py                    # Entry: `python -m aggregator`
│   ├── main.py                        # CLI + asyncio orchestration
│   ├── server.py                      # CsiUdpServer (asyncio DatagramProtocol)
│   ├── parser.py                      # Binary CSI frame parser (ADR-018)
│   ├── buffer.py                      # Per-node ring buffer (drop-oldest)
│   ├── frame.py                       # CSIFrame dataclass
│   ├── persistence.py                 # NpyWriter (amplitudes → .npy + JSON metadata)
│   ├── test_parser.py                 # Unit tests: parser
│   ├── test_server.py                 # Unit tests: buffer + server
│   └── test_integration.py            # Integration tests: persistence + UDP + CLI
├── firmware/
│   └── esp32-csi-node/                # ESP32-S3 firmware
│       ├── CMakeLists.txt             # ESP-IDF project definition
│       ├── sdkconfig.defaults          # Build config defaults
│       ├── partitions.csv             # Flash partition table
│       ├── build_firmware.ps1         # PowerShell build script (Docker)
│       ├── build_firmware.bat         # CMD build script
│       ├── provision.py               # NVS provisioning via serial
│       ├── version.txt                # v1.0.0
│       ├── main/
│       │   ├── CMakeLists.txt         # Component registration
│       │   ├── main.c                 # app_main: WiFi init, CSI start, streaming
│       │   ├── csi_collector.c/.h     # CSI data collection via esp_wifi CSI API
│       │   ├── stream_sender.c/.h     # UDP streaming over LWIP sockets
│       │   └── nvs_config.c/.h        # NVS config loading
│       └── test/
│           ├── test_udp.py            # Simple UDP listener test
│           └── web_aggregator.py      # Flask/SocketIO real-time dashboard (prototype)
├── scripts/
│   └── view_csi.py                    # Heatmap visualization via matplotlib
├── data/
│   └── raw/                           # Session data output directory
│── requirements.txt                   # Python dependencies (numpy, pytest, pytest-asyncio)
└── README.md                          # Setup guide (Vietnamese)
```

---

*Stack analysis: 2026-05-01*
