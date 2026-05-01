"""Offline inference CLI for the Activity Recognition classifier.

Loads a trained Attention-GRU model and scaler from a checkpoint,
processes .npy files, and outputs predictions as JSON or CSV.

Usage:
    python -m classifier --input data/activities/walking/test.npy --model checkpoints/best_model.pth
    python -m classifier --input data/activities/ --output predictions.json
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from classifier.infer import (
    LABEL_MAP,
    TARGET_SUBCARRIERS,
    _center_crop_1d,
)
from classifier.train import load_checkpoint
from classifier.dataset import load_scaler

logger = logging.getLogger("classifier.cli")


def _predict_file(
    filepath: str,
    model: torch.nn.Module,
    scaler: Any,
    device: torch.device,
    batch_size: int,
    confidence_threshold: float,
) -> list[dict[str, Any]]:
    """Run inference on a single .npy file.

    Expected shape: (samples, time_steps, subcarriers).
    Returns list of prediction dicts.
    """
    data = np.load(filepath)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D array (samples, time_steps, subcarriers), got {data.shape}")

    n_samples = data.shape[0]
    results: list[dict[str, Any]] = []

    for i in range(0, n_samples, batch_size):
        batch = data[i : i + batch_size].astype(np.float64)
        b_size = batch.shape[0]

        # Center-crop/pad subcarriers to 52
        batch_cropped = np.empty((b_size, batch.shape[1], TARGET_SUBCARRIERS), dtype=np.float64)
        for j in range(b_size):
            batch_cropped[j] = _center_crop_1d(batch[j], TARGET_SUBCARRIERS, axis=1)

        # Normalize
        orig_shape = batch_cropped.shape
        flat = batch_cropped.reshape(b_size, -1)
        normalized = scaler.transform(flat)
        batch_norm = normalized.reshape(orig_shape).astype(np.float32)

        tensor = torch.from_numpy(batch_norm).to(device)
        with torch.no_grad():
            logits = model(tensor)

        probs = F.softmax(logits, dim=1).cpu().numpy()
        best_indices = np.argmax(probs, axis=1)
        confidences = probs[np.arange(b_size), best_indices]

        for j in range(b_size):
            idx = int(best_indices[j])
            conf = float(confidences[j])
            label = LABEL_MAP.get(idx, "unknown") if conf >= confidence_threshold else "unknown"
            class_probs = {LABEL_MAP.get(k, str(k)): float(v) for k, v in enumerate(probs[j])}

            results.append({
                "file": str(pathlib.Path(filepath).name),
                "sample_index": i + j,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "label": label,
                "confidence": conf,
                "class_probs": class_probs,
            })

    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="CSI Activity Classifier — offline .npy inference"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to .npy file or directory of .npy files",
    )
    parser.add_argument(
        "--model",
        default="checkpoints/best_model.pth",
        help="Path to model checkpoint (default: checkpoints/best_model.pth)",
    )
    parser.add_argument(
        "--scaler",
        default="checkpoints/scaler.json",
        help="Path to scaler JSON (default: checkpoints/scaler.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (JSON or CSV); prints to stdout if omitted",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Inference batch size (default: 32)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.0,
        help="Minimum confidence to emit a label (default: 0.0)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device to run inference on (default: cpu)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    device = torch.device(args.device)

    # Load model
    model, meta = load_checkpoint(args.model, device=device)
    model.eval()
    logger.info(
        "Loaded model (input=%d, output=%d) from %s",
        getattr(model, "input_dim", 52),
        getattr(model, "output_dim", 4),
        args.model,
    )

    # Load scaler
    scaler = meta.get("scaler")
    if scaler is None:
        scaler = load_scaler(args.scaler)
    logger.info("Scaler loaded — n_features=%d", getattr(scaler, "n_features_in_", 0))

    # Discover input files
    input_path = pathlib.Path(args.input)
    if input_path.is_dir():
        npy_files = sorted(input_path.glob("**/*.npy"))
    else:
        npy_files = [input_path]

    if not npy_files:
        logger.error("No .npy files found in %s", args.input)
        return

    all_results: list[dict[str, Any]] = []
    for fp in npy_files:
        logger.info("Processing %s", fp)
        try:
            results = _predict_file(
                str(fp), model, scaler, device,
                args.batch_size, args.confidence_threshold,
            )
            all_results.extend(results)
        except Exception as exc:
            logger.error("Failed to process %s: %s", fp, exc)
            continue

    if not all_results:
        logger.warning("No predictions generated")
        return

    # Output
    output_text: str
    if args.output and args.output.endswith(".csv"):
        lines = ["label,confidence,sample_index,file"]
        for r in all_results:
            lines.append(f'{r["label"]},{r["confidence"]:.4f},{r["sample_index"]},{r["file"]}')
        output_text = "\n".join(lines)
    else:
        output_text = json.dumps(all_results, indent=2)

    if args.output:
        pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.output).write_text(output_text)
        logger.info("Saved %d predictions to %s", len(all_results), args.output)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
