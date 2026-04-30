# ESP32-S3 CSI Node Firmware (v1)

Streams WiFi Channel State Information (CSI) to an aggregator over UDP.

## Quick Start

### Prerequisites
- Docker Desktop
- Python 3.10+ with `esptool` and `nvs-partition-gen`
- ESP32-S3-DevKitC-1 board
- CP210x USB-UART driver

### 1. Build

**Windows (PowerShell):**
```powershell
.\build_firmware.ps1
```

**Windows (CMD):**
```batch
build_firmware.bat
```

**Manual (Docker):**
```bash
docker run --rm -v "$(pwd):/project" -w /project espressif/idf:v5.2 bash -c "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"
```

### 2. Flash

```bash
python -m esptool --chip esp32s3 --port COM7 --baud 460800 \
  write_flash --flash_mode dio --flash_size 4MB \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0x10000 build/esp32-csi-node.bin
```

### 3. Provision

```bash
python provision.py --port COM7 --ssid "MyWiFi" --password "secret" --target-ip 192.168.1.20 --node-id 1
```

Repeat for second node with `--node-id 2`.

### 4. Verify

Use Wireshark or tcpdump to capture UDP on port 5005:
```bash
tcpdump -i any -n udp port 5005 -X
```

Expected: packets starting with magic bytes `01 00 11 C5` (little-endian `0xC5110001`).

## ADR-018 Binary Frame Format

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Magic: 0xC5110001 |
| 4 | 1 | Node ID |
| 5 | 1 | Antennas |
| 6 | 2 | Subcarriers |
| 8 | 4 | Frequency MHz |
| 12 | 4 | Sequence |
| 16 | 1 | RSSI |
| 17 | 1 | Noise floor |
| 18 | 2 | Reserved |
| 20 | N | I/Q data |
