"""Training pipeline with early stopping, validation, and cross-validation.

Supports HAR pre-training and ESP32-S3 fine-tuning per the hybrid
data strategy (D-33), with MixUp batch augmentation inside the
training loop (D-43).

Ref: D-33, D-41, D-43
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import pathlib
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, random_split, Subset, TensorDataset

from .augment import mixup_augment
from .model import AttentionGRU
from .dataset import (
    HarDataset,
    Esp32Dataset,
    fit_scaler,
    load_scaler,
    save_scaler,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "epochs": 100,
    "lr": 1e-3,
    "patience": 10,
    "scheduler_type": "cosine",
    "batch_size": 32,
    "augment": True,
    "mixup_prob": 0.3,
    "mixup_alpha": 1.0,
    "val_split": 0.2,
    "n_splits": 5,
    "num_classes": 6,
    "input_dim": 52,
    "timesteps": 50,
    "hidden_dim": 128,
    "attention_dim": 32,
}


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    device: torch.device,
    config: dict[str, Any] | None = None,
) -> tuple[nn.Module, dict[str, Any]]:
    """Train with early stopping on validation loss.

    Saves best model weights based on validation accuracy.
    Returns (best_model, history_dict).

    history keys: train_loss, train_acc, val_loss, val_acc (lists), best_val_acc
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"])

    if cfg["scheduler_type"] == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=cfg["epochs"]
        )
    else:
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)

    best_acc = 0.0
    best_model_wts = copy.deepcopy(model.state_dict())
    best_loss = float("inf")
    patience_counter = 0

    history: dict[str, list[float]] = {
        "train_loss": [],
        "train_acc": [],
        "val_loss": [],
        "val_acc": [],
    }

    for epoch in range(cfg["epochs"]):
        model.train()
        running_loss = 0.0
        running_corrects = 0
        total = 0

        for inputs, labels in train_loader:
            inputs = inputs.to(device).float()
            labels = labels.to(device).long()

            use_mixup = cfg["augment"] and np.random.random() < cfg["mixup_prob"]

            if use_mixup:
                X_np = inputs.cpu().numpy()
                y_np = labels.cpu().numpy()
                X_mix, y_mix = mixup_augment(
                    X_np, y_np, alpha=cfg["mixup_alpha"], prob=1.0,
                    num_classes=cfg.get("num_classes", 6)
                )
                inputs = torch.from_numpy(X_mix.astype(np.float32)).to(device)
                targets = torch.from_numpy(y_mix.astype(np.float32)).to(device)
            else:
                targets = labels

            optimizer.zero_grad()
            outputs = model(inputs)

            if use_mixup:
                loss = -(targets * torch.log_softmax(outputs, dim=1)).sum(dim=1).mean()
            else:
                loss = criterion(outputs, targets)

            loss.backward()
            optimizer.step()

            running_loss += loss.item() * inputs.size(0)
            if use_mixup:
                _, preds = torch.max(outputs, 1)
                _, true_labels = torch.max(targets, 1)
                running_corrects += int((preds == true_labels).sum())
            else:
                _, preds = torch.max(outputs, 1)
                running_corrects += int((preds == targets).sum())
            total += inputs.size(0)

        train_loss = running_loss / total
        train_acc = 100.0 * running_corrects / total
        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)

        scheduler.step()

        model.eval()
        val_loss = 0.0
        val_corrects = 0
        val_total = 0

        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs = inputs.to(device).float()
                labels = labels.to(device).long()

                outputs = model(inputs)
                loss = criterion(outputs, labels)

                val_loss += loss.item() * inputs.size(0)
                _, preds = torch.max(outputs, 1)
                val_corrects += int((preds == labels).sum())
                val_total += inputs.size(0)

        val_loss_avg = val_loss / val_total
        val_acc = 100.0 * val_corrects / val_total
        history["val_loss"].append(val_loss_avg)
        history["val_acc"].append(val_acc)

        logger.info(
            "Epoch %3d  |  train_loss %.4f  train_acc %.2f%%  |  "
            "val_loss %.4f  val_acc %.2f%%",
            epoch + 1, train_loss, train_acc, val_loss_avg, val_acc,
        )

        improved = False
        if val_acc > best_acc:
            best_acc = val_acc
            best_model_wts = copy.deepcopy(model.state_dict())
            improved = True
        if val_loss_avg < best_loss:
            best_loss = val_loss_avg
            improved = True

        if improved:
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= cfg["patience"]:
            logger.info("Early stopping triggered at epoch %d", epoch + 1)
            break

    model.load_state_dict(best_model_wts)
    history["best_val_acc"] = best_acc

    logger.info("Training complete — best val acc: %.2f%%", best_acc)
    return model, history


