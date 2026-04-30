---
status: complete
phase: 01-firmware
source: 01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md
started: 2026-04-30T18:55:00Z
updated: 2026-04-30T18:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Project Structure
expected: All files from 3 plans exist in correct locations
result: pass

### 2. Header Contracts
expected: nvs_config.h, csi_collector.h, stream_sender.h define correct APIs
result: pass

### 3. CSI Magic Number
expected: CSI_MAGIC defined as 0xC5110001 in csi_collector.h and used in csi_collector.c
result: pass

### 4. CSI Callback Registration
expected: csi_collector.c calls esp_wifi_set_csi_rx_cb with callback that serializes frames
result: pass

### 5. UDP Sender Integration
expected: CSI callback calls stream_sender_send() after serialization
result: pass

### 6. NVS Config Loading
expected: nvs_config.c loads 5 fields from NVS namespace "csi_cfg" with Kconfig fallback
result: pass

### 7. main.c Module Wiring
expected: app_main initializes NVS, loads config, starts WiFi STA, UDP sender, CSI collector
result: pass

### 8. WiFi STA Mode
expected: main.c sets WIFI_MODE_STA and connects with retry logic (MAX_RETRY=10)
result: pass

### 9. ENOMEM Backoff
expected: stream_sender.c implements 100ms cooldown on ENOMEM
result: pass

### 10. 50 Hz Rate Limit
expected: csi_rx_callback drops frames if < 20ms since last send
result: pass

### 11. Provisioning Tool
expected: provision.py supports --port, --ssid, --password, --target-ip, --target-port, --node-id
result: pass

### 12. Build Scripts
expected: PowerShell and batch scripts use Docker with espressif/idf:v5.2
result: pass

### 13. No V2 Features
expected: No references to edge_processing, wasm, ota, display, hopping, MAC filter
result: pass

### 14. README Documentation
expected: README includes build/flash/provision/verify steps and ADR-018 frame format
result: pass

### 15. ESP-IDF Build (HARDWARE REQUIRED)
expected: idf.py build produces esp32-csi-node.bin under 2MB
result: blocked
blocked_by: physical-device
reason: Requires ESP32-S3-DevKitC-1 board and ESP-IDF v5.2 Docker container

### 16. WiFi Connection Test (HARDWARE REQUIRED)
expected: Node connects to router and gets IP address
result: blocked
blocked_by: physical-device
reason: Requires flashed ESP32-S3 board and WiFi network

### 17. UDP Stream Test (HARDWARE REQUIRED)
expected: Wireshark captures UDP packets on port 5005 with magic 0xC5110001
result: blocked
blocked_by: physical-device
reason: Requires 2x ESP32-S3 boards, router, and aggregator host

## Summary

total: 17
passed: 14
issues: 0
pending: 0
skipped: 0
blocked: 3

## Gaps

None — all code-level verifications passed. 3 tests blocked pending hardware availability.
