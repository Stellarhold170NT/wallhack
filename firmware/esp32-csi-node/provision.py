#!/usr/bin/env python3
"""ESP32-S3 CSI Node Provisioning Script.

Writes WiFi credentials and aggregator target to NVS via serial.
Usage:
    python provision.py --port COM7 --ssid "MyWiFi" --password "secret" --target-ip 192.168.1.20
"""

import argparse
import csv
import io
import os
import subprocess
import sys
import tempfile

NVS_PARTITION_OFFSET = 0x9000
NVS_PARTITION_SIZE = 0x6000


def build_nvs_csv(args):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["key", "type", "encoding", "value"])
    writer.writerow(["csi_cfg", "namespace", "", ""])
    if args.ssid:
        writer.writerow(["ssid", "data", "string", args.ssid])
    if args.password is not None:
        writer.writerow(["password", "data", "string", args.password])
    if args.target_ip:
        writer.writerow(["target_ip", "data", "string", args.target_ip])
    if args.target_port is not None:
        writer.writerow(["target_port", "data", "u16", str(args.target_port)])
    if args.node_id is not None:
        writer.writerow(["node_id", "data", "u8", str(args.node_id)])
    return buf.getvalue()


def generate_nvs_binary(csv_content, size):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f_csv:
        f_csv.write(csv_content)
        csv_path = f_csv.name
    bin_path = csv_path.replace(".csv", ".bin")
    try:
        for module_name in ["esp_idf_nvs_partition_gen", "nvs_partition_gen"]:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", module_name, "generate",
                     csv_path, bin_path, hex(size)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                with open(bin_path, "rb") as f:
                    return f.read()
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        raise RuntimeError("nvs_partition_gen module not found. Install: pip install nvs-partition-gen")
    finally:
        os.unlink(csv_path)
        if os.path.exists(bin_path):
            os.unlink(bin_path)


def flash_nvs(port, nvs_bin):
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        f.write(nvs_bin)
        bin_path = f.name
    try:
        subprocess.check_call(
            [sys.executable, "-m", "esptool", "--chip", "esp32s3",
             "--port", port, "--baud", "460800",
             "write_flash", str(NVS_PARTITION_OFFSET), bin_path],
            stdout=sys.stdout, stderr=sys.stderr,
        )
    finally:
        os.unlink(bin_path)


def main():
    parser = argparse.ArgumentParser(description="Provision ESP32-S3 CSI Node")
    parser.add_argument("--port", required=True, help="Serial port (e.g. COM7 or /dev/ttyUSB0)")
    parser.add_argument("--ssid", required=True, help="WiFi SSID")
    parser.add_argument("--password", default="", help="WiFi password (empty for open network)")
    parser.add_argument("--target-ip", required=True, help="Aggregator IP address")
    parser.add_argument("--target-port", type=int, default=5005, help="Aggregator UDP port")
    parser.add_argument("--node-id", type=int, default=1, help="Node ID (0-255)")
    args = parser.parse_args()

    csv_content = build_nvs_csv(args)
    nvs_bin = generate_nvs_binary(csv_content, NVS_PARTITION_SIZE)
    flash_nvs(args.port, nvs_bin)
    print(f"Provisioned node {args.node_id}: ssid={args.ssid}, target={args.target_ip}:{args.target_port}")


if __name__ == "__main__":
    main()