def pretrain_har(
    har_root: str,
    device: torch.device,
    config: dict[str, Any] | None = None,
) -> tuple[nn.Module, dict[str, Any]]:
    """Pre-train on all 6 HAR classes (D-41).

    Returns (model_with_6class_head, history).
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    train_ds = HarDataset(har_root, split="train")
    scaler = fit_scaler(train_ds)
    train_ds.scaler = scaler

    val_ds = HarDataset(har_root, split="test")
    val_ds.scaler = scaler

    train_loader = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=cfg["batch_size"], shuffle=False)

    model = AttentionGRU(
        input_dim=cfg["input_dim"],
        hidden_dim=cfg["hidden_dim"],
        attention_dim=cfg["attention_dim"],
        output_dim=6,
    ).to(device)

    model, history = train_model(
        model, train_loader, val_loader, device, {**cfg, "num_classes": 6}
    )

    return model, history


def finetune_esp32(
    model: nn.Module,
    esp32_root: str,
    device: torch.device,
    config: dict[str, Any] | None = None,
) -> tuple[nn.Module, dict[str, Any]]:
    """Fine-tune on ESP32 data with 6-class output (D-35).

    Replaces the final FC layer with a 6-class head, applies
    augmentation, and trains.

    Returns (fine_tuned_model, history).
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    ds = Esp32Dataset(esp32_root)
    scaler = fit_scaler(ds)

    val_size = int(len(ds) * cfg["val_split"])
    train_size = len(ds) - val_size
    train_subset, val_subset = random_split(
        ds, [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )

    if cfg["augment"]:
        aug_ds = _augment_subset(ds, train_subset.indices)
    else:
        aug_ds = Subset(ds, train_subset.indices)

    aug_ds.scaler = scaler
    val_subset.dataset.scaler = scaler

    train_loader = DataLoader(aug_ds, batch_size=cfg["batch_size"], shuffle=True)
    val_loader = DataLoader(val_subset, batch_size=cfg["batch_size"], shuffle=False)

    hidden_dim = model.hidden_dim
    old_fc = model.fc
    model.fc = nn.Linear(hidden_dim, cfg["num_classes"]).to(device)
    model.output_dim = cfg["num_classes"]

    if old_fc.out_features >= cfg["num_classes"]:
        with torch.no_grad():
            model.fc.weight[:] = old_fc.weight[: cfg["num_classes"]]
            model.fc.bias[:] = old_fc.bias[: cfg["num_classes"]]
    else:
        nn.init.xavier_uniform_(model.fc.weight)
        nn.init.zeros_(model.fc.bias)

    model, history = train_model(model, train_loader, val_loader, device, cfg)

    return model, history


def _augment_subset(ds: Dataset, indices: list[int]) -> TensorDataset:
    """Return augmented TensorDataset for the given indices."""
    from .augment import shift_augment, noise_augment

    samples_x, samples_y = [], []
    for i in indices:
        x, y = ds[i]
        samples_x.append(x.numpy() if isinstance(x, torch.Tensor) else np.asarray(x))
        samples_y.append(int(y))

    X = np.stack(samples_x)
    y_vec = np.array(samples_y)

    X, y_vec = shift_augment(X, y_vec)
    X, y_vec = noise_augment(X, y_vec)

    return TensorDataset(
        torch.from_numpy(X.astype(np.float32)),
        torch.from_numpy(y_vec).long(),
    )


def cross_validate(
    dataset: Dataset,
    device: torch.device,
    config: dict[str, Any] | None = None,
) -> list[float]:
    """K-fold cross-validation (default 5-fold, per D-43).

    Returns list of fold accuracies.
    """
    from sklearn.model_selection import KFold

    cfg = {**DEFAULT_CONFIG, **(config or {})}
    n_splits = cfg.get("n_splits", 5)

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    fold_accuracies: list[float] = []

    for fold, (train_idx, val_idx) in enumerate(kf.split(range(len(dataset)))):
        logger.info("=== Fold %d/%d ===", fold + 1, n_splits)

        train_sub = Subset(dataset, train_idx)
        val_sub = Subset(dataset, val_idx)

        train_loader = DataLoader(
            train_sub, batch_size=cfg["batch_size"], shuffle=True
        )
        val_loader = DataLoader(
            val_sub, batch_size=cfg["batch_size"], shuffle=False
        )

        model = AttentionGRU(
            input_dim=cfg["input_dim"],
            hidden_dim=cfg["hidden_dim"],
            attention_dim=cfg["attention_dim"],
            output_dim=cfg["num_classes"],
        ).to(device)

        _, history = train_model(
            model, train_loader, val_loader, device, cfg
        )

        best_acc = history["best_val_acc"]
        fold_accuracies.append(best_acc)
        logger.info("Fold %d best acc: %.2f%%", fold + 1, best_acc)

    avg = float(np.mean(fold_accuracies))
    logger.info(
        "CV complete — %.2f%% ± %.2f%% across %d folds",
        avg, float(np.std(fold_accuracies)), n_splits,
    )
    return fold_accuracies


def save_checkpoint(
    model: nn.Module,
    path: str,
    scaler=None,
    config: dict[str, Any] | None = None,
) -> None:
    """Save model state dict, scaler, and config."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    checkpoint: dict[str, Any] = {
        "model_state_dict": model.state_dict(),
        "input_dim": getattr(model, "input_dim", 52),
        "hidden_dim": getattr(model, "hidden_dim", 128),
        "attention_dim": getattr(model, "attention_dim", 32),
        "output_dim": getattr(model, "output_dim", 6),
    }
    torch.save(checkpoint, p)

    if scaler is not None:
        scaler_path = p.with_suffix(".scaler.json")
        save_scaler(scaler, str(scaler_path))

    if config is not None:
        cfg_path = p.with_suffix(".config.json")
        with open(cfg_path, "w") as f:
            json.dump(config, f, indent=2)


def load_checkpoint(
    path: str,
    device: torch.device | str = "cpu",
) -> tuple[nn.Module, dict[str, Any]]:
    """Load model, scaler, and config from checkpoint."""
    p = pathlib.Path(path)
    checkpoint = torch.load(p, map_location=device, weights_only=False)

    model = AttentionGRU(
        input_dim=checkpoint.get("input_dim", 52),
        hidden_dim=checkpoint.get("hidden_dim", 128),
        attention_dim=checkpoint.get("attention_dim", 32),
        output_dim=checkpoint.get("output_dim", 4),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)

    scaler = None
    scaler_path = p.with_suffix(".scaler.json")
    if scaler_path.exists():
        scaler = load_scaler(str(scaler_path))

    config = None
    cfg_path = p.with_suffix(".config.json")
    if cfg_path.exists():
        with open(cfg_path) as f:
            config = json.load(f)

    return model, {
        "scaler": scaler,
        "config": config,
        "input_dim": checkpoint.get("input_dim", 52),
        "output_dim": checkpoint.get("output_dim", 4),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Train Attention-GRU activity classifier"
    )
    parser.add_argument(
        "--data-dir",
        help="ESP32-S3 dataset directory (data/activities/)",
    )
    parser.add_argument(
        "--har-dir",
        help="HAR dataset directory for pre-training",
    )
    parser.add_argument(
        "--output-dir",
        default="models/activity",
        help="Directory to save models (default: models/activity)",
    )
    parser.add_argument(
        "--pretrained",
        type=str,
        help="Path to a pre-trained model checkpoint (e.g., pretrain_har.pth)",
    )
    parser.add_argument(
        "--fine-tune",
        action="store_true",
        help="Enable fine-tuning mode (loads --pretrained and trains on --data-dir)",
    )
    parser.add_argument(
        "--epochs", type=int, default=100, help="Max training epochs (default: 100)"
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=1e-3,
        help="Learning rate (default: 1e-3)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size (default: 32)",
    )
    parser.add_argument(
        "--augment",
        action="store_true",
        default=True,
        help="Enable data augmentation (shift + noise, default: True)",
    )
    parser.add_argument(
        "--no-augment",
        action="store_false",
        dest="augment",
        help="Disable data augmentation",
    )
    parser.add_argument(
        "--cross-validate",
        action="store_true",
        help="Run 5-fold cross-validation and report average accuracy",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device to train on (default: cpu)",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    device = torch.device(args.device)
    cfg = {
        "epochs": args.epochs,
        "lr": args.lr,
        "batch_size": args.batch_size,
        "augment": args.augment,
    }

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.cross_validate and args.data_dir:
        ds = Esp32Dataset(args.data_dir)
        scaler = fit_scaler(ds)
        ds.scaler = scaler
        accs = cross_validate(ds, device, cfg)
        avg = float(np.mean(accs))
        print(f"\n5-fold CV: {avg:.2f}% avg accuracy")
        for i, a in enumerate(accs):
            print(f"  Fold {i+1}: {a:.2f}%")
        return

    model = None
    history: dict[str, Any] = {}

    if args.har_dir:
        logger.info("=== HAR pre-training ===")
        model, hist = pretrain_har(args.har_dir, device, cfg)
        history["pretrain"] = hist
        logger.info(
            "HAR pre-training done — best acc: %.2f%%",
            hist["best_val_acc"],
        )
        save_checkpoint(
            model,
            str(output_dir / "pretrain_har.pth"),
            scaler=fit_scaler(HarDataset(args.har_dir, split="train")),
            config=cfg,
        )
        logger.info("Pre-train checkpoint saved to %s", output_dir / "pretrain_har.pth")

    # Load or initialize model
    if args.pretrained:
        logger.info("Loading pre-trained model from %s", args.pretrained)
        model, meta = load_checkpoint(args.pretrained, device=device)
    elif model is None:
        model = AttentionGRU(52, 128, 32, output_dim=6).to(device)

    # Fine-tune on ESP32 data
    if args.data_dir:

        logger.info("=== ESP32 fine-tuning ===")
        model, hist = finetune_esp32(model, args.data_dir, device, {**cfg, "num_classes": 6})

        scaler_path = output_dir / "activity_scaler.json"
        ds = Esp32Dataset(args.data_dir)
        scaler = fit_scaler(ds)
        save_scaler(scaler, str(scaler_path))

        checkpoint_path = output_dir / "model.pth"
        save_checkpoint(
            model, str(checkpoint_path), scaler=scaler, config=cfg
        )
        logger.info("Fine-tuned model saved to %s", checkpoint_path)
        logger.info("Best val acc: %.2f%%", hist["best_val_acc"])

    if not args.data_dir and not args.har_dir:
        parser.error("At least --data-dir or --har-dir required")


if __name__ == "__main__":
    main()
