import json
import time
import socket
import argparse
import os
import numpy as np

def replay_data(data_dir, target_ip, target_port, fps):
    print(f"Replaying data from {data_dir} to {target_ip}:{target_port} @ {fps} FPS")
    
    # Find all .json files that are NOT metadata (usually have longer names)
    files = sorted([f for f in os.listdir(data_dir) if f.endswith(".json") and "node_" in f])
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    delay = 1.0 / fps
    total_sent = 0
    
    for filename in files:
        filepath = os.path.join(data_dir, filename)
        try:
            with open(filepath, 'r') as f:
                content = json.load(f)
                
            # If it's a metadata file, skip
            if "csi_matrix" not in content and "data" not in content:
                continue
                
            # Handle both list and nested formats
            csi_data = content.get("csi_matrix") or content.get("data")
            node_id = content.get("node_id", 1)
            
            if not csi_data:
                continue
                
            for frame in csi_data:
                # Construct a packet similar to the ESP32 output
                # [node_id, timestamp, ...csi...]
                packet = {
                    "type": "csi",
                    "node_id": node_id,
                    "timestamp": time.time(),
                    "csi": frame
                }
                payload = json.dumps(packet).encode('utf-8')
                sock.sendto(payload, (target_ip, target_port))
                
                total_sent += 1
                if total_sent % 100 == 0:
                    print(f"Sent {total_sent} frames...")
                
                time.sleep(delay)
                
        except Exception as e:
            print(f"Error reading {filename}: {e}")

    print(f"Finished replaying {total_sent} frames.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Directory containing raw JSON files")
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--fps", type=float, default=20)
    args = parser.parse_args()
    
    replay_data(args.dir, args.ip, args.port, args.fps)
