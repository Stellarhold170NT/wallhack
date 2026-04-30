# Plan 01-03 Summary: Integration, Provisioning, Build Scripts

**Status:** Complete
**Commit:** e70dc19
**Date:** 2026-04-30

## What Was Built

Final integration and tooling for the ESP32-S3 CSI streaming firmware.

### Files Created

| File | Purpose |
|------|---------|
| `main/main.c` | Application entry point — WiFi STA init, module wiring, keep-alive loop |
| `provision.py` | Serial provisioning tool — writes WiFi credentials to NVS via USB-UART |
| `build_firmware.ps1` | PowerShell Docker build script (ESP-IDF v5.2) |
| `build_firmware.bat` | Batch Docker build script (ESP-IDF v5.2) |
| `README.md` | Build/flash/provision/verify instructions + ADR-018 frame format spec |

### Key Implementation Details

- **WiFi STA mode:** Connects to existing router with WPA2-PSK or open auth
- **Retry logic:** MAX_RETRY=10 with connection logging
- **Provisioning:** 6 CLI args (`--port`, `--ssid`, `--password`, `--target-ip`, `--target-port`, `--node-id`)
- **NVS flash:** Writes to partition offset 0x9000, size 0x6000
- **Build:** Docker container `espressif/idf:v5.2` with `idf.py set-target esp32s3 && idf.py build`

## Verification

- [x] main.c initializes NVS, WiFi STA, UDP sender, CSI collector in correct order
- [x] No v2 module references (edge_processing, wasm, ota, display, etc.)
- [x] provision.py supports all 6 required CLI arguments
- [x] Build scripts reference correct Docker image and paths
- [x] README.md documents full workflow and ADR-018 frame format

## Phase 1 Complete

All 3 waves executed successfully:
- **Wave 1 (01-01):** Project scaffolding and header files — commit 1f46096
- **Wave 2 (01-02):** Core C modules — commit 781d1c0
- **Wave 3 (01-03):** Integration and tooling — commit e70dc19

### Artifacts Summary

| Artifact | Location |
|----------|----------|
| Firmware source | `firmware/esp32-csi-node/main/` |
| Build scripts | `firmware/esp32-csi-node/build_firmware.ps1`, `.bat` |
| Provisioning tool | `firmware/esp32-csi-node/provision.py` |
| Documentation | `firmware/esp32-csi-node/README.md` |
| Plan summaries | `.planning/phases/01-firmware/01-0{1,2,3}-SUMMARY.md` |

## Next Step

Phase 2: UDP Aggregator — Python asyncio server that receives CSI streams from both nodes.
