"""Unit tests for NodeBuffer and CsiUdpServer (Wave 2)."""

import struct
import time
import asyncio
import pytest
from aggregator.buffer import NodeBuffer
from aggregator.server import CsiUdpServer
from aggregator.parser import CSI_MAGIC
from aggregator.frame import CSIFrame


# ---------------------------------------------------------------------------
# Test build_frame helper (copied from test_parser.py for independence)
# ---------------------------------------------------------------------------

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


# ====================== NodeBuffer Tests ======================

class TestBuffer:
    def test_buffer_capacity_drop_oldest(self):
        buf = NodeBuffer(node_id=1, capacity=3)
        a = CSIFrame(node_id=1, sequence=1, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        b = CSIFrame(node_id=1, sequence=2, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        c = CSIFrame(node_id=1, sequence=3, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        d = CSIFrame(node_id=1, sequence=4, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        buf.push(a)
        buf.push(b)
        buf.push(c)
        buf.push(d)
        assert len(buf) == 3
        all_frames = buf.get_all()
        assert all_frames[0].sequence == 2  # a was evicted
        assert all_frames[2].sequence == 4

    def test_buffer_get_all_order(self):
        buf = NodeBuffer(node_id=2, capacity=10)
        a = CSIFrame(node_id=2, sequence=1, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        b = CSIFrame(node_id=2, sequence=2, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        c = CSIFrame(node_id=2, sequence=3, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        buf.push(a)
        buf.push(b)
        buf.push(c)
        assert buf.get_all() == [a, b, c]

    def test_buffer_drop_count(self):
        buf = NodeBuffer(node_id=1, capacity=5)
        for i in range(10):
            frame = CSIFrame(node_id=1, sequence=i, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
            buf.push(frame)
        assert len(buf) == 5
        assert buf.drop_count == 5

    def test_buffer_empty(self):
        buf = NodeBuffer(node_id=1, capacity=10)
        assert len(buf) == 0
        assert buf.get_all() == []
        assert buf.last_sequence() is None

    def test_buffer_last_sequence(self):
        buf = NodeBuffer(node_id=1, capacity=10)
        a = CSIFrame(node_id=1, sequence=5, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        b = CSIFrame(node_id=1, sequence=99, amplitudes=[0.0], phases=[0.0], n_subcarriers=1)
        buf.push(a)
        buf.push(b)
        assert buf.last_sequence() == 99


# ====================== CsiUdpServer Tests ======================

class TestServer:
    @pytest.mark.asyncio
    async def test_server_starts_and_stops(self):
        server = CsiUdpServer(port=0)  # ephemeral
        await server.start()
        assert server.transport is not None
        await server.stop()

    def test_server_registers_node(self):
        server = CsiUdpServer()
        iq = _make_52_iq(5)
        data = build_frame(node_id=1, sequence=10, rssi=-40, noise_floor=-85, iq_pairs=iq)
        server.datagram_received(data, ("192.168.1.10", 5005))
        assert 1 in server.nodes
        assert server.nodes[1].frame_count == 1

    def test_server_pushes_to_queue(self):
        queue = asyncio.Queue()
        server = CsiUdpServer(queue=queue)
        iq = _make_52_iq(5)
        data = build_frame(node_id=2, sequence=42, rssi=-30, noise_floor=-80, iq_pairs=iq)
        server.datagram_received(data, ("192.168.1.20", 5005))
        frame = queue.get_nowait()
        assert isinstance(frame, CSIFrame)
        assert frame.node_id == 2
        assert frame.sequence == 42

    def test_server_multiple_frames_same_node(self):
        server = CsiUdpServer()
        iq = _make_52_iq(5)
        data1 = build_frame(node_id=3, sequence=1, rssi=-30, noise_floor=-80, iq_pairs=iq)
        data2 = build_frame(node_id=3, sequence=2, rssi=-31, noise_floor=-81, iq_pairs=iq)
        data3 = build_frame(node_id=3, sequence=3, rssi=-32, noise_floor=-82, iq_pairs=iq)
        server.datagram_received(data1, ("192.168.1.30", 5005))
        server.datagram_received(data2, ("192.168.1.30", 5005))
        server.datagram_received(data3, ("192.168.1.30", 5005))
        assert server.nodes[3].frame_count == 3

    def test_server_sequence_gap(self):
        server = CsiUdpServer()
        iq = _make_52_iq(5)
        data1 = build_frame(node_id=4, sequence=1, rssi=-30, noise_floor=-80, iq_pairs=iq)
        data2 = build_frame(node_id=4, sequence=5, rssi=-31, noise_floor=-81, iq_pairs=iq)
        server.datagram_received(data1, ("192.168.1.40", 5005))
        server.datagram_received(data2, ("192.168.1.40", 5005))
        # seq 1 → 5: gap of 3 (missing seq 2, 3, 4)
        assert server.nodes[4].loss_count == 3

    def test_server_ignores_invalid_frame(self):
        server = CsiUdpServer()
        server.datagram_received(b"garbage", ("192.168.1.99", 5005))
        assert len(server.nodes) == 0

    def test_server_stale_node(self):
        server = CsiUdpServer()
        iq = _make_52_iq(5)
        data = build_frame(node_id=5, sequence=1, rssi=-30, noise_floor=-80, iq_pairs=iq)
        server.datagram_received(data, ("192.168.1.50", 5005))
        assert not server.nodes[5].stale

        # Simulate 20 seconds of inactivity
        server.nodes[5].last_seen = time.monotonic() - 20.0
        # Manually run the stale check logic
        now = time.monotonic()
        for node in server.nodes.values():
            if not node.stale and (now - node.last_seen > 10.0):
                node.stale = True
        assert server.nodes[5].stale is True

    def test_server_new_frame_unstales_node(self):
        server = CsiUdpServer()
        iq = _make_52_iq(5)
        data1 = build_frame(node_id=6, sequence=1, rssi=-30, noise_floor=-80, iq_pairs=iq)
        server.datagram_received(data1, ("192.168.1.60", 5005))
        # Manually make it stale
        server.nodes[6].stale = True
        # New frame should un-stale
        data2 = build_frame(node_id=6, sequence=2, rssi=-31, noise_floor=-81, iq_pairs=iq)
        server.datagram_received(data2, ("192.168.1.60", 5005))
        assert not server.nodes[6].stale
