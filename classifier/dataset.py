import json
import pathlib

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler


LABEL_MAP_ESP32 = {"walking": 0, "sitting": 1, "standing": 2}

TARGET_SUBCARRIERS = 52
TARGET_TIMESTEPS = 50


def _center_crop_1d(arr: np.ndarray, target: int, axis: int) -> np.ndarray:
    n = arr.shape[axis]
    if n <= target:
        pad_before = (target - n) // 2
        pad_after = target - n - pad_before
        pad_width = [(0, 0)] * arr.ndim
        pad_width[axis] = (pad_before, pad_after)
        return np.pad(arr, pad_width, mode="constant")
    start = (n - target) // 2
    slc = [slice(None)] * arr.ndim
    slc[axis] = slice(start, start + target)
    return arr[tuple(slc)]


class Esp32Dataset(torch.utils.data.Dataset):
    def __init__(self, root_dir: str, transform=None, scaler: StandardScaler | None = None):
        self.root_dir = pathlib.Path(root_dir)
        self.transform = transform
        self.scaler = scaler
        self.samples: list[np.ndarray] = []
        self.labels: list[int] = []

        for label_name, label_idx in LABEL_MAP_ESP32.items():
            label_dir = self.root_dir / label_name
            if not label_dir.is_dir():
                continue
            for npy_path in sorted(label_dir.rglob("*.npy")):
                data = np.load(npy_path)
                if data.ndim != 3:
                    continue
                for i in range(data.shape[0]):
                    sample = data[i].astype(np.float32)

                    sample = _center_crop_1d(sample, TARGET_SUBCARRIERS, axis=1)
                    sample = _center_crop_1d(sample, TARGET_TIMESTEPS, axis=0)

                    self.samples.append(sample)
                    self.labels.append(label_idx)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        x = self.samples[idx].copy()
        label = self.labels[idx]

        if self.scaler is not None:
            orig_shape = x.shape
            x_2d = x.reshape(1, -1)
            x_2d = self.scaler.transform(x_2d)
            x = x_2d.reshape(orig_shape)

        # Temporal difference: highlight motion patterns
        x_diff = np.diff(x, axis=0)  # (49, 52)
        x = np.vstack([np.zeros((1, x.shape[1]), dtype=x.dtype), x_diff])  # (50, 52)

        x = torch.from_numpy(x)
        label = torch.tensor(label, dtype=torch.long)

        if self.transform is not None:
            x = self.transform(x)

        return x, label


class HarDataset(torch.utils.data.Dataset):
    """Load HAR dataset from IEEE DataPort (Experiments 2 + 3).

    Supports both CSV (Experiment-3) and pcap (Experiment-2) sources.
    All samples are center-cropped to (TARGET_TIMESTEPS, TARGET_SUBCARRIERS).

    Unified 6-class labels:
      Empty=0, Lying=1, Sitting=2, Standing=3, Walking=4, Falling=5
    """

    def __init__(self, root_dir: str, split: str = "train", scaler: StandardScaler | None = None):
        self.root_dir = pathlib.Path(root_dir)
        self.scaler = scaler

        self.label_map = {
            "walking": 0,
            "walk": 0,
            "running": 1,
            "run": 1,
            "lying": 2,
            "lie": 2,
            "falling": 3,
            "fall": 3,
            "sitting": 4,
            "sit": 4,
            "standing": 5,
            "stand": 5,
        }

        self.samples: list[np.ndarray] = []
        self.labels: list[int] = []

        self._load_csv_files()
        self._load_pcap_files()

        if split in ("train", "test") and len(self.samples) >= 2:
            from sklearn.model_selection import train_test_split

            indices = np.arange(len(self.samples))
            train_idx, test_idx = train_test_split(
                indices,
                test_size=0.2,
                random_state=42,
                stratify=self.labels,
            )
            selected = train_idx if split == "train" else test_idx
            self.samples = [self.samples[i] for i in selected]
            self.labels = [self.labels[i] for i in selected]

    def _load_csv_files(self) -> None:
        for csv_path in sorted(self.root_dir.rglob("*.csv")):
            name = csv_path.stem
            activity = name.split("_")[0].lower()
            if activity not in self.label_map:
                continue

            try:
                data = np.loadtxt(str(csv_path), delimiter=",", skiprows=1)
            except Exception:
                continue

            if data.ndim != 2:
                continue

            data = data.astype(np.float32)
            data = _center_crop_1d(data, TARGET_TIMESTEPS, axis=0)
            data = _center_crop_1d(data, TARGET_SUBCARRIERS, axis=1)

            self.samples.append(data)
            self.labels.append(self.label_map[activity])

    def _load_pcap_files(self) -> None:
        from .pcap_reader import parse_experiment2_pcap

        pcap_files = sorted(self.root_dir.rglob("*.pcap"))
        for pcap_path in pcap_files:
            activity = pcap_path.parent.name.lower()
            if activity not in self.label_map:
                continue

            try:
                data = parse_experiment2_pcap(str(pcap_path))
            except Exception:
                continue

            if data is None or data.ndim != 2:
                continue

            data = data.astype(np.float32)
            data = _center_crop_1d(data, TARGET_TIMESTEPS, axis=0)
            data = _center_crop_1d(data, TARGET_SUBCARRIERS, axis=1)

            self.samples.append(data)
            self.labels.append(self.label_map[activity])

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        x = self.samples[idx].copy()
        label = self.labels[idx]

        if self.scaler is not None:
            orig_shape = x.shape
            x_2d = x.reshape(1, -1)
            x_2d = self.scaler.transform(x_2d)
            x = x_2d.reshape(orig_shape)

        x = torch.from_numpy(x)
        label = torch.tensor(label, dtype=torch.long)

        return x, label


def fit_scaler(dataset: torch.utils.data.Dataset) -> StandardScaler:
    samples = []
    for i in range(len(dataset)):
        x, _ = dataset[i]
        if isinstance(x, torch.Tensor):
            x = x.numpy()
        samples.append(x.flatten())
    all_data = np.stack(samples, axis=0)
    scaler = StandardScaler()
    scaler.fit(all_data)
    return scaler


def save_scaler(scaler: StandardScaler, path: str) -> None:
    state = {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "var": scaler.var_.tolist(),
        "n_features": int(scaler.n_features_in_),
        "n_samples_seen": int(scaler.n_samples_seen_),
    }
    with open(path, "w") as f:
        json.dump(state, f)


def load_scaler(path: str) -> StandardScaler:
    with open(path) as f:
        state = json.load(f)
    scaler = StandardScaler()
    scaler.n_features_in_ = state["n_features"]
    scaler.mean_ = np.array(state["mean"], dtype=np.float64)
    scaler.scale_ = np.array(state["scale"], dtype=np.float64)
    scaler.var_ = np.array(state["var"], dtype=np.float64)
    scaler.n_samples_seen_ = state["n_samples_seen"]
    return scaler
