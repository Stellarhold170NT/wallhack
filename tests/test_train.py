"""Unit tests for classifier/train.py training pipeline."""

import json
import pathlib
import tempfile

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from classifier.model import AttentionGRU
from classifier.train import (
    train_model,
    cross_validate,
    save_checkpoint,
    load_checkpoint,
)
from classifier.dataset import fit_scaler, save_scaler

rng = np.random.default_rng(42)


def _synthetic_dataset(n_samples=200, n_timesteps=50, n_sub=52, n_classes=4):
    X = rng.standard_normal((n_samples, n_timesteps, n_sub)).astype(np.float32)
    y = rng.integers(0, n_classes, size=n_samples).astype(np.int64)
    return TensorDataset(torch.from_numpy(X), torch.from_numpy(y))


class TestTrainModel:
    def test_model_converges(self):
        ds = _synthetic_dataset(n_samples=200, n_classes=4)
        loader = DataLoader(ds, batch_size=16, shuffle=True)
        val_ds = _synthetic_dataset(n_samples=40, n_classes=4)
        val_loader = DataLoader(val_ds, batch_size=16)

        model = AttentionGRU(52, 64, 16, 4)
        device = torch.device("cpu")
        model, hist = train_model(
            model, loader, val_loader, device,
            config={"epochs": 5, "lr": 1e-3, "patience": 5, "augment": False, "batch_size": 16},
        )

        assert hist["train_loss"][0] > hist["train_loss"][-1], (
            f"Loss did not decrease: {hist['train_loss'][0]:.4f} → {hist['train_loss'][-1]:.4f}"
        )
        assert "best_val_acc" in hist

    def test_early_stopping(self):
        ds = _synthetic_dataset(n_samples=200, n_classes=4)
        loader = DataLoader(ds, batch_size=16, shuffle=True)
        val_ds = _synthetic_dataset(n_samples=40, n_classes=4)
        val_loader = DataLoader(val_ds, batch_size=16)

        model = AttentionGRU(52, 64, 16, 4)
        device = torch.device("cpu")
        model, hist = train_model(
            model, loader, val_loader, device,
            config={"epochs": 50, "lr": 1e-3, "patience": 2, "augment": False, "batch_size": 16},
        )

        n_epochs = len(hist["val_loss"])
        assert n_epochs < 50, f"Early stopping should trigger before 50 epochs, got {n_epochs}"


class TestCheckpoint:
    def test_save_load_roundtrip(self):
        model = AttentionGRU(52, 128, 32, 4)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "test_model.pth"
            save_checkpoint(model, str(path))
            loaded, info = load_checkpoint(str(path))

        for p1, p2 in zip(model.parameters(), loaded.parameters()):
            assert torch.allclose(p1, p2), "Model weights differ after roundtrip"

    def test_save_load_with_scaler(self):
        model = AttentionGRU(52, 64, 16, 4)
        X = rng.standard_normal((50, 52 * 50)).astype(np.float64)

        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        scaler.fit(X)

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "test_model.pth"
            save_checkpoint(model, str(path), scaler=scaler, config={"lr": 1e-3})
            loaded, info = load_checkpoint(str(path))

        assert info["scaler"] is not None
        assert np.allclose(info["scaler"].mean_, scaler.mean_)
        assert info["config"]["lr"] == 1e-3

    def test_save_creates_files(self):
        model = AttentionGRU(52, 64, 16, 4)
        with tempfile.TemporaryDirectory() as tmp:
            pth = pathlib.Path(tmp) / "chkpt.pth"
            save_checkpoint(model, str(pth))
            assert pth.exists()
            assert pth.stat().st_size > 0


class TestCrossValidate:
    def test_cv_runs(self):
        ds = _synthetic_dataset(n_samples=60, n_classes=4)
        device = torch.device("cpu")
        accs = cross_validate(
            ds, device,
            config={"epochs": 3, "lr": 1e-3, "n_splits": 2, "patience": 3,
                    "augment": False, "batch_size": 8, "hidden_dim": 32, "attention_dim": 8},
        )
        assert len(accs) == 2
        assert all(0.0 <= a <= 100.0 for a in accs)


class TestOutputShapes:
    def test_pretrain_har_produces_6class(self):
        from classifier.train import pretrain_har
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            ds = _synthetic_dataset(n_samples=100, n_classes=6)
            model = AttentionGRU(52, 32, 8, output_dim=6)

            device = torch.device("cpu")
            loader = DataLoader(ds, batch_size=16, shuffle=True)
            val_loader = DataLoader(_synthetic_dataset(n_samples=20, n_classes=6), batch_size=16)

            model, hist = train_model(
                model, loader, val_loader, device,
                config={"epochs": 2, "augment": False, "batch_size": 16},
            )
            assert model.fc.out_features == 6
            assert "best_val_acc" in hist

    def test_finetune_produces_7class(self):
        from classifier.train import finetune_esp32
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            with tempfile.TemporaryDirectory() as tmp:
                root = pathlib.Path(tmp)
                for label in ["walking", "running", "lying", "bending", "falling", "sitting", "standing"]:
                    (root / label).mkdir()
                    data = rng.standard_normal((3, 50, 52)).astype(np.float32)
                    np.save(root / label / "a.npy", data)

                model = AttentionGRU(52, 32, 8, output_dim=6)
                device = torch.device("cpu")
                model, hist = finetune_esp32(
                    model, str(tmp), device,
                    config={"epochs": 2, "augment": False, "batch_size": 4, "hidden_dim": 32, "attention_dim": 8},
                )
                assert model.fc.out_features == 7
                assert "best_val_acc" in hist


class TestCLI:
    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "classifier.train", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--data-dir" in result.stdout
        assert "--har-dir" in result.stdout
        assert "--cross-validate" in result.stdout
