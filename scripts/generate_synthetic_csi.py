#!/usr/bin/env python3
"""Synthetic CSI data generator for offline testing of the presence-detection pipeline.

Replays realistic CSI amplitude patterns over UDP so you can test the
aggregator / detector without physical ESP32-S3 nodes.

Usage (live UDP injection):
    python scripts/generate_synthetic_csi.py --target-ip 127.0.0.1 --target-port 5005 \\
        --scenario empty_then_occupied --duration 120 --fps 10

Usage (save to .npy for replay):
    python scripts/generate_synthetic_csi.py --output data/synthetic/empty_room.npy \\
        --scenario empty_stable --duration 60 --fps 10

Scenarios
---------
empty_stable          : constant low-amplitude noise (empty room)
empty_then_occupied   : 30 s empty → 30 s occupied → 30 s empty
brief_visit           : 20 s empty → 10 s occupied → 20 s empty
noisy_baseline        : drifting baseline to test robustness
slow_drift_occupied   : slowly increasing distortion (simulates door opening)
"""

from __future__ import annotations

import argparse
import math
import socket
import struct
import time
from pathlib import Path
from typing import Callable

import numpy as np

CSI_MAGIC = 0xC5110001
CSI_HEADER_SIZE = 20

# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------

def _empty_amplitude(t: float, subcarrier_idx: int, n_sc: int) -> float:
    """Stable empty-room amplitude with tiny per-subcarrier variation."""
    base = 100.0 + 20.0 * math.sin(2 * math.pi * subcarrier_idx / n_sc)
    noise = np.random.normal(0, 3.0)
    return max(10.0, base + noise)


def _occupied_amplitude(t: float, subcarrier_idx: int, n_sc: int) -> float:
    """Occupied-room amplitude: breathing + larger random motion."""
    base = 100.0 + 20.0 * math.sin(2 * math.pi * subcarrier_idx / n_sc)
    # Breathing band ~0.25 Hz
    breathing = 15.0 * math.sin(2 * math.pi * 0.25 * t + subcarrier_idx)
    # Random body motion
    motion = np.random.normal(0, 12.0)
    return max(10.0, base + breathing + motion)


def _noisy_drift_amplitude(t: float, subcarrier_idx: int, n_sc: int) -> float:
    """Slowly drifting baseline to test adaptive baseline robustness."""
    base = 100.0 + 20.0 * math.sin(2 * math.pi * subcarrier_idx / n_sc)
    drift = 0.5 * t  # amplitude slowly creeps up
    noise = np.random.normal(0, 5.0)
    return max(10.0, base + drift + noise)


def _slow_distortion_amplitude(t: float, subcarrier_idx: int, n_sc: int) -> float:
    """Simulate a door slowly opening / environmental change."""
    base = 100.0 + 20.0 * math.sin(2 * math.pi * subcarrier_idx / n_sc)
    # Slow ramp then hold
    ramp = min(t, 30.0) * 1.5
    noise = np.random.normal(0, 4.0)
    return max(10.0, base + ramp + noise)


ScenarioFn = Callable[[float, int, int], float]

SCENARIOS: dict[str, ScenarioFn] = {
    "empty_stable": _empty_amplitude,
    "occupied": _occupied_amplitude,
    "noisy_baseline": _noisy_drift_amplitude,
    "slow_drift_occupied": _slow_distortion_amplitude,
}


def build_scenario_fn(name: str) -> ScenarioFn:
    """Return a time-varying amplitude function for the named scenario.

    Composite scenarios (e.g. ``empty_then_occupied``) are built by
    stitching together simpler segment functions.
    """
    if name in SCENARIOS:
        return SCENARIOS[name]

    if name == "empty_then_occupied":
        def _empty_then_occupied(t: float, sc: int, n_sc: int) -> float:
            if t < 30.0:
                return _empty_amplitude(t, sc, n_sc)
            if t < 60.0:
                return _occupied_amplitude(t, sc, n_sc)
            return _empty_amplitude(t, sc, n_sc)
        return _empty_then_occupied

    if name == "brief_visit":
        def _brief_visit(t: float, sc: int, n_sc: int) -> float:
            if t < 20.0:
                return _empty_amplitude(t, sc, n_sc)
            if t < 30.0:
                return _occupied_amplitude(t, sc, n_sc)
            return _empty_amplitude(t, sc, n_sc)
        return _brief_visit

    if name == "multiple_visits":
        def _multiple_visits(t: float, sc: int, n_sc: int) -> float:
            cycle = t % 20.0
            occupied = (10.0 <= cycle < 15.0)
            return _occupied_amplitude(t, sc, n_sc) if occupied else _empty_amplitude(t, sc, n_sc)
        return _multiple_visits

    raise ValueError(f"Unknown scenario '{name}'. Choose from: {list(SCENARIOS.keys()) + ['empty_then_occupied', 'brief_visit', 'multiple_visits']}")


# ---------------------------------------------------------------------------
# Frame construction
# ---------------------------------------------------------------------------

