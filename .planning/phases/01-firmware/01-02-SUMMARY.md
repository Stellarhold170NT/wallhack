# Plan 01-02 Summary: Core C Modules

**Status:** Complete
**Commit:** 781d1c0
**Date:** 2026-04-30

## What Was Built

Three core C modules implementing the firmware's runtime configuration, CSI capture, and network transmission.

### Files Created

| File | Purpose | Key Features |
|------|---------|--------------|
| `main/nvs_config.c` | Runtime config loader | Loads 5 fields from NVS namespace "csi_cfg", Kconfig fallback, supports empty password |
| `main/csi_collector.c` | CSI capture & serialization | Registers `esp_wifi_set_csi_rx_cb`, ADR-018 binary frame format, 50 Hz rate limit, little-endian serialization |
| `main/stream_sender.c` | UDP stream sender | Creates UDP socket, sends frames to configured IP:port, ENOMEM backoff (100ms) |

### Key Implementation Details

- **ADR-018 frame layout:** magic (4B) + node_id (1B) + n_antennas (1B) + n_subcarriers (2B) + freq_mhz (4B) + sequence (4B) + RSSI (1B) + noise_floor (1B) + reserved (2B) + raw I/Q
- **Rate limiting:** 20ms minimum interval = 50 Hz cap (per D-02)
- **Frequency derivation:** 2.4GHz (2412 + (ch-1)*5) or 5GHz (5000 + ch*5)
- **ENOMEM mitigation:** 100ms cooldown when lwIP pbuf pool exhausted (T-01-05)

## Verification

- [x] All 3 files exist with correct content
- [x] `CONFIG_ESP_WIFI_CSI_ENABLED` build guard present
- [x] `esp_wifi_set_csi_rx_cb` registered in callback
- [x] `stream_sender_send` called from CSI callback
- [x] No v2 features (hopping, WASM, edge processing, MAC filter)

## Next Step

Plan 01-03: Integration (main.c), provisioning tool, build scripts
