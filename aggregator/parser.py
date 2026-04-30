"""
Binary CSI frame parser for ADR-018 format.

Validates magic header and frame length before extracting metadata
and per-subcarrier I/Q data into a CSIFrame dataclass.

Ref: D-09 (strict validation, graceful degradation)
"""

import struct
import math
import logging
from .frame import CSIFrame

logger = logging.getLogger(__name__)

CSI_MAGIC = 0xC5110001
CSI_HEADER_SIZE = 20


def parse_frame(data: bytes) -> CSIFrame | None:
    """Parse a raw binary CSI frame into a CSIFrame dataclass.

    Returns None and logs a warning if the frame is invalid
    (wrong magic, wrong length, truncated, or corrupt).

    Args:
        data: Raw bytes from UDP datagram.

    Returns:
        CSIFrame on success, None on failure.
    """
    if data is None or len(data) < CSI_HEADER_SIZE:
        logger.warning(
            "Frame too short (%d bytes, min %d) — dropping",
            len(data) if data else 0,
            CSI_HEADER_SIZE,
        )
        return None

    try:
        magic = struct.unpack("<I", data[0:4])[0]
        if magic != CSI_MAGIC:
            logger.warning(
                "Invalid magic 0x%08X (expected 0x%08X) — dropping frame",
                magic,
                CSI_MAGIC,
            )
            return None

        node_id = data[4]
        # antennas = data[5] — not stored in CSIFrame currently
        n_subcarriers = struct.unpack("<H", data[6:8])[0]
        frequency_mhz = struct.unpack("<I", data[8:12])[0]
        sequence = struct.unpack("<I", data[12:16])[0]
        rssi = struct.unpack("b", bytes([data[16]]))[0]
        noise_floor = struct.unpack("b", bytes([data[17]]))[0]

        expected_len = CSI_HEADER_SIZE + n_subcarriers * 2
        if len(data) != expected_len:
            logger.warning(
                "Frame length mismatch: got %d bytes, expected %d "
                "(header=%d + %d subcarriers × 2) — dropping frame",
                len(data),
                expected_len,
                CSI_HEADER_SIZE,
                n_subcarriers,
            )
            return None

        amplitudes: list[float] = []
        phases: list[float] = []

        for i in range(n_subcarriers):
            offset = CSI_HEADER_SIZE + i * 2
            # I and Q are signed 8-bit integers
            i_val = struct.unpack("b", bytes([data[offset]]))[0]
            q_val = struct.unpack("b", bytes([data[offset + 1]]))[0]
            amp = math.sqrt(i_val * i_val + q_val * q_val)
            phs = math.atan2(q_val, i_val)
            amplitudes.append(amp)
            phases.append(phs)

        return CSIFrame(
            node_id=node_id,
            sequence=sequence,
            timestamp_ms=0,
            rssi=rssi,
            noise_floor=noise_floor,
            frequency_mhz=frequency_mhz,
            n_subcarriers=n_subcarriers,
            amplitudes=amplitudes,
            phases=phases,
        )

    except (struct.error, IndexError, ValueError) as exc:
        logger.warning("Failed to parse frame: %s — dropping", exc)
        return None
