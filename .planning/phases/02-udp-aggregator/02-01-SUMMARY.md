# Wave 1 Summary: Frame Dataclass and Binary Parser

**Plan:** 02-01
**Executed:** 2026-04-30
**Status:** Complete — 17/17 tests pass

## Files Delivered

| File | Purpose | Lines |
|------|---------|-------|
| `aggregator/__init__.py` | Package root marker | 0 |
| `aggregator/frame.py` | `CSIFrame` dataclass with 9 typed fields | 37 |
| `aggregator/parser.py` | `parse_frame()` — ADR-018 binary parser | 58 |
| `aggregator/test_parser.py` | Unit tests (valid, invalid, fuzz, accuracy) | 142 |

## Key Decisions Implemented

- **D-09:** Strict validation with graceful degradation
  - Validates magic `0xC5110001` and frame length (`20 + n_subcarriers * 2`)
  - Invalid frames return `None` + `WARNING` log — never crash
  - Fuzz test with 1000 random-byte frames verifies no exceptions

## Verification

- `python -m pytest aggregator/test_parser.py -x` → **17 passed**
- Tests cover: valid frame parsing, wrong magic, length mismatch, truncation, amplitude/phase accuracy (I=3,Q=4 → amp=5.0), corrupted IQ data, CSIFrame instantiation

## Notes

- Frame format verified against `firmware/esp32-csi-node/main/csi_collector.c`
- Total frame size: 124 bytes (20 header + 104 I/Q for 52 subcarriers)
- Little-endian unpacking with `struct.unpack`
- Amplitude: `sqrt(I^2 + Q^2)`, Phase: `atan2(Q, I)` in radians
