"""
CSI Frame dataclass per ADR-018 binary format.

Frame format (little-endian, 20-byte header + I/Q payload):
  Offset | Size | Field
  -------|------|------
       0 |    4 | magic (0xC5110001)
       4 |    1 | node_id
       5 |    1 | antennas
       6 |    2 | n_subcarriers
       8 |    4 | frequency_mhz
      12 |    4 | sequence
      16 |    1 | rssi (int8)
      17 |    1 | noise_floor (int8)
      18 |    2 | reserved
      20 |  N*2 | I/Q interleaved (int8 I, int8 Q per subcarrier)

Ref: ADR-018, firmware/esp32-csi-node/main/csi_collector.c
"""

from dataclasses import dataclass, field


@dataclass
class CSIFrame:
    """A single parsed CSI frame received from an ESP32-S3 node.

    Contains header metadata and per-subcarrier amplitude/phase arrays
    extracted from the raw I/Q bytes.
    """

    node_id: int
    sequence: int
    timestamp_ms: int = 0
    rssi: int = 0
    noise_floor: int = 0
    frequency_mhz: int = 0
    n_subcarriers: int = 0
    amplitudes: list[float] = field(default_factory=list)
    phases: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.n_subcarriers < 0:
            raise ValueError("n_subcarriers must be non-negative")
        expected = self.n_subcarriers
        if len(self.amplitudes) != expected:
            raise ValueError(
                f"amplitudes length ({len(self.amplitudes)}) "
                f"!= n_subcarriers ({expected})"
            )
        if len(self.phases) != expected:
            raise ValueError(
                f"phases length ({len(self.phases)}) "
                f"!= n_subcarriers ({expected})"
            )
