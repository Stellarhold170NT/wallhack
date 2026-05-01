"""Nexmon pcap parser for HAR Experiment-2 (bcm4366c0, 80MHz).

Ports unpack_float.c to Python for decoding custom float CSI format.
"""

import struct
import pathlib
import logging

import numpy as np

logger = logging.getLogger(__name__)

PCAP_GLOBAL_HEADER_SIZE = 24
PCAP_PACKET_HEADER_SIZE = 16


def _unpack_float_acphy(nbits, autoscale, shft, fmt, nman, nexp, nfft, H):
    """Port of unpack_float_acphy from unpack_float.c.

    Parameters
    ----------
    nbits, autoscale, shft, fmt, nman, nexp, nfft : int
        Format parameters.
    H : np.ndarray
        uint32 array of shape (nfft,).

    Returns
    -------
    Hout : np.ndarray
        int32 array of shape (nfft * 2,) — interleaved I, Q.
    """
    k_tof_unpack_sgn_mask = 1 << 31

    iq_mask = (1 << (nman - 1)) - 1
    e_mask = (1 << nexp) - 1
    e_p = 1 << (nexp - 1)
    sgnr_mask = 1 << (nexp + 2 * nman - 1)
    sgni_mask = sgnr_mask >> nman
    e_zero = -nman
    n_out = nfft << 1
    e_shift = 1
    maxbit = -e_p

    He: list[int] = [0] * nfft
    Hout: list[int] = [0] * n_out

    for i in range(nfft):
        vi = int((H[i] >> (nexp + nman)) & iq_mask)
        vq = int((H[i] >> nexp) & iq_mask)
        e = int(H[i] & e_mask)
        if e >= e_p:
            e -= e_p << 1
        He[i] = e
        x = vi | vq
        if autoscale and x:
            m = 0xFFFF0000
            b = 0xFFFF
            s = 16
            while s > 0:
                if x & m:
                    e += s
                    x >>= s
                s >>= 1
                m = (m >> s) & b
                b >>= s
            if e > maxbit:
                maxbit = e
        if H[i] & sgnr_mask:
            vi |= k_tof_unpack_sgn_mask
        if H[i] & sgni_mask:
            vq |= k_tof_unpack_sgn_mask
        Hout[i << 1] = vi
        Hout[(i << 1) + 1] = vq

    shft_val = nbits - maxbit
    for i in range(n_out):
        e = He[i >> e_shift] + shft_val
        vi = Hout[i]
        sgn = 1
        if vi & k_tof_unpack_sgn_mask:
            sgn = -1
            vi &= ~k_tof_unpack_sgn_mask
        if e < e_zero:
            vi = 0
        elif e < 0:
            vi = vi >> (-e)
        else:
            vi = vi << e
        Hout[i] = sgn * vi

    arr = np.array(Hout, dtype=np.int64)
    arr = np.bitwise_and(arr, 0xFFFFFFFF).astype(np.uint32).view(np.int32)
    return arr


def unpack_float(format_flag, nfft, H):
    """Python port of MATLAB mex unpack_float.

    Parameters
    ----------
    format_flag : int
        0 for bcm4358, 1 for bcm4366c0.
    nfft : int
        Number of FFT bins / subcarriers.
    H : np.ndarray
        uint32 array.

    Returns
    -------
    np.ndarray
        int32 array of length nfft*2 (interleaved I, Q).
    """
    if format_flag == 0:
        return _unpack_float_acphy(10, 1, 0, 1, 9, 5, nfft, H)
    elif format_flag == 1:
        return _unpack_float_acphy(10, 1, 0, 1, 12, 6, nfft, H)
    else:
        raise ValueError("format_flag must be 0 or 1")


def read_pcap_packets(filepath: str):
    """Yield raw packet payloads from a pcap file.

    Skips the pcap global header and yields each packet's raw bytes.
    """
    path = pathlib.Path(filepath)
    with open(path, "rb") as f:
        global_header = f.read(PCAP_GLOBAL_HEADER_SIZE)
        if len(global_header) != PCAP_GLOBAL_HEADER_SIZE:
            raise ValueError(f"Invalid pcap file: {filepath}")

        magic = struct.unpack("<I", global_header[:4])[0]
        if magic == 0xA1B2C3D4:
            endian = "<"
        elif magic == 0xD4C3B2A1:
            endian = ">"
        else:
            raise ValueError(f"Unknown pcap magic: 0x{magic:08X}")

        while True:
            pkt_header = f.read(PCAP_PACKET_HEADER_SIZE)
            if len(pkt_header) != PCAP_PACKET_HEADER_SIZE:
                break

            ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
                f"{endian}IIII", pkt_header
            )
            pkt_data = f.read(incl_len)
            if len(pkt_data) != incl_len:
                logger.warning("Truncated packet in %s", filepath)
                break

            yield pkt_data


def parse_experiment2_pcap(filepath: str, nfft: int = 256):
    """Parse Experiment-2 pcap file and return amplitude matrix.

    Parameters
    ----------
    filepath : str
        Path to .pcap file.
    nfft : int
        Number of subcarriers (default 256 for 80MHz).

    Returns
    -------
    np.ndarray | None
        Amplitude matrix of shape (n_packets, nfft), or None if invalid.
    """
    hoffset = 15  # MATLAB 1-based HOFFSET=16 -> Python 0-based=15
    expected_uint32s = 271
    expected_bytes = expected_uint32s * 4
    format_flag = 1  # bcm4366c0

    amplitudes = []

    for pkt_data in read_pcap_packets(filepath):
        if len(pkt_data) != expected_bytes:
            continue

        payload = np.frombuffer(pkt_data, dtype=np.uint32)
        if payload.shape[0] != expected_uint32s:
            continue

        H = payload[hoffset : hoffset + nfft]
        Hout = unpack_float(format_flag, nfft, H)
        Hout = Hout.reshape(nfft, 2)
        i_vals = Hout[:, 0].astype(np.float64)
        q_vals = Hout[:, 1].astype(np.float64)
        amp = np.sqrt(i_vals * i_vals + q_vals * q_vals).astype(np.float32)
        amplitudes.append(amp)

    if not amplitudes:
        return None

    return np.stack(amplitudes, axis=0)


def load_experiment2_amplitudes(root_dir: str, activity: str, max_files: int | None = None):
    """Load all pcap files for a given activity from Experiment-2.

    Returns list of amplitude matrices, one per pcap file.
    Each matrix has shape (n_packets, 256).
    """
    root = pathlib.Path(root_dir)
    pattern = f"{activity}*.pcap"
    files = sorted(root.glob(pattern))
    if max_files:
        files = files[:max_files]

    results = []
    for f in files:
        amp = parse_experiment2_pcap(str(f))
        if amp is not None and amp.shape[0] > 0:
            results.append(amp)

    return results
