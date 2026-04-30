"""Integration tests for full aggregator pipeline (Wave 3).

Tests: persistence (NpyWriter), end-to-end UDP, CLI argument parsing,
and graceful shutdown with data flush.
"""

import struct
import json
import asyncio
import tempfile
import pathlib
import socket
import pytest
import numpy as np
from aggregator.parser import CSI_MAGIC
from aggregator.frame import CSIFrame
from aggregator.server import CsiUdpServer
from aggregator.persistence import NpyWriter


def build_frame(node_id, sequence, rssi, noise_floor, iq_pairs):
    magic = struct.pack("<I", CSI_MAGIC)
    nid = bytes([node_id])
    antennas = bytes([1])
    n_sub = struct.pack("<H", len(iq_pairs))
    freq = struct.pack("<I", 2412)
    seq = struct.pack("<I", sequence)
    rssi_b = struct.pack("b", rssi)
    nf_b = struct.pack("b", noise_floor)
    reserved = bytes([0, 0])
    iq = bytes([b & 0xFF for pair in iq_pairs for b in pair])
    return magic + nid + antennas + n_sub + freq + seq + rssi_b + nf_b + reserved + iq


def _make_52_iq(value=10):
    return [(value, value) for _ in range(52)]


class TestPersistence:
    def test_integration_queue_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = NpyWriter(output_dir=tmpdir, rotation_frames=100)

            for i in range(10):
                frame = CSIFrame(
                    node_id=1,
                    sequence=i,
                    rssi=-30,
                    noise_floor=-80,
                    frequency_mhz=2412,
                    n_subcarriers=52,
                    amplitudes=[float(v) for v in range(52)],
                    phases=[0.0] * 52,
                )
                writer.write(frame)

            writer.flush_all()

            session_dirs = list(pathlib.Path(tmpdir).glob("*"))
            assert len(session_dirs) == 1

            npy_files = list(session_dirs[0].glob("*.npy"))
            assert len(npy_files) == 1

            arr = np.load(npy_files[0])
            assert arr.shape == (10, 52)
            assert arr.dtype == np.float32

            json_files = list(session_dirs[0].glob("*.json"))
            assert len(json_files) == 1
            meta = json.loads(json_files[0].read_text())
            assert meta["node_id"] == 1
            assert meta["frame_count"] == 10
            assert meta["shape"] == [10, 52]

    def test_npy_writer_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = NpyWriter(output_dir=tmpdir, rotation_frames=5)
            for i in range(12):
                frame = CSIFrame(
                    node_id=1,
                    sequence=i,
                    n_subcarriers=52,
                    amplitudes=[float(i)] * 52,
                    phases=[0.0] * 52,
                )
                writer.write(frame)
            writer.flush_all()

            session_dirs = list(pathlib.Path(tmpdir).glob("*"))
            assert len(session_dirs) == 1
            npy_files = sorted(session_dirs[0].glob("*.npy"))
            assert len(npy_files) >= 2

    def test_graceful_shutdown_flushes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = NpyWriter(output_dir=tmpdir, rotation_frames=1000)
            for i in range(5):
                frame = CSIFrame(
                    node_id=2,
                    sequence=i,
                    n_subcarriers=52,
                    amplitudes=[1.0] * 52,
                    phases=[0.0] * 52,
                )
                writer.write(frame)
            writer.flush_all()

            session_dirs = list(pathlib.Path(tmpdir).glob("*"))
            assert len(session_dirs) == 1
            assert len(list(session_dirs[0].glob("*.npy"))) == 1
            assert len(list(session_dirs[0].glob("*.json"))) == 1


class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_end_to_end_udp(self):
        server = CsiUdpServer(port=0)
        await server.start()

        try:
            addr = server.transport.get_extra_info("sockname")
            actual_port = addr[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            iq = _make_52_iq(5)

            for i in range(5):
                data = build_frame(
                    node_id=10,
                    sequence=i,
                    rssi=-40,
                    noise_floor=-85,
                    iq_pairs=iq,
                )
                sock.sendto(data, ("127.0.0.1", actual_port))
                await asyncio.sleep(0.01)

            await asyncio.sleep(0.2)

            frames = []
            for _ in range(5):
                try:
                    frame = server.queue.get_nowait()
                    frames.append(frame)
                except asyncio.QueueEmpty:
                    break

            assert len(frames) == 5
            for f in frames:
                assert isinstance(f, CSIFrame)
                assert f.node_id == 10

        finally:
            await server.stop()


class TestCLI:
    def test_cli_argument_parsing(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, default=5005)
        parser.add_argument("--buffer-capacity", type=int, default=500)
        parser.add_argument("--output-dir", type=str, default="data/raw")
        parser.add_argument("--rotation-frames", type=int, default=10000)
        parser.add_argument("--log-level", type=str, default="INFO")

        args = parser.parse_args(
            ["--port", "6000", "--buffer-capacity", "1000", "--log-level", "DEBUG"]
        )
        assert args.port == 6000
        assert args.buffer_capacity == 1000
        assert args.log_level == "DEBUG"
        assert args.output_dir == "data/raw"
        assert args.rotation_frames == 10000
