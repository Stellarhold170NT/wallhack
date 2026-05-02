import json
import tempfile
from pathlib import Path

import numpy as np
import torch

from classifier.model import AttentionGRU, count_parameters
from classifier.dataset import (
    Esp32Dataset,
    HarDataset,
    fit_scaler,
    save_scaler,
    load_scaler,
)
from sklearn.preprocessing import StandardScaler

rng = np.random.default_rng(42)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestAttentionGRU:
    def test_model_forward_shape(self):
        model = AttentionGRU(52, 128, 32, 4)
        x = torch.randn(8, 50, 52)
        y = model(x)
        assert y.shape == (8, 4)

    def test_model_forward_single_batch(self):
        model = AttentionGRU(52, 128, 32, 4)
        x = torch.randn(1, 50, 52)
        y = model(x)
        assert y.shape == (1, 4)

    def test_model_parameters(self):
        model = AttentionGRU(52, 128, 32, 4)
        n = count_parameters(model)
        assert 74000 <= n <= 90000, f"Expected 74K-90K, got {n}"

    def test_model_gradients(self):
        model = AttentionGRU(52, 128, 32, 4)
        x = torch.randn(8, 50, 52)
        y = model(x)
        loss = y.sum()
        loss.backward()
        for name, param in model.named_parameters():
            assert param.grad is not None, f"Gradient None for {name}"

    def test_attention_weights_sum_to_one(self):
        model = AttentionGRU(52, 128, 32, 4)
        model.eval()
        with torch.no_grad():
            x = torch.randn(4, 50, 52)
            gru_out, _ = model.gru(x)
            attn_scores = model.attention(gru_out).squeeze(-1)
            attn_weights = torch.softmax(attn_scores, dim=1)
            sums = attn_weights.sum(dim=1)
            for s in sums:
                assert abs(float(s) - 1.0) < 1e-5

    def test_no_pruning_code_present(self):
        import inspect

        src = inspect.getsource(AttentionGRU)
        assert "prune" not in src.lower()


# ---------------------------------------------------------------------------
# Esp32Dataset tests
# ---------------------------------------------------------------------------

def _make_synthetic_npy(path: Path, samples: int, timesteps: int, subcarriers: int):
    data = rng.standard_normal((samples, timesteps, subcarriers)).astype(np.float32)
    np.save(path, data)


class TestEsp32Dataset:
    def test_dataset_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label_dir in ["walking", "running", "lying", "falling", "sitting", "standing"]:
                (root / label_dir).mkdir()
                _make_synthetic_npy(
                    root / label_dir / "a.npy", samples=5, timesteps=50, subcarriers=52
                )
            ds = Esp32Dataset(str(root))
            assert len(ds) == 30
            x, y = ds[0]
            assert x.shape == (50, 52)
            assert y.item() == 0  # walking

    def test_dataset_crop_subcarriers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "walking").mkdir()
            _make_synthetic_npy(
                root / "walking" / "a.npy", samples=2, timesteps=50, subcarriers=128
            )
            ds = Esp32Dataset(str(root))
            x, _ = ds[0]
            assert x.shape == (50, 52)

    def test_dataset_pad_subcarriers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "walking").mkdir()
            _make_synthetic_npy(
                root / "walking" / "a.npy", samples=2, timesteps=50, subcarriers=30
            )
            ds = Esp32Dataset(str(root))
            x, _ = ds[0]
            assert x.shape == (50, 52)

    def test_dataset_pad_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "walking").mkdir()
            _make_synthetic_npy(
                root / "walking" / "a.npy", samples=2, timesteps=30, subcarriers=52
            )
            ds = Esp32Dataset(str(root))
            x, _ = ds[0]
            assert x.shape == (50, 52)

    def test_dataset_truncate_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "walking").mkdir()
            _make_synthetic_npy(
                root / "walking" / "a.npy", samples=2, timesteps=100, subcarriers=52
            )
            ds = Esp32Dataset(str(root))
            x, _ = ds[0]
            assert x.shape == (50, 52)

    def test_dataset_scaler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "walking").mkdir()
            _make_synthetic_npy(
                root / "walking" / "a.npy", samples=5, timesteps=50, subcarriers=52
            )
            ds = Esp32Dataset(str(root))
            scaler = fit_scaler(ds)
            assert scaler.n_features_in_ == 2600  # 50 * 52
            ds_with_scaler = Esp32Dataset(str(root), scaler=scaler)
            x, _ = ds_with_scaler[0]
            assert x.shape == (50, 52)

    def test_dataset_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ds = Esp32Dataset(str(tmp))
            assert len(ds) == 0

    def test_dataset_skips_bad_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "walking").mkdir()
            _make_synthetic_npy(
                root / "walking" / "good.npy", samples=1, timesteps=50, subcarriers=52
            )
            bad_path = root / "walking" / "bad.npy"
            np.save(bad_path, rng.random((10,)).astype(np.float32))
            ds = Esp32Dataset(str(root))
            assert len(ds) == 1

    def test_dataset_label_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label, idx in [("walking", 0), ("running", 1), ("lying", 2), ("falling", 3), ("sitting", 4), ("standing", 5)]:
                (root / label).mkdir()
                _make_synthetic_npy(
                    root / label / "a.npy", samples=2, timesteps=50, subcarriers=52
                )
            ds = Esp32Dataset(str(root))
            labels = {int(ds[i][1]) for i in range(len(ds))}
            assert labels == {0, 1, 2, 3, 4, 5}


