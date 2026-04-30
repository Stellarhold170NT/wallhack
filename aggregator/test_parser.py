"""Unit tests for CSI binary frame parser (Wave 1)."""

import struct
import math
import pytest
from aggregator.parser import parse_frame, CSI_MAGIC
from aggregator.frame import CSIFrame


def build_frame(node_id, sequence, rssi, noise_floor, iq_pairs):
    """Construct a valid binary CSI frame from individual fields.

    Args:
        node_id: Node identifier (uint8).
        sequence: Frame sequence number (uint32).
        rssi: RSSI value (int8).
        noise_floor: Noise floor value (int8).
        iq_pairs: List of (I, Q) tuples, each is int8.

    Returns:
        bytes: Complete binary frame ready for parse_frame().
    """
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


def _make_64_iq(value=10):
    """Generate 64 identical (I, Q) pairs for test frames."""
    return [(value, value) for _ in range(64)]


class TestParseValidFrame:
    """Valid frame parsing tests."""

    def test_parse_valid_frame_all_fields(self):
        """Full 64-subcarrier frame parses correctly with all fields."""
        iq = _make_64_iq(10)
        data = build_frame(node_id=3, sequence=42, rssi=-55, noise_floor=-90, iq_pairs=iq)
        frame = parse_frame(data)

        assert frame is not None
        assert isinstance(frame, CSIFrame)
        assert frame.node_id == 3
        assert frame.sequence == 42
        assert frame.rssi == -55
        assert frame.noise_floor == -90
        assert frame.frequency_mhz == 2412
        assert frame.n_subcarriers == 64
        assert len(frame.amplitudes) == 64
        assert len(frame.phases) == 64

    def test_parse_valid_frame_64_subcarriers(self):
        """Parser returns exactly 64 amplitudes and phases."""
        iq = _make_64_iq(5)
        data = build_frame(node_id=1, sequence=100, rssi=-30, noise_floor=-85, iq_pairs=iq)
        frame = parse_frame(data)

        assert frame is not None
        assert frame.n_subcarriers == 64
        assert len(frame.amplitudes) == 64
        assert len(frame.phases) == 64

    def test_parse_frame_size_148_bytes(self):
        """Verify 64-subcarrier frame is exactly 148 bytes."""
        iq = _make_64_iq(0)
        data = build_frame(node_id=0, sequence=0, rssi=-1, noise_floor=-1, iq_pairs=iq)
        assert len(data) == 148
        frame = parse_frame(data)
        assert frame is not None


class TestParseInvalidFrame:
    """Invalid frame rejection tests (D-09)."""

    def test_parse_wrong_magic(self):
        """Frame with wrong magic returns None."""
        # Build a frame but corrupt the magic bytes
        iq = [(5, 5)] * 10
        data = build_frame(node_id=1, sequence=1, rssi=-40, noise_floor=-80, iq_pairs=iq)
        # Overwrite magic with DEADBEEF
        bad = struct.pack("<I", 0xDEADBEEF) + data[4:120]
        frame = parse_frame(bad)
        assert frame is None

    def test_parse_length_mismatch(self):
        """Header n_subcarriers says 64 but only 50 I/Q pairs provided → None."""
        iq_50 = [(5, 5)] * 50
        data = build_frame(node_id=1, sequence=1, rssi=-40, noise_floor=-80, iq_pairs=iq_50)
        # The header says 50 subcarriers, but let's test with a frame
        # where data length doesn't match header claim.
        # Build frame with n_sub=10 IQ pairs
        iq_10 = [(3, 3)] * 10
        data = build_frame(node_id=1, sequence=1, rssi=-40, noise_floor=-80, iq_pairs=iq_10)
        # Now corrupt n_subcarriers field to claim 64 instead of 10
        # The n_sub field is at bytes 6-7 (little-endian uint16)
        bad = bytearray(data)
        struct.pack_into("<H", bad, 6, 64)  # Claim 64 subcarriers
        frame = parse_frame(bytes(bad))
        # Frame is 20 + 10*2 = 40 bytes but header claims 64 → 124 bytes expected
        assert frame is None

    def test_parse_truncated_frame(self):
        """Frame shorter than header size returns None."""
        data = b"\x00" * 10
        frame = parse_frame(data)
        assert frame is None

    def test_parse_empty_bytes(self):
        """Empty bytes return None without raising."""
        frame = parse_frame(b"")
        assert frame is None

    def test_parse_none_input(self):
        """None input returns None without raising."""
        frame = parse_frame(None)
        assert frame is None