def make_csi_frame(
    node_id: int,
    sequence: int,
    n_subcarriers: int = 128,
    amplitude_fn: ScenarioFn | None = None,
    t: float = 0.0,
) -> bytes:
    """Build a single ADR-018 binary CSI frame.

    Parameters
    ----------
    node_id:
        Emitter node identifier.
    sequence:
        Monotonically increasing frame counter.
    n_subcarriers:
        Number of subcarriers (default 128).
    amplitude_fn:
        Callable ``(t, sc_idx, n_sc) -> amplitude``.
    t:
        Wall-clock time used to evaluate the amplitude function.

    Returns
    -------
    Raw bytes ready to be sent over UDP.
    """
    amplitude_fn = amplitude_fn or _empty_amplitude

    header = struct.pack(
        "<I B B H I I b b H",
        CSI_MAGIC,
        node_id,
        1,                       # antennas
        n_subcarriers,
        2412,                    # frequency_mhz (2.4 GHz ch1)
        sequence & 0xFFFFFFFF,   # wrap-around safety
        -45,                     # rssi (typical indoor)
        -95,                     # noise_floor
        0,                       # reserved
    )

    iq_bytes = bytearray()
    for sc in range(n_subcarriers):
        amp = amplitude_fn(t, sc, n_subcarriers)
        # Random phase so amplitude is the only controlled variable
        theta = np.random.uniform(0, 2 * math.pi)
        # Scale so that sqrt(I^2 + Q^2) ≈ amp
        i_val = int(amp * math.cos(theta))
        q_val = int(amp * math.sin(theta))
        # Clamp to int8 range
        i_val = max(-128, min(127, i_val))
        q_val = max(-128, min(127, q_val))
        iq_bytes.extend(struct.pack("bb", i_val, q_val))

    return header + bytes(iq_bytes)


# ---------------------------------------------------------------------------
# Output sinks
# ---------------------------------------------------------------------------

def _udp_sender(target_ip: str, target_port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (target_ip, target_port)

    def send(frame: bytes):
        sock.sendto(frame, dest)

    return send


def _npy_writer(path: Path, n_subcarriers: int):
    """Accumulate frames as a list of amplitude vectors and save on close."""
    frames: list[np.ndarray] = []

    def append(frame: bytes):
        # Parse amplitudes back from the frame we just built
        n_sc = struct.unpack("<H", frame[6:8])[0]
        amps = np.zeros(n_sc, dtype=np.float64)
        for i in range(n_sc):
            off = CSI_HEADER_SIZE + i * 2
            i_val = struct.unpack("b", bytes([frame[off]]))[0]
            q_val = struct.unpack("b", bytes([frame[off + 1]]))[0]
            amps[i] = math.sqrt(i_val * i_val + q_val * q_val)
        frames.append(amps)

    def close():
        arr = np.stack(frames, axis=0)  # shape (n_frames, n_subcarriers)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, arr)
        print(f"Saved {arr.shape[0]} frames x {arr.shape[1]} subcarriers -> {path}")

    return append, close


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    np.random.seed(args.seed)

    amplitude_fn = build_scenario_fn(args.scenario)
    n_frames = int(args.duration * args.fps)
    interval = 1.0 / args.fps

    # Select output sink
    if args.output:
        sink_append, sink_close = _npy_writer(Path(args.output), args.subcarriers)
        sink = sink_append
    else:
        send = _udp_sender(args.target_ip, args.target_port)
        sink = send

    print(
        f"Emitting {n_frames} frames ({args.duration}s @ {args.fps} fps, "
        f"sc={args.subcarriers}) scenario='{args.scenario}' node={args.node_id}"
    )
    if not args.output:
        print(f"-> UDP {args.target_ip}:{args.target_port}")
    else:
        print(f"-> {args.output}")

    t0 = time.monotonic()
    for seq in range(n_frames):
        t = seq * interval
        frame = make_csi_frame(
            node_id=args.node_id,
            sequence=seq,
            n_subcarriers=args.subcarriers,
            amplitude_fn=amplitude_fn,
            t=t,
        )
        sink(frame)

        # Real-time pacing
        if not args.output:
            expected = t0 + (seq + 1) * interval
            now = time.monotonic()
            sleep_time = expected - now
            if sleep_time > 0:
                time.sleep(sleep_time)

    if args.output:
        sink_close()
    else:
        print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synthetic CSI generator for presence-detection testing"
    )
    parser.add_argument(
        "--scenario",
        default="empty_then_occupied",
        choices=[
            "empty_stable",
            "occupied",
            "empty_then_occupied",
            "brief_visit",
            "multiple_visits",
            "noisy_baseline",
            "slow_drift_occupied",
        ],
        help="Amplitude pattern to simulate",
    )
    parser.add_argument("--duration", type=float, default=120, help="Total seconds")
    parser.add_argument("--fps", type=float, default=10, help="Frames per second")
    parser.add_argument("--subcarriers", type=int, default=128, help="Subcarrier count")
    parser.add_argument("--node-id", type=int, default=1, help="Node identifier")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--target-ip", default="127.0.0.1", help="Target IP for UDP mode"
    )
    parser.add_argument(
        "--target-port", type=int, default=5005, help="Target UDP port"
    )
    parser.add_argument(
        "--output",
        default="",
        help="If set, write amplitude matrix .npy instead of sending UDP",
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
