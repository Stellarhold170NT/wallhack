# ESP32-S3 CSI Wallhack - Setup Guide

Hướng dẫn thiết lập nhanh hệ thống thu thập dữ liệu CSI từ 2 Node ESP32-S3.

## 1. Cài đặt môi trường (Python)
Cài đặt các công cụ cần thiết để nạp firmware và xử lý dữ liệu:
```powershell
pip install esptool pyserial esp-idf-nvs-partition-gen numpy matplotlib
```

## 2. Thiết lập Node cảm biến

### Node 1 (COM5)
1. **Nạp Firmware**:
   ```powershell
   python -m esptool --chip esp32s3 --port COM5 --baud 460800 write_flash 0x0 build/bootloader/bootloader.bin 0x8000 build/partition_table/partition-table.bin 0x10000 build/esp32-csi-node.bin
   ```
2. **Cấu hình (Wifi, IP đích, ID)**:
   ```powershell
   python provision.py --port COM5 --ssid "VIET HUY" --password "12345678" --target-ip 192.168.1.3 --node-id 1
   ```
3. **Kiểm tra**: `python -m serial.tools.miniterm COM5 115200` (Phải thấy log "CSI streaming active").

### Node 2 (COM6)
Thực hiện tương tự Node 1, thay đổi `--port COM6` và `--node-id 2`.

---

## 3. Vận hành hệ thống (Phase 2 & 3)

Hệ thống tích hợp sẵn bộ xử lý tín hiệu (Phase 3). Khi bạn chạy Aggregator, nó sẽ tự động phát hiện và kích hoạt `CsiProcessor` để lọc nhiễu và trích xuất đặc trưng trong thời gian thực.

### Chạy trực tiếp (Real-time)
Mở terminal tại thư mục gốc:
```powershell
# Chạy với log thông thường
python -m aggregator --port 5005

# Xem chi tiết quá trình xử lý (Debug)
python -m aggregator --port 5005 --log-level INFO
```
*   **Dấu hiệu hoạt động:** Bạn sẽ thấy dòng `INFO aggregator: CsiProcessor wired into pipeline`.
*   **Log đầu ra:** Hệ thống sẽ in log mỗi khi trích xuất xong một "Feature Vector".

### Cấu hình nâng cao (Tùy chỉnh)
Bạn có thể điều chỉnh tham số xử lý bằng JSON:
```powershell
python -m aggregator --processor-config '{"window_size": 200, "step_size": 100}'
```

---

## 4. Công cụ hỗ trợ Phase 3

### Xử lý Offline (Offline Processing)
Bạn có thể chạy riêng bộ xử lý trên dữ liệu đã ghi lại:
```powershell
python -m processor --input data/raw/node_1_record.npy
```

### Kiểm tra thuật toán (Testing)
Đảm bảo các bộ lọc (Hampel, Phase Unwrap) hoạt động chính xác:
```powershell
pytest tests/
```

## 5. Xem dữ liệu (Visualizer)
Dùng script để xem bản đồ nhiệt (Heatmap) từ dữ liệu đã thu thập:
```powershell
python scripts/view_csi.py <tên_session_trong_data_raw>
```

<img width="1911" height="1019" alt="image" src="https://github.com/user-attachments/assets/0320c389-4dfe-4cd8-aa64-12579f8128af" />
