import copy
import json
import logging
import pathlib
import time
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, Subset, TensorDataset, random_split

from .dataset import LABEL_MAP_ESP32, Esp32Dataset, fit_scaler, save_scaler
from .model import AttentionGRU

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("train")

DEFAULT_CONFIG = {
    "lr": 1e-3,
    "epochs": 100,
    "hidden_dim": 128,
    "attention_dim": 32,
    "patience": 20,
    "scheduler_type": "cosine",
    "batch_size": 32,
    "augment": True,
    "noise_copies": 0,  # Disabled as requested
    "mixup_prob": 0.3,
    "mixup_alpha": 1.0,
    "val_split": 0.2,
    "n_splits": 5,
    "num_classes": 3,
    "input_dim": 52,
    "timesteps": 50,
}


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    device: torch.device,
    config: dict[str, Any] | None = None,
) -> tuple[nn.Module, dict[str, Any]]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"])

    if cfg["scheduler_type"] == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg["epochs"])
    else:
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)

    best_acc = 0.0
    best_model_wts = copy.deepcopy(model.state_dict())
    best_loss = float("inf")
    patience_counter = 0

    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    try:
        for epoch in range(cfg["epochs"]):
            model.train()
            running_loss, running_corrects, total = 0.0, 0, 0

            for inputs, labels in train_loader:
                inputs, labels = inputs.to(device).float(), labels.to(device).long()
                use_mixup = cfg["augment"] and np.random.random() < cfg["mixup_prob"]

                if use_mixup:
                    from .augment import mixup_augment
                    X_mix, y_mix = mixup_augment(inputs.cpu().numpy(), labels.cpu().numpy(), 
                                               alpha=cfg["mixup_alpha"], prob=1.0, num_classes=cfg["num_classes"])
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
                _, preds = torch.max(outputs, 1)
                if use_mixup:
                    _, true_labels = torch.max(targets, 1)
                    running_corrects += int((preds == true_labels).sum())
                else:
                    running_corrects += int((preds == targets).sum())
                total += inputs.size(0)

            train_loss, train_acc = running_loss / total, 100.0 * running_corrects / total
            history["train_loss"].append(train_loss)
            history["train_acc"].append(train_acc)
            scheduler.step()

            # Validation
            model.eval()
            val_loss, val_corrects, val_total = 0.0, 0, 0
            with torch.no_grad():
                for inputs, labels in val_loader:
                    inputs, labels = inputs.to(device).float(), labels.to(device).long()
                    outputs = model(inputs)
                    loss = criterion(outputs, labels)
                    val_loss += loss.item() * inputs.size(0)
                    _, preds = torch.max(outputs, 1)
                    val_corrects += int((preds == labels).sum())
                    val_total += inputs.size(0)

            val_loss_avg, val_acc = val_loss / val_total, 100.0 * val_corrects / val_total
            history["val_loss"].append(val_loss_avg)
            history["val_acc"].append(val_acc)

            logger.info(f"Epoch {epoch+1:3d} | train_loss {train_loss:.4f} train_acc {train_acc:.2f}% | val_loss {val_loss_avg:.4f} val_acc {val_acc:.2f}%")

            improved = False
            if val_acc > best_acc:
                best_acc = val_acc
                best_model_wts = copy.deepcopy(model.state_dict())
                improved = True
            if val_loss_avg < best_loss:
                best_loss = val_loss_avg
                improved = True

            if improved: patience_counter = 0
            else: patience_counter += 1

            if patience_counter >= cfg["patience"]:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break
    except KeyboardInterrupt:
        logger.info("Training interrupted. Using best weights so far.")

    model.load_state_dict(best_model_wts)
    
    # --- AUTOMATIC PRUNING ---
    if hasattr(model, 'prune_by_std'):
        print("\n--- Performing Automatic Pruning ---")
        with torch.no_grad():
            model.prune_by_std(s=0.25, k=0.1)
    
    history["best_val_acc"] = best_acc
    return model, history


def finetune_esp32(model, esp32_root, device, config=None):
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    ds = Esp32Dataset(esp32_root)
    scaler = fit_scaler(ds)

    val_size = int(len(ds) * cfg["val_split"])
    train_subset, val_subset = random_split(ds, [len(ds) - val_size, val_size], 
                                          generator=torch.Generator().manual_seed(42))

    if cfg["augment"]:
        aug_ds = _augment_subset(ds, train_subset.indices, cfg)
    else:
        aug_ds = Subset(ds, train_subset.indices)

    aug_ds.scaler = scaler
    val_subset.dataset.scaler = scaler

    train_loader = DataLoader(aug_ds, batch_size=cfg["batch_size"], shuffle=True)
    val_loader = DataLoader(val_subset, batch_size=cfg["batch_size"], shuffle=False)

    # Reset FC layer
    old_fc = model.fc
    from .model import MaskedLinear
    model.fc = MaskedLinear(model.attention_dim, cfg["num_classes"]).to(device)
    
    if old_fc.weight.shape[1] == model.fc.weight.shape[1]:
        with torch.no_grad():
            model.fc.weight[:] = old_fc.weight[:cfg["num_classes"]]
            if model.fc.bias is not None: model.fc.bias[:] = old_fc.bias[:cfg["num_classes"]]
    
    model, history = train_model(model, train_loader, val_loader, device, cfg)
    return model, history


def _augment_subset(ds, indices, cfg):
    from .augment import shift_augment, noise_augment
    samples_x, samples_y = [], []
    for i in indices:
        x, y = ds[i]
        samples_x.append(x.numpy() if isinstance(x, torch.Tensor) else np.asarray(x))
        samples_y.append(int(y))

    X, y_vec = np.stack(samples_x), np.array(samples_y)
    X, y_vec = shift_augment(X, y_vec)
    X, y_vec = noise_augment(X, y_vec, num_copies=cfg.get("noise_copies", 0))

    return TensorDataset(torch.from_numpy(X.astype(np.float32)), torch.from_numpy(y_vec).long())


def load_checkpoint(path, device):
    checkpoint = torch.load(path, map_location=device)
    meta = checkpoint.get("meta", {})
    model = AttentionGRU(
        input_dim=meta.get("input_dim", 52),
        hidden_dim=meta.get("hidden_dim", 128),
        attention_dim=meta.get("attention_dim", 32),
        output_dim=meta.get("num_classes", 3),
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    return model, meta


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=str)
    parser.add_argument("--output-dir", type=str, default="models/activity")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = {**DEFAULT_CONFIG, "epochs": args.epochs, "lr": args.lr}
    
    model = AttentionGRU(52, 128, 32, output_dim=len(LABEL_MAP_ESP32)).to(device)

    if args.data_dir:
        model, hist = finetune_esp32(model, args.data_dir, device, cfg)
        
        # Save results
        scaler_path = output_dir / "activity_scaler.json"
        ds = Esp32Dataset(args.data_dir)
        scaler = fit_scaler(ds)
        save_scaler(scaler, str(scaler_path))

        torch.save({
            "model_state_dict": model.state_dict(),
            "meta": {**cfg, "num_classes": len(LABEL_MAP_ESP32)},
            "history": hist
        }, output_dir / "model.pth")
        
        print(f"Model saved to {output_dir / 'model.pth'}")

if __name__ == "__main__":
    main()
