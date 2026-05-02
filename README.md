<img width="3636" height="713" alt="image" src="https://github.com/user-attachments/assets/a48cafb3-6bf0-4f45-93ce-33b89bcc3ee7" />

# ESP32-S3 CSI Wallhack - Setup Guide

Hướng dẫn thiết lập hệ thống thu thập và phân tích dữ liệu WiFi CSI xuyên tường. Hệ thống tích hợp xử lý tín hiệu thời gian thực và phát hiện xâm nhập thông minh.

## 1. Cài đặt môi trường (Python)
Cài đặt các công cụ cần thiết để nạp firmware và xử lý dữ liệu:
```powershell
pip install esptool pyserial esp-idf-nvs-partition-gen numpy matplotlib pytest
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

Hệ thống tích hợp bộ xử lý tín hiệu `CsiProcessor` để lọc nhiễu và trích xuất đặc trưng (motion, breathing) trong thời gian thực.

### Chạy thu thập & xử lý
```powershell
# Chạy với log thông thường
python -m aggregator --port 5005

# Xem chi tiết quá trình xử lý (Debug)
python -m aggregator --port 5005 --log-level INFO
```

---

## 4. Phát hiện xâm nhập (Phase 4 - Presence Detection)

Đây là tính năng mới giúp hệ thống tự động nhận diện có người trong phòng dựa trên thuật toán Adaptive Baseline.

### Chạy hệ thống giám sát AI
```powershell
python -m aggregator --port 5005 --log-level INFO --processor-config "{\"window_size\":30,\"step_size\":15}" --detector-config "{\"enter_threshold_sigma\":2.5,\"exit_threshold_sigma\":1.5,\"enter_frames\":2,\"exit_frames\":5,\"baseline_alpha\":0.15}"
```

### Các tính năng nổi bật:
- **Adaptive Baseline (Tự học):** Hệ thống dành 10-20 giây đầu để học "độ tĩnh" của căn phòng và tự điều chỉnh khi môi trường thay đổi.
- **Hysteresis Detection:** Ngăn chặn báo động giả khi tín hiệu dao động nhẹ ở ngưỡng biên.
- **Multi-node Fusion:** Hợp nhất dữ liệu từ nhiều Node (Logic OR) để mở rộng vùng bao phủ.
- **Alert Persistence:** Cảnh báo được lưu tại `data/alerts/alerts_YYYY-MM-DD.jsonl`.

### Tùy chỉnh độ nhạy:
Bạn có thể điều chỉnh độ nhạy (Sigma) qua tham số:
```powershell
python -m aggregator --detector-config "{\"enter_threshold_sigma\": 3.0, \"cooldown_seconds\": 10.0}"
```

---

## 5. Công cụ hỗ trợ & Kiểm thử

### Xử lý Offline
Chạy bộ xử lý trên dữ liệu đã ghi lại:
```powershell
python -m processor --input data/raw/node_1_record.npy
```

### Chạy bộ Test (90+ tests)
Đảm bảo toán học và logic hệ thống hoạt động chính xác:
```powershell
$env:PYTHONPATH="."; pytest tests/
```
### Phase 6
```powershell
python -m aggregator --port 5005 --dashboard --dashboard-port 8024 --log-level INFO --classifier-config "{\"model_path\":\"models/activity/model.pth\",\"scaler_path\":\"models/activity/activity_scaler.json\",\"confidence_threshold\":0.6}"
```

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/c679775e-9734-4f29-8380-bbe0b7cd1768" />


### Xem dữ liệu (Visualizer)
Dùng script để xem bản đồ nhiệt (Heatmap):
```powershell
python scripts/view_csi.py <tên_session_trong_data_raw>
```

<img width="1911" height="1019" alt="image" src="https://github.com/user-attachments/assets/0320c389-4dfe-4cd8-aa64-12579f8128af" />
