"""Data augmentation for CSI activity recognition.

Implements temporal shifting, multiplicative Gaussian noise, and
MixUp augmentation from Kang et al. 2025.  All functions operate on
numpy arrays to avoid GPU memory pressure with large augmented sets.

Ref: D-43 (offline training with augmentation)
"""

import numpy as np


def shift_augment(
    X: np.ndarray,
    y: np.ndarray,
    max_shift: int = 10,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Temporal shifting: 20 shifted copies + original = 21× samples.

    Each sample is rolled along the time axis (axis=1) by each shift
    value in [-max_shift, max_shift] excluding 0.

    Args:
        X: Input shape (samples, time_steps, subcarriers).
        y: Labels shape (samples,) — integer class indices.
        max_shift: Maximum shift magnitude (default 10 → ±10 steps).
        rng: Optional numpy Generator for reproducibility.

    Returns:
        X_aug: shape (samples * 21, time_steps, subcarriers)
        y_aug: shape (samples * 21,)
    """
    shifts = [s for s in range(-max_shift, max_shift + 1) if s != 0]

    X_aug = [X]
    y_aug = [y]

    for shift in shifts:
        X_shifted = np.roll(X, shift, axis=1)
        X_aug.append(X_shifted)
        y_aug.append(y.copy())

    return np.concatenate(X_aug, axis=0), np.concatenate(y_aug, axis=0)


def noise_augment(
    X: np.ndarray,
    y: np.ndarray,
    num_copies: int = 3,
    noise_std: float = 1.0,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Multiplicative Gaussian noise: num_copies + original = (num_copies+1)×.

    X_noisy = X + X * ε  where ε ~ N(0, noise_std)

    Args:
        X: Input shape (samples, time_steps, subcarriers).
        y: Labels shape (samples,) — integer class indices.
        num_copies: Number of noisy copies per sample (default 3).
        noise_std: Standard deviation of multiplicative noise (default 1.0).
        rng: Optional numpy Generator for reproducibility.

    Returns:
        X_aug: shape (samples * (num_copies+1), time_steps, subcarriers)
        y_aug: shape (samples * (num_copies+1),)
    """
    if rng is None:
        rng = np.random.default_rng()

    X_aug = [X]
    y_aug = [y]

    for _ in range(num_copies):
        noise = rng.normal(0.0, noise_std, X.shape).astype(X.dtype)
        X_noisy = X + X * noise
        X_aug.append(X_noisy)
        y_aug.append(y.copy())

    return np.concatenate(X_aug, axis=0), np.concatenate(y_aug, axis=0)


def mixup_augment(
    X: np.ndarray,
    y: np.ndarray,
    alpha: float = 1.0,
    prob: float = 0.3,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """MixUp augmentation — randomly mixes sample pairs.

    For each sample with probability *prob*, mixes with another random
    sample:  X' = λ·X_i + (1-λ)·X_j  where λ ~ Beta(α, α).

    Labels are returned as one-hot soft targets:
        y' = λ·onehot(y_i) + (1-λ)·onehot(y_j)

    This function is designed for batch-level online use during training,
    not dataset-level offline augmentation.

    Args:
        X: Input batch shape (samples, time_steps, subcarriers).
        y: Labels shape (samples,) — integer class indices.
        alpha: Beta distribution parameter (default 1.0 = uniform mixing).
        prob: Probability of applying MixUp to each sample (default 0.3).
        rng: Optional numpy Generator for reproducibility.

    Returns:
        X_mixed: shape (samples, time_steps, subcarriers)
        y_mixed: one-hot soft labels shape (samples, num_classes)
    """
    if rng is None:
        rng = np.random.default_rng()

    num_classes = int(y.max()) + 1
    y_onehot = np.eye(num_classes)[y.astype(int)]

    X_out = X.copy()
    y_out = y_onehot.copy()

    idx = np.arange(len(X))
    rng.shuffle(idx)

    for i in range(len(X)):
        if rng.random() >= prob:
            continue

        j = idx[i]
        lam = rng.beta(alpha, alpha)

        X_out[i] = lam * X[i] + (1 - lam) * X[j]
        y_out[i] = lam * y_onehot[i] + (1 - lam) * y_onehot[j]

    return X_out, y_out


def augment_dataset(
    dataset,
    shift: bool = True,
    noise: bool = True,
    mixup: bool = False,
    rng: np.random.Generator | None = None,
):
    """Convenience: extract all data from a Dataset, augment, return new Dataset.

    Default augmentation: shift + noise (MixUp is optional per D-43).

    Args:
        dataset: A torch.utils.data.Dataset returning (x_tensor, y_tensor).
        shift: Apply temporal shift augmentation (21×).
        noise: Apply multiplicative noise augmentation (4×).
        mixup: Apply MixUp augmentation (same size, soft labels).
        rng: Optional numpy Generator for reproducibility.

    Returns:
        A new TensorDataset with augmented samples.
    """
    import torch

    X_list = []
    y_list = []
    for i in range(len(dataset)):
        x, y = dataset[i]
        X_list.append(x.numpy() if isinstance(x, torch.Tensor) else np.asarray(x))
        y_list.append(int(y) if isinstance(y, torch.Tensor) else int(y))

    X = np.stack(X_list, axis=0)
    y = np.array(y_list)

    if shift:
        X, y = shift_augment(X, y, rng=rng)
    if noise:
        X, y = noise_augment(X, y, rng=rng)
    if mixup:
        X, y = mixup_augment(X, y, rng=rng)

    X_tensor = torch.from_numpy(X.astype(np.float32))
    y_tensor = torch.from_numpy(y) if y.ndim == 1 else torch.from_numpy(y.astype(np.float32))

    return torch.utils.data.TensorDataset(X_tensor, y_tensor)
