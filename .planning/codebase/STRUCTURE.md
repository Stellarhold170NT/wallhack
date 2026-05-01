# Codebase Structure

**Analysis Date:** 2026-05-01

## Directory Layout

```
wallhack/
├── .agents/                           # Project agent skills
│   └── skills/                        # Skill definitions
├── .opencode/                         # OpenCode platform config
├── .planning/                         # GSD planning artifacts
│   ├── codebase/                      # Codebase analysis docs (this dir)
│   ├── config.json
│   ├── phases/                        # Phase plans
│   ├── research/                      # Research artifacts
│   ├── PROJECT.md
│   ├── REQUIREMENTS.md
│   ├── ROADMAP.md
│   └── STATE.md
├── .sisyphus/                         # Dev workflow state
├── aggregator/                        # Python CSI aggregator (main application)
├── data/                              # CSI data storage
│   └── raw/                           # Collected session data (.npy + .json)
├── docs/                              # Project documentation
│   └── agents/                        # Agent workflow docs
├── firmware/                          # ESP32-S3 firmware (C/ESP-IDF)
│   └── esp32-csi-node/                # CSI node firmware with build infra
├── llm-wiki/                          # Karpathy-style LLM knowledge wiki
│   ├── raw/                           # Immutable source documents
│   └── SKILL.md                       # Wiki management skill
├── scripts/                           # Utility scripts
├── AGENTS.md                          # Agent skills configuration
├── README.md                          # Setup guide
├── requirements.txt                   # Python dependencies
└── skills-lock.json                   # Locked skill versions
```

## Directory Purposes

**`aggregator/`:**
- Purpose: Core Python application — receives, parses, buffers, and persists CSI data from ESP32-S3 nodes over UDP
- Contains: 7 Python modules (3 test files + 4 production modules) plus `__init__.py` and `__main__.py`
- Key files:
  - `__main__.py`: Entry point for `python -m aggregator`
  - `main.py`: CLI argument parsing, asyncio orchestration, consumer loop
  - `server.py`: `CsiUdpServer` — asyncio `DatagramProtocol` UDP receiver with dynamic node discovery and health tracking
  - `parser.py`: `parse_frame()` — binary frame parser for ADR-018 format
  - `frame.py`: `CSIFrame` dataclass — parsed frame representation
  - `buffer.py`: `NodeBuffer` — per-node ring buffer with drop-oldest semantics
  - `persistence.py`: `NpyWriter` — amplitude accumulator with `.npy` + `.json` output and auto-rotation
  - `test_parser.py`: Unit tests for `parse_frame()` (Wave 1)
  - `test_server.py`: Unit tests for `NodeBuffer` and `CsiUdpServer` (Wave 2)
  - `test_integration.py`: Integration tests for persistence, end-to-end UDP, CLI, graceful shutdown (Wave 3)

**`data/raw/`:**
- Purpose: Persistent storage for collected CSI sessions
- Contains: Timestamped subdirectories (`YYYY-MM-DD_HH-MM/`) with per-node `.npy` (amplitude matrices, float32) and `.json` (metadata) files
- Generated: Yes — created by `NpyWriter` during aggregator runs
- Committed: Currently contains 4 empty session directories (files not tracked?)

**`firmware/esp32-csi-node/`:**
- Purpose: ESP32-S3 firmware for capturing and streaming WiFi CSI data
- Contains: C source code, CMake build system, Docker-based build scripts, provisioning tool
- Key files:
  - `main/main.c`: Application entry point — NVS init, WiFi connect, subsystem init
  - `main/csi_collector.c`: ESP-IDF WiFi CSI callback registration, rate-limiting, ADR-018 serialization
  - `main/stream_sender.c`: UDP socket creation, datagram send, ENOMEM backoff
  - `main/nvs_config.c`: Read WiFi/node config from NVS flash with compiled defaults
  - `provision.py`: Python script to flash NVS config via serial
  - `CMakeLists.txt`: Top-level ESP-IDF project
  - `partitions.csv`: Flash partition table (NVS + phy_init + factory app)
  - `sdkconfig.defaults`: Default sdkconfig (ESP32-S3 target, CSI enabled)
  - `build_firmware.ps1` / `build_firmware.bat`: Docker-based build scripts
  - `version.txt`: Firmware version "1.0.0"
  - `test/test_udp.py`: Raw UDP listener for firmware testing
  - `test/web_aggregator.py`: Flask + WebSocket real-time dashboard with Chart.js (prototype)

