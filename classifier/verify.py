import os
import pathlib
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import logging

# Ensure output directory exists
os.makedirs("artifacts", exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("verify")

DATA_DIR = "data/activities"
TARGET_SUBCARRIERS = 52
TARGET_TIMESTEPS = 50

def load_data():
    X = []
    labels = []
    class_names = []
    
    root = pathlib.Path(DATA_DIR)
    if not root.exists():
        logger.error(f"Data directory {DATA_DIR} not found!")
        return [], [], []

    folders = sorted([f for f in root.iterdir() if f.is_dir()])
    
    for idx, folder in enumerate(folders):
        class_names.append(folder.name)
        npy_files = list(folder.rglob("*.npy"))
        logger.info(f"Loading {len(npy_files)} files from {folder.name}...")
        
        for npy_path in npy_files:
            try:
                data = np.load(npy_path) # (N, T, C)
                if data.ndim != 3: continue
                
                for i in range(data.shape[0]):
                    sample = data[i]
                    # Center crop to target size
                    t_start = max(0, (sample.shape[0] - TARGET_TIMESTEPS) // 2)
                    c_start = max(0, (sample.shape[1] - TARGET_SUBCARRIERS) // 2)
                    sample = sample[t_start:t_start+TARGET_TIMESTEPS, c_start:c_start+TARGET_SUBCARRIERS]
                    
                    # Statistical features (Mean, Std, Max, Min)
                    mean_feat = np.mean(sample, axis=0) 
                    std_feat = np.std(sample, axis=0)
                    X.append(np.concatenate([mean_feat, std_feat]))
                    labels.append(idx)
            except Exception as e:
                logger.warning(f"Error loading {npy_path}: {e}")
                
    return np.array(X), np.array(labels), class_names

def main():
    X, y, class_names = load_data()
    if len(X) == 0:
        logger.error("No data found! Please collect some data first.")
        return

    logger.info(f"Analyzing {len(X)} samples across {len(class_names)} classes...")

    # 1. Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 2. PCA for visualization
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_scaled)

    # 3. Calculate Clustering Quality
    sil_score = silhouette_score(X_scaled, y)
    logger.info(f"Silhouette Score: {sil_score:.4f}")

    # 4. Plotting
    plt.figure(figsize=(12, 8))
    # Use a fixed color map
    colors = plt.cm.get_cmap('tab10')
    
    for i, name in enumerate(class_names):
        mask = (y == i)
        plt.scatter(X_pca[mask, 0], X_pca[mask, 1], label=name, color=colors(i), alpha=0.6, edgecolors='w')

    plt.title(f"PCA Analysis of CSI Features\nDataset: {len(X)} samples | Silhouette Score: {sil_score:.4f}")
    plt.xlabel("Principal Component 1 (PC1)")
    plt.ylabel("Principal Component 2 (PC2)")
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    
    output_path = "artifacts/feature_verification.png"
    plt.savefig(output_path)
    logger.info(f"Analysis complete. Plot saved to {output_path}")
    print(f"\n[SUMMARY] Silhouette Score: {sil_score:.4f}")
    print(f"A score < 0 means features are heavily overlapping (Neural Network required).")
    print(f"A score > 0.5 means features are easily separable by simple algorithms.")

if __name__ == "__main__":
    main()
