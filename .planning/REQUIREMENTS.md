# Requirements: ESP32-S3 CSI Wallhack

**Defined:** 2026-04-30
**Core Value:** Reliable presence detection and simple activity classification using 2 ESP32-S3 nodes — shipped within 6 weeks.

## v1 Requirements

### Hardware & Firmware

- [ ] **HW-01**: ESP32-S3 firmware captures CSI via ESP-IDF `esp_wifi_set_csi_rx_cb()` with 52 subcarriers, 20-50 Hz
- [ ] **HW-02**: Firmware serializes CSI into binary UDP frame (magic header + node_id + I/Q payload)
- [ ] **HW-03**: Provisioning tool configures WiFi SSID/password and target aggregator IP via serial
- [ ] **HW-04**: Both nodes stream CSI concurrently to aggregator on configurable UDP port

### Data Ingestion & Signal Processing

- [ ] **SIG-01**: Python aggregator receives UDP packets from 2 nodes asynchronously
- [ ] **SIG-02**: Parser validates frame magic, extracts amplitude `sqrt(I^2+Q^2)` and phase `atan2(Q,I)` per subcarrier
- [ ] **SIG-03**: Phase sanitizer unwraps phase and removes linear trend
- [ ] **SIG-04**: Hampel outlier filter removes spike artifacts per subcarrier
- [ ] **SIG-05**: Sliding window (4 seconds / ~200 frames) produces spectrogram or amplitude matrix
- [ ] **SIG-06**: Feature extraction: variance, mean amplitude, motion energy (high-frequency band power), breathing band power (0.1-0.5 Hz)

### Presence & Intrusion Detection

- [ ] **SEC-01**: Presence detector thresholds CSI variance across subcarriers; emits binary occupied/empty
- [ ] **SEC-02**: Intrusion alert triggers when presence transitions from empty → occupied with motion energy above baseline
- [ ] **SEC-03**: 2-node fusion: if either node detects presence, system reports presence (reduces blind spots)
- [ ] **SEC-04**: Alert cooldown (5s) prevents spam; alert logged with timestamp and node ID

### Activity Recognition

- [ ] **ACT-01**: Collect labeled dataset for 4 classes: empty, static (sitting/standing still), walking, waving arms
- [ ] **ACT-02**: Train lightweight classifier (SVM, Random Forest, or 2-layer CNN) on amplitude features + variance + spectrogram slices
- [ ] **ACT-03**: Real-time inference window: 4 seconds sliding with 50% overlap
- [ ] **ACT-04**: Classification output streamed to dashboard with confidence score

### Dashboard & API

- [ ] **UI-01**: Web dashboard displays real-time CSI amplitude heatmap (subcarrier × time)
- [ ] **UI-02**: Presence status indicator (green = empty, red = occupied)
- [ ] **UI-03**: Activity label display with confidence bar
- [ ] **UI-04**: Alert log panel showing intrusion events
- [ ] **UI-05**: WebSocket pushes updates to browser at 2 Hz
- [ ] **API-01**: REST endpoint `GET /status` returns current presence + activity + node health
- [ ] **API-02**: REST endpoint `GET /alerts` returns recent alert history

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Signal Processing

- **SIG-10**: Subcarrier selection via sensitivity/variance ratio (SpotFi-style)
- **SIG-11**: Doppler velocity profile extraction
- **SIG-12**: Fresnel zone modeling for approximate distance

### Enhanced Activity Recognition

- **ACT-10**: Expand to 6+ classes (falling, running, sitting, standing)
- **ACT-11**: Cross-domain generalization (train LOS, test NLOS)

### Multi-Node Features

- **MESH-01**: Auto-discovery and health monitoring of mesh nodes
- **MESH-02**: Feature-level fusion with node confidence weighting

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| People counting | 2-node deployment cannot resolve multi-person spatial separation. RuView rates 3-node as "marginal" (ADR-012). |
| Heart rate detection | ESP32-S3 CSI micro-Doppler resolution insufficient for 0.1-0.5 mm cardiac displacement (ADR-021, ADR-028). |
| Breathing rate (reliable) | Possible in theory but placement-sensitive and unreliable on ESP32-S3; deferred until proven on this hardware. |
| Pose estimation (DensePose) | Requires 4-6+ nodes + transformer/GNN backbone (RuVector). Far beyond 2-node budget. |
| On-device ML inference | ESP32-S3 has 520 KB SRAM; model quantization to 55 KB is research-level (ADR-028 gap). Not feasible in 6-week v1. |
| Through-wall depth/range | Fresnel modeling requires calibrated antenna arrays and precise TX-RX geometry. |
| Cloud / remote server | All processing local-only; no cloud dependency for v1. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HW-01 | Phase 1 | Pending |
| HW-02 | Phase 1 | Pending |
| HW-03 | Phase 1 | Pending |
| HW-04 | Phase 1 | Pending |
| SIG-01 | Phase 2 | Pending |
| SIG-02 | Phase 2 | Pending |
| SIG-03 | Phase 3 | Pending |
| SIG-04 | Phase 3 | Pending |
| SIG-05 | Phase 3 | Pending |
| SIG-06 | Phase 3 | Pending |
| SEC-01 | Phase 4 | Pending |
| SEC-02 | Phase 4 | Pending |
| SEC-03 | Phase 4 | Pending |
| SEC-04 | Phase 4 | Pending |
| ACT-01 | Phase 5 | Pending |
| ACT-02 | Phase 5 | Pending |
| ACT-03 | Phase 5 | Pending |
| ACT-04 | Phase 5 | Pending |
| UI-01 | Phase 6 | Pending |
| UI-02 | Phase 6 | Pending |
| UI-03 | Phase 6 | Pending |
| UI-04 | Phase 6 | Pending |
| UI-05 | Phase 6 | Pending |
| API-01 | Phase 6 | Pending |
| API-02 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-30*
*Last updated: 2026-04-30 after initial definition*
