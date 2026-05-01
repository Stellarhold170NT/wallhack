"""Offline CLI for processing .npy CSI files.

Reads raw amplitude arrays from disk, runs the full signal processing
pipeline, and writes feature vectors to output files.

Usage:
    python -m processor --input data/raw/session.npy --output features.npy
"""

import argparse
import logging
import numpy as np
from processor.window import SlidingWindow
from processor.features import extract_features
from processor.hampel import hampel_filter

logger = logging.getLogger("processor.cli")


def process_npy(
    input_path: str,
    output_path: str,
    window_size: int = 200,
    step_size: int = 100,
    sample_rate: float = 50.0,
) -> int:
    """Process a .npy file and save feature vectors.

    Returns:
        Number of windows processed.
    """
    data = np.load(input_path)
    if data.ndim != 2:
        raise ValueError(f"Expected 2D array (frames, subcarriers), got {data.shape}")

    n_frames, n_subcarriers = data.shape
    sw = SlidingWindow(
        n_subcarriers=n_subcarriers,
        window_size=window_size,
        step_size=step_size,
    )

    feature_dicts = []
    for i in range(n_frames):
        # Simulate CSIFrame push
        from aggregator.frame import CSIFrame
        frame = CSIFrame(
            node_id=0,
            sequence=i,
            n_subcarriers=n_subcarriers,
            amplitudes=data[i, :].tolist(),
            phases=[0.0] * n_subcarriers,
        )
        window = sw.push(frame)
        if window is not None:
            # Apply Hampel per subcarrier
            cleaned = window.copy()
            for col in range(n_subcarriers):
                cleaned[:, col] = hampel_filter(cleaned[:, col])
            features = extract_features(
                cleaned, sample_rate=sample_rate
            )
            feature_dicts.append(features)

    if feature_dicts:
        np.save(output_path, feature_dicts, allow_pickle=True)
        logger.info(
            "Processed %d frames → %d feature vectors → %s",
            n_frames,
            len(feature_dicts),
            output_path,
        )
    else:
        logger.warning("No feature vectors generated — not enough frames")

    return len(feature_dicts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CSI Signal Processor — offline .npy processing"
    )
    parser.add_argument(
        "--input", required=True, help="Input .npy file (frames, subcarriers)"
    )
    parser.add_argument(
        "--output", required=True, help="Output .npy file for feature dicts"
    )
    parser.add_argument(
        "--window-size", type=int, default=200, help="Window size in frames"
    )
    parser.add_argument(
        "--step-size", type=int, default=100, help="Step size in frames"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    count = process_npy(
        input_path=args.input,
        output_path=args.output,
        window_size=args.window_size,
        step_size=args.step_size,
    )
    print(f"Processed {count} feature vectors → {args.output}")


if __name__ == "__main__":
    main()
