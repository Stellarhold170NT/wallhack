import socket
import struct

# Lắng nghe tại cổng 5005
UDP_IP = "0.0.0.0"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"--- DANG THEO DOI DU LIEU CSI CHI TIET ---")

while True:
    data, addr = sock.recvfrom(2048)
    
    # Kiểm tra nếu gói tin đủ độ dài tối thiểu (ít nhất 18 bytes header)
    if len(data) >= 18:
        # Giải mã header theo cấu hình firmware của bạn
        magic = struct.unpack('<I', data[0:4])[0]
        node_id = data[4]
        seq = struct.unpack('<I', data[12:16])[0]
        rssi = data[16]
        
        # In ra thông tin chi tiết
        print(f"[Node {node_id}] Seq: {seq:5d} | RSSI: -{rssi} dBm | Len: {len(data)} bytes")