**`scripts/`:**
- Purpose: Standalone utility scripts for data exploration
- Key files:
  - `view_csi.py`: matplotlib heatmap viewer for recorded sessions — CLI arg is session directory name

**`docs/`**:
- Purpose: Developer documentation and agent workflow guidance
- Contains: `agents/` subdirectory with `domain.md`, `issue-tracker.md`, `triage-labels.md`

**`llm-wiki/`**:
- Purpose: Persistent knowledge base using Karpathy-style LLM wiki pattern
- Contains: `raw/` (immutable source documents including RuView reference project analysis), `SKILL.md` (wiki management rules)

## Key File Locations

**Entry Points:**
- `aggregator/__main__.py`: Python aggregator — run via `python -m aggregator`
- `aggregator/main.py:main()`: CLI argument parser and asyncio runner
- `firmware/esp32-csi-node/main/main.c:app_main()`: ESP32 firmware entry
- `firmware/esp32-csi-node/provision.py:main()`: NVS provisioning tool
- `scripts/view_csi.py`: Session data visualizer

**Configuration:**
- `requirements.txt`: Python dependencies (numpy, pytest, pytest-asyncio)
- `firmware/esp32-csi-node/sdkconfig.defaults`: ESP-IDF Kconfig defaults
- `firmware/esp32-csi-node/partitions.csv`: Flash memory layout
- `firmware/esp32-csi-node/main/nvs_config.h`: NVS config struct definition

**Core Logic:**
- `aggregator/server.py`: `CsiUdpServer` — UDP reception + node management
- `aggregator/parser.py`: `parse_frame()` — binary protocol parsing
- `aggregator/buffer.py`: `NodeBuffer` — bounded per-node storage
- `aggregator/persistence.py`: `NpyWriter` — data persistence
- `firmware/esp32-csi-node/main/csi_collector.c`: CSI capture + serialization
- `firmware/esp32-csi-node/main/stream_sender.c`: UDP transmission

**Testing:**
- `aggregator/test_parser.py`: Frame parser unit tests
- `aggregator/test_server.py`: Buffer + server unit tests
- `aggregator/test_integration.py`: Integration tests (persistence, UDP e2e, CLI)
- `firmware/esp32-csi-node/test/test_udp.py`: Simple UDP listener for firmware testing
- `firmware/esp32-csi-node/test/web_aggregator.py`: Flask/WebSocket real-time dashboard prototype

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` — e.g., `frame.py`, `persistence.py`, `test_integration.py`
- C source: `snake_case.c` — e.g., `csi_collector.c`, `stream_sender.c`
- C headers: `snake_case.h` — e.g., `csi_collector.h`, `nvs_config.h`
- PowerShell: `PascalCase.ps1` — `build_firmware.ps1`
- Batch: `snake_case.bat` — `build_firmware.bat`
- Data files: `node_{id}_{timestamp}_{batch:04d}.npy` — `node_1_20260501_0918_0001.npy`
- Metadata: Same stem as data file with `.json` extension
- Session directories: `YYYY-MM-DD_HH-MM` — `2026-05-01_09-18`
- Test files: `test_{module}.py` — co-located with source in the same package directory

**Directories:**
- All lowercase with kebab-case: `llm-wiki/`, `esp32-csi-node/`
- Exceptions: `.agents/`, `.opencode/`, `.planning/`, `.sisyphus/` (dot-prefixed tool dirs)

**Classes:**
- Python: `PascalCase` — `CsiUdpServer`, `NodeBuffer`, `NodeState`, `NpyWriter`, `CSIFrame`
- C: `snake_case` — `nvs_config_t`, `csi_collector_init()`, `stream_sender_send()`

**Functions:**
- Python: `snake_case` — `parse_frame()`, `flush_all()`, `build_frame()`
- C: `snake_case` with module prefix — `csi_collector_init()`, `csi_serialize_frame()`, `stream_sender_send()`

**Constants:**
- Python: `UPPER_SNAKE_CASE` — `CSI_MAGIC`, `CSI_HEADER_SIZE`
- C: `UPPER_SNAKE_CASE` — `CSI_MAGIC`, `CSI_HEADER_SIZE`, `NVS_CFG_SSID_MAX`
- C `#define` macros: `UPPER_SNAKE_CASE` — `WIFI_CONNECTED_BIT`, `MAX_RETRY`, `ENOMEM_COOLDOWN_MS`

