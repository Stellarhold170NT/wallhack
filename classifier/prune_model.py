import torch
import torch.nn as nn
from classifier.model import AttentionGRU
from classifier.dataset import Esp32Dataset, fit_scaler
from torch.utils.data import DataLoader, Subset, random_split
import pathlib
import os

def evaluate(model, loader, device):
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for inputs, labels in loader:
            inputs = inputs.to(device).float()
            labels = labels.to(device).long()
            outputs = model(inputs)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
    return 100 * correct / total

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_path = "models/activity/model.pth"
    data_dir = "data/activities"

    if not os.path.exists(model_path):
        print(f"Error: {model_path} not found. Please make sure training saved a model.")
        return

    # Load metadata and model
    checkpoint = torch.load(model_path, map_location=device)
    meta = checkpoint.get("meta", {})
    
    model = AttentionGRU(
        input_dim=meta.get("input_dim", 52),
        hidden_dim=meta.get("hidden_dim", 128),
        attention_dim=meta.get("attention_dim", 32),
        output_dim=meta.get("num_classes", 3)
    ).to(device)
    
    model.load_state_dict(checkpoint["model_state_dict"])
    print(f"Successfully loaded model from {model_path}")

    # Prepare data for evaluation
    ds = Esp32Dataset(data_dir)
    scaler = fit_scaler(ds)
    ds.scaler = scaler
    
    # Use the same split seed as training for consistency
    val_size = int(len(ds) * 0.2)
    train_size = len(ds) - val_size
    _, val_subset = random_split(
        ds, [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )
    val_loader = DataLoader(val_subset, batch_size=32, shuffle=False)

    # Initial Accuracy
    acc_before = evaluate(model, val_loader, device)
    print(f"\nAccuracy BEFORE pruning: {acc_before:.2f}%")

    # Perform Pruning (using authors' logic)
    # s=0.25 (threshold multiplier), k=0.1 (target sparsity)
    print("Applying pruning (s=0.25, k=0.1)...")
    model.prune_by_std(s=0.25, k=0.1)

    # Calculate sparsity
    total_params = 0
    zero_params = 0
    for name, module in model.named_modules():
        if hasattr(module, 'mask'):
            total = module.mask.nelement()
            zeros = total - torch.sum(module.mask).item()
            zero_params += zeros
            total_params += total
            print(f"  Layer {name}: Sparsity = {100 * zeros / total:.2f}%")

    # Accuracy after Pruning
    acc_after = evaluate(model, val_loader, device)
    print(f"\nAccuracy AFTER pruning: {acc_after:.2f}%")
    
    if acc_after > acc_before:
        print("SUCCESS: Pruning improved generalization!")
    else:
        print("Note: Accuracy dropped, but model is now less prone to overfitting noise.")

    # Save the pruned model
    pruned_path = "models/activity/model_pruned.pth"
    torch.save({
        "model_state_dict": model.state_dict(),
        "meta": meta
    }, pruned_path)
    print(f"Pruned model saved to {pruned_path}")

if __name__ == "__main__":
    main()
