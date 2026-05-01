<img width="3639" height="716" alt="image" src="https://github.com/user-attachments/assets/e91fbb8e-64b4-4b1d-95be-70b79b4a7efb" />



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

## 3. Chạy Aggregator (Phase 2)

Mở terminal tại thư mục gốc và chạy bộ gom dữ liệu chuyên nghiệp:
```powershell
# Chạy bình thường
python -m aggregator --port 5005 --output-dir data/raw

# Chạy chế độ Debug (xem chi tiết từng gói tin)
python -m aggregator --port 5005 --log-level DEBUG
```
*Ghi chú: Nhấn **Ctrl+C** để dừng và lưu dữ liệu vào file `.npy`.*

## 4. Xem dữ liệu (Visualizer)
Dùng script để xem bản đồ nhiệt (Heatmap) từ dữ liệu đã thu thập:
```powershell
python scripts/view_csi.py <tên_session_trong_data_raw>
```

<img width="1911" height="1019" alt="image" src="https://github.com/user-attachments/assets/0320c389-4dfe-4cd8-aa64-12579f8128af" />