**Types:**
- Python: `PascalCase` — `CSIFrame` (dataclass)
- C: `snake_case_t` suffix — `nvs_config_t`, `wifi_csi_info_t` (ESP-IDF type)
- Python type hints: Use `| None` syntax (Python 3.10+), e.g., `asyncio.Task | None`, `int | None`

## Where to Add New Code

**New Aggregator Feature:**
- Primary code: `aggregator/<module>.py`
- Tests: `aggregator/test_<module>.py` (co-located in same package)
- Examples: Add signal processing -> `aggregator/processor.py` + `aggregator/test_processor.py`

**New Firmware Module (ESP32-C):**
- Implementation: `firmware/esp32-csi-node/main/<module>.c`
- Header: `firmware/esp32-csi-node/main/<module>.h`
- Register in: `firmware/esp32-csi-node/main/CMakeLists.txt` (add to `SRCS` and `INCLUDE_DIRS`)
- Initialize in: `firmware/esp32-csi-node/main/main.c` (`app_main()`)

**New Build Target or Config:**
- ESP-IDF config: `firmware/esp32-csi-node/sdkconfig.defaults`
- Partition layout: `firmware/esp32-csi-node/partitions.csv`
- Docker build: Edit `build_firmware.ps1` or `build_firmware.bat`

**New Script/Utility:**
- Python scripts: `scripts/<name>.py`
- No package structure needed — standalone scripts with CLI args

**New Session Data:**
- Automatically created by `NpyWriter` in `data/raw/<YYYY-MM-DD_HH-MM>/`
- Manual data should follow the same convention for compatibility with `view_csi.py`

**New Wiki Content:**
- Sources: `llm-wiki/raw/<topic>/<date>-<slug>.md`
- Compiled articles: `llm-wiki/wiki/<topic>/<article>.md`
- See `llm-wiki/SKILL.md` for full workflow

## Special Directories

**`.agents/`:**
- Purpose: Project-specific agent skill definitions
- Generated: No
- Committed: Yes

**`.opencode/`:**
- Purpose: OpenCode IDE settings and workspace config
- Generated: Partial (some artifacts may be generated)
- Committed: Yes

**`.planning/`:**
- Purpose: GSD (Goal-oriented Software Development) planning artifacts — roadmap, phases, requirements, codebase maps
- Generated: Yes (by GSD workflow commands)
- Committed: Yes (tracked alongside code for persistent planning)

**`.sisyphus/`:**
- Purpose: Developer workflow state (Sisyphus system)
- Generated: Yes
- Committed: Probably no (runtime state)

**`build/` (in firmware):**
- Purpose: ESP-IDF build output (compiled binaries, object files)
- Location: `firmware/esp32-csi-node/build/`
- Generated: Yes (by Docker build)
- Committed: No (in `.gitignore`)

**`__pycache__/` (in aggregator):**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No

---

*Structure analysis: 2026-05-01*