# ---------------------------------------------------------------------------
# Scaler persistence tests
# ---------------------------------------------------------------------------

class TestHarDataset:
    def test_har_dataset_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for activity in ["Lying", "Sitting", "Standing", "Walking", "fall", "run"]:
                for i in range(5):
                    data = rng.standard_normal((500, 256)).astype(np.float32)
                    np.savetxt(
                        root / f"{activity}_{i}.csv",
                        data,
                        delimiter=",",
                        header=",".join(str(i) for i in range(256)),
                        comments="",
                    )
            ds = HarDataset(str(root), split="train")
            assert len(ds) == 24
            x, y = ds[0]
            assert x.shape == (50, 52)
            assert y.item() in {0, 1, 2, 3, 4, 5}

    def test_har_dataset_train_test_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for activity in ["Walking", "Standing", "fall"]:
                for i in range(10):
                    data = rng.standard_normal((500, 256)).astype(np.float32)
                    np.savetxt(
                        root / f"{activity}_{i}.csv",
                        data,
                        delimiter=",",
                        header=",".join(str(i) for i in range(256)),
                        comments="",
                    )
            train_ds = HarDataset(str(root), split="train")
            test_ds = HarDataset(str(root), split="test")
            assert len(train_ds) == 24
            assert len(test_ds) == 6

    def test_har_dataset_skips_unknown_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = rng.standard_normal((500, 256)).astype(np.float32)
            np.savetxt(
                root / "Walking_0.csv",
                data,
                delimiter=",",
                header=",".join(str(i) for i in range(256)),
                comments="",
            )
            np.save(root / "unknown.npy", rng.random((10,)))
            ds = HarDataset(str(root))
            assert len(ds) == 1


class TestScalerPersistence:
    def test_roundtrip(self):
        scaler = StandardScaler()
        X = rng.standard_normal((100, 2600)).astype(np.float64)
        scaler.fit(X)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scaler.json"
            save_scaler(scaler, str(path))
            loaded = load_scaler(str(path))
        assert np.allclose(scaler.mean_, loaded.mean_)
        assert np.allclose(scaler.scale_, loaded.scale_)
        assert scaler.n_features_in_ == loaded.n_features_in_
        assert scaler.n_samples_seen_ == loaded.n_samples_seen_

    def test_loaded_scaler_transforms_correctly(self):
        scaler = StandardScaler()
        X = rng.standard_normal((100, 2600)).astype(np.float64)
        scaler.fit(X)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scaler.json"
            save_scaler(scaler, str(path))
            loaded = load_scaler(str(path))
        x_in = rng.standard_normal((5, 2600)).astype(np.float64)
        y_orig = scaler.transform(x_in)
        y_loaded = loaded.transform(x_in)
        assert np.allclose(y_orig, y_loaded)

    def test_saved_file_is_valid_json(self):
        scaler = StandardScaler()
        X = rng.standard_normal((50, 2600)).astype(np.float64)
        scaler.fit(X)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scaler.json"
            save_scaler(scaler, str(path))
            with open(path) as f:
                data = json.load(f)
        for key in ["mean", "scale", "var", "n_features", "n_samples_seen"]:
            assert key in data


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_model_consumes_dataset_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label in ["walking", "running", "lying", "falling", "sitting", "standing"]:
                (root / label).mkdir()
                _make_synthetic_npy(
                    root / label / "a.npy", samples=3, timesteps=50, subcarriers=52
                )
            ds = Esp32Dataset(str(root))
            loader = torch.utils.data.DataLoader(ds, batch_size=4)

            model = AttentionGRU(52, 128, 32, 6)
            model.eval()
            with torch.no_grad():
                x, y = next(iter(loader))
                out = model(x)
                assert out.shape == (4, 6)

    def test_model_on_scaled_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "walking").mkdir()
            _make_synthetic_npy(
                root / "walking" / "a.npy", samples=10, timesteps=50, subcarriers=52
            )
            ds = Esp32Dataset(str(root))
            scaler = fit_scaler(ds)
            ds_scaled = Esp32Dataset(str(root), scaler=scaler)
            loader = torch.utils.data.DataLoader(ds_scaled, batch_size=2)

            model = AttentionGRU(52, 128, 32, 6)
            model.eval()
            with torch.no_grad():
                x, y = next(iter(loader))
                out = model(x)
                assert out.shape == (2, 6)
