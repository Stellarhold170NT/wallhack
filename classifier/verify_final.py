import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset, random_split
import numpy as np
from sklearn.metrics import confusion_matrix, classification_report
import matplotlib.pyplot as plt
import seaborn as sns
from .model import AttentionGRU
from .dataset import Esp32Dataset, fit_scaler, LABEL_MAP_ESP32
from .train import load_checkpoint

def evaluate_and_plot(model, loader, device, title, class_names):
    model.eval()
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(device).float()
            outputs = model(inputs)
            _, predicted = torch.max(outputs, 1)
            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.numpy())

    cm = confusion_matrix(all_labels, all_preds)
    acc = 100 * np.sum(np.diag(cm)) / np.sum(cm)
    
    print(f"\n--- {title} ---")
    print(f"Accuracy: {acc:.2f}%")
    print(classification_report(all_labels, all_preds, target_names=class_names))
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=class_names, yticklabels=class_names)
    plt.title(f"Confusion Matrix: {title} (Acc: {acc:.2f}%)")
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.savefig(f"artifacts/cm_{title.lower().replace(' ', '_')}.png")
    print(f"Confusion matrix saved to artifacts/cm_{title.lower().replace(' ', '_')}.png")

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_path = "models/activity/model.pth"
    data_dir = "data/activities"
    class_names = list(LABEL_MAP_ESP32.keys())

    # Load model
    model, meta = load_checkpoint(model_path, device)
    print(f"Loaded model from {model_path}")

    # Load dataset
    ds = Esp32Dataset(data_dir)
    scaler = fit_scaler(ds)
    ds.scaler = scaler
    
    # Split exactly like training
    val_size = int(len(ds) * 0.2)
    train_size = len(ds) - val_size
    train_subset, val_subset = random_split(
        ds, [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )
    
    train_loader = DataLoader(train_subset, batch_size=32, shuffle=False)
    val_loader = DataLoader(val_subset, batch_size=32, shuffle=False)

    # 1. Verify on Training Data (The "Learned" data)
    evaluate_and_plot(model, train_loader, device, "Training Set", class_names)
    
    # 2. Verify on Validation Data (The "Unseen" data)
    evaluate_and_plot(model, val_loader, device, "Validation Set", class_names)

if __name__ == "__main__":
    import os
    os.makedirs("artifacts", exist_ok=True)
    main()
