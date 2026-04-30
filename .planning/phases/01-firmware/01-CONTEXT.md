# Phase 1: Firmware & Flashing - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Both ESP32-S3 nodes capture and stream CSI to aggregator. Firmware built with ESP-IDF v5.2, flashed to 2x ESP32-S3-DevKitC-1 boards. Nodes connect to WiFi, capture CSI via `esp_wifi_set_csi_rx_cb()`, serialize into binary UDP frames, and stream to aggregator IP.

</domain>

<decisions>
## Implementation Decisions

### WiFi Topology
- **D-01:** Both nodes operate as STA (station) connecting to existing WiFi router
  - Rationale: Uses existing infrastructure; both stream to aggregator IP directly; cleanest separation of concerns
  - Rejected: AP+STA (locks fixed TX/RX roles), APSTA (overly complex for 2-node setup)

### CSI Sampling Rate
- **D-02:** Default sampling rate 50 Hz (200 frames per 4-second window)
  - Rationale: Matches standard HAR window size; good temporal resolution; manageable UDP bandwidth (~6 KB/s/node with rich format)
  - Firmware supports runtime config to 100 Hz for transition-heavy experiments

### Provisioning Strategy
- **D-03:** Serial Python script provisioning (`provision.py` via USB-UART)
  - Rationale: User explicitly chose RuView-style approach; no reflash needed to change WiFi credentials; stores SSID/password/target IP in NVS flash
  - Rejected: Hardcoded (inflexible), SmartConfig (overly complex for v1)

### UDP Frame Format
- **D-04:** Rich binary frame format
  - Header: magic `0xC511_0001` (4 bytes)
  - Metadata: node_id (1 byte), sequence (4 bytes), timestamp_ms (4 bytes), RSSI (1 byte), noise_floor (1 byte)
  - Payload: 52 subcarriers × I/Q pairs (104 bytes), total ~121 bytes per frame
  - CRC-16 (2 bytes) for integrity validation
  - Rationale: User explicitly chose; minimal bandwidth overhead (~8 bytes vs minimal) but provides critical diagnostics

### Node Role Assignment
- **D-05:** Node roles fixed at provisioning time
  - Node 0: CSI TX (generates traffic) + CSI RX (captures)
  - Node 1: CSI RX only (captures reflected signal)
  - Both nodes stream their captured CSI to the same aggregator IP

### the agent's Discretion
- Exact ESP-IDF component structure (follow RuView reference)
- Build system: `idf.py` with custom partitions table
- Flashing tool: `esptool.py` or `idf.py flash`
- LED indicators for WiFi connection status (optional)

</decisions>

<specifics>
## Specific Ideas

- Follow RuView firmware structure in `llm-wiki/raw/RuView/firmware/esp32-csi-node/` as canonical reference
- `provision.py` should support setting: WiFi SSID, WiFi password, aggregator IP, UDP port, node ID, sampling rate
- Binary frame format must match parser in Phase 2 exactly — coordinate with aggregator developer

</specifics>

<canonical_refs>
## Canonical References

### Firmware reference
- `llm-wiki/raw/RuView/firmware/esp32-csi-node/` — RuView reference firmware structure
- `llm-wiki/raw/RuView/firmware/esp32-csi-node/README.md` — Build and flash instructions
- `llm-wiki/raw/RuView/firmware/esp32-csi-node/provision.py` — Serial provisioning tool reference
- `llm-wiki/raw/RuView/docs/adr/ADR-012-esp32-csi-sensor-mesh.md` — Mesh architecture decisions
- `llm-wiki/raw/RuView/docs/adr/ADR-018-esp32-dev-implementation.md` — Binary frame format specification

### ESP-IDF docs
- ESP-IDF v5.2 CSI API: `esp_wifi_set_csi_rx_cb()`, `wifi_csi_info_t` structure
- ESP32-S3 Technical Reference Manual — WiFi chapter

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `llm-wiki/raw/RuView/firmware/esp32-csi-node/` — Full working firmware with CSI capture, UDP streaming, and provisioning
- `llm-wiki/raw/RuView/firmware/esp32-csi-node/provision.py` — Python serial provisioning tool (16KB)

### Established Patterns
- Binary UDP frame with magic header + metadata + payload
- NVS flash for persistent config (SSID, password, target IP)
- `idf.py` build system with custom partitions

### Integration Points
- Phase 2 aggregator expects UDP frames on port 5005 with magic `0xC511_0001`
- Phase 5 dataset collection needs consistent frame format for `.npy`/`.csv` export

</code_context>

<deferred>
## Deferred Ideas

- AP+STA mode for standalone operation without router — future phase if router unavailable
- SmartConfig/WPS provisioning — v2 user experience improvement
- OTA firmware updates — v2 feature
- LED status indicators — nice-to-have, not critical for v1

---

*Phase: 01-firmware*
*Context gathered: 2026-04-30*
