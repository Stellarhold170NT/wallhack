# Plan 01-01 Summary: Project Scaffolding

**Status:** Complete
**Commit:** 1f46096
**Date:** 2026-04-30

## What Was Built

ESP-IDF v5.2 project structure for ESP32-S3 CSI streaming firmware.

### Files Created

| File | Purpose |
|------|---------|
| `firmware/esp32-csi-node/CMakeLists.txt` | Top-level CMake project definition |
| `firmware/esp32-csi-node/version.txt` | Firmware version (1.0.0) |
| `firmware/esp32-csi-node/sdkconfig.defaults` | Default build config with CSI enabled |
| `firmware/esp32-csi-node/partitions.csv` | 4MB flash partition table |
| `firmware/esp32-csi-node/main/CMakeLists.txt` | Component build with 4 source files |
| `firmware/esp32-csi-node/main/nvs_config.h` | Runtime config struct and loader API |
| `firmware/esp32-csi-node/main/csi_collector.h` | CSI capture API with magic 0xC5110001 |
| `firmware/esp32-csi-node/main/stream_sender.h` | UDP sender API |

### Key Design Decisions

- **Magic number:** `0xC5110001` per ADR-018
- **CSI enabled:** `CONFIG_ESP_WIFI_CSI_ENABLED=y`
- **Target:** ESP32-S3 (`CONFIG_IDF_TARGET="esp32s3"`)
- **Source files:** Exactly 4 (main.c, csi_collector.c, stream_sender.c, nvs_config.c)

## Verification

- [x] All 8 files exist with correct content
- [x] sdkconfig.defaults contains `CONFIG_ESP_WIFI_CSI_ENABLED=y`
- [x] partitions.csv has nvs at 0x9000 size 0x6000
- [x] No deferred modules referenced (edge_processing, wasm, ota, display)

## Next Step

Plan 01-02: Core C modules (csi_collector.c, stream_sender.c, nvs_config.c)