class TestAmplitudePhase:
    """Amplitude and phase calculation accuracy."""

    def test_amplitude_phase_i3_q4(self):
        """I=3, Q=4 → amplitude=5.0, phase=atan2(4,3)."""
        iq = [(3, 4)]
        data = build_frame(node_id=1, sequence=0, rssi=0, noise_floor=0, iq_pairs=iq)
        frame = parse_frame(data)
        assert frame is not None
        assert frame.n_subcarriers == 1
        assert frame.amplitudes[0] == pytest.approx(5.0)
        assert frame.phases[0] == pytest.approx(math.atan2(4, 3))

    def test_amplitude_phase_negatives(self):
        """I=-4, Q=-3 → amplitude=5.0, phase in Q3."""
        iq = [(-4, -3)]
        data = build_frame(node_id=1, sequence=0, rssi=0, noise_floor=0, iq_pairs=iq)
        frame = parse_frame(data)
        assert frame is not None
        assert frame.amplitudes[0] == pytest.approx(5.0)
        assert frame.phases[0] == pytest.approx(math.atan2(-3, -4))

    def test_amplitude_zero(self):
        """I=0, Q=0 → amplitude=0.0."""
        iq = [(0, 0)]
        data = build_frame(node_id=1, sequence=0, rssi=0, noise_floor=0, iq_pairs=iq)
        frame = parse_frame(data)
        assert frame is not None
        assert frame.amplitudes[0] == 0.0

    def test_multiple_subcarriers_all_correct(self):
        """All 64 subcarriers have correct amplitudes and phases."""
        iq = [(i % 10, (i + 5) % 10) for i in range(64)]
        data = build_frame(node_id=1, sequence=50, rssi=-20, noise_floor=-70, iq_pairs=iq)
        frame = parse_frame(data)
        assert frame is not None
        assert len(frame.amplitudes) == 64
        assert len(frame.phases) == 64
        for i, (expected_i, expected_q) in enumerate(iq):
            expected_amp = math.sqrt(expected_i * expected_i + expected_q * expected_q)
            expected_ph = math.atan2(expected_q, expected_i)
            assert frame.amplitudes[i] == pytest.approx(expected_amp)
            assert frame.phases[i] == pytest.approx(expected_ph)


class TestCorruptedFrame:
    """Corrupted frame handling (never crash — D-09)."""

    def test_parse_corrupted_iq_region(self):
        """Garbage bytes in IQ region should still parse (struct.unpack handles any byte)."""
        iq = [(3, 4)] * 64
        data = build_frame(node_id=2, sequence=10, rssi=-30, noise_floor=-80, iq_pairs=iq)
        # Overwrite IQ region with random bytes
        bad = bytearray(data)
        for i in range(20, len(bad)):
            bad[i] = (i * 7 + 13) & 0xFF
        frame = parse_frame(bytes(bad))
        # Should still produce a valid frame — any byte value is valid int8
        assert frame is not None
        assert frame.n_subcarriers == 64
        assert len(frame.amplitudes) == 64

    def test_parse_1000_random_frames_no_crash(self):
        """Fuzz test: 1000 random-byte frames should never raise."""
        import random
        random.seed(42)
        for _ in range(1000):
            length = random.randint(0, 200)
            data = bytes(random.randint(0, 255) for _ in range(length))
            # Must never raise
            result = parse_frame(data)
            assert result is None or isinstance(result, CSIFrame)


class TestCSIFrameDataclass:
    """CSIFrame dataclass construction tests."""

    def test_instantiate_with_all_fields(self):
        """CSIFrame can be instantiated with all required fields."""
        frame = CSIFrame(
            node_id=1,
            sequence=42,
            timestamp_ms=0,
            rssi=-55,
            noise_floor=-90,
            frequency_mhz=2412,
            n_subcarriers=64,
            amplitudes=[1.0] * 64,
            phases=[0.5] * 64,
        )
        assert frame.node_id == 1
        assert frame.sequence == 42
        assert len(frame.amplitudes) == 64
        assert len(frame.phases) == 64

    def test_amplitudes_length_matches_n_subcarriers(self):
        """Amplitude list must match n_subcarriers."""
        with pytest.raises(ValueError, match="amplitudes length"):
            CSIFrame(
                node_id=1,
                sequence=0,
                n_subcarriers=64,
                amplitudes=[1.0] * 10,
                phases=[0.0] * 64,
            )

    def test_phases_length_matches_n_subcarriers(self):
        """Phase list must match n_subcarriers."""
        with pytest.raises(ValueError, match="phases length"):
            CSIFrame(
                node_id=1,
                sequence=0,
                n_subcarriers=64,
                amplitudes=[1.0] * 64,
                phases=[0.0] * 10,
            )
