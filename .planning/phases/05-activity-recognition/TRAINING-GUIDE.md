# Phase 5 Training Guide — Từ Data Có Sẵn Đến Thu Thập

## Tổng quan Pipeline

```
HAR Dataset (Exp 2+3) ──► Pre-train ──► Model 6-class
                                        │
ESP32 Data (tự thu thập) ──► Fine-tune ──► Model 7-class
```

---

## Bước 1: Chuẩn bị HAR Dataset

### Cấu trúc thư mục

```
llm-wiki/raw/HAR/
├── Experiment-2/
│   └── realdata/input_data/30ms/csidata/
│       ├── fall/           ← pcap files (ngã)
│       ├── sit/            ← pcap files (ngồi)
│       ├── stand/          ← pcap files (đứng)
│       └── walk/           ← pcap files (đi)
│
└── Experiment-3/
    └── Data/
        ├── Empty_*.csv     ← không có ngườii
        ├── Lying_*.csv     ← nằm
        ├── Sitting_*.csv   ← ngồi
        ├── Standing_*.csv  ← đứng
        └── Walking_*.csv   ← đi bộ
```

### Unified labels (6 classes)

| Label | Class | Nguồn |
|-------|-------|-------|
| 0 | Empty | Exp-3 CSV |
| 1 | Lying | Exp-3 CSV |
| 2 | Sitting | Exp-2 pcap + Exp-3 CSV |
| 3 | Standing | Exp-2 pcap + Exp-3 CSV |
| 4 | Walking | Exp-2 pcap + Exp-3 CSV |
| 5 | Falling | Exp-2 pcap |

**Tổng:** ~1,539 samples (960 CSV + 579 pcap)

---

## Bước 2: Pre-train trên HAR Dataset

```bash
# Cách 1: Load toàn bộ HAR (cả Exp2 + Exp3)
python -m classifier.train \
  --har-dir "llm-wiki/raw/HAR" \
  --output-dir models/activity \
  --epochs 100 \
  --batch-size 32 \
  --lr 1e-3

# Cách 2: Chỉ dùng Exp-3 CSV
python -m classifier.train \
  --har-dir "llm-wiki/raw/HAR/Experiment-3/Data" \
  --output-dir models/activity \
  --epochs 100

# Cách 3: Chỉ dùng Exp-2 pcap (có falling)
python -m classifier.train \
  --har-dir "llm-wiki/raw/HAR/Experiment-2/realdata/input_data/30ms/csidata" \
  --output-dir models/activity \
  --epochs 100
```

**Output:**
- `models/activity/pretrain_har.pth` — model 6-class
- `models/activity/pretrain_har.scaler.json` — StandardScaler

---

## Bước 3: Thu thập ESP32-S3 Data (Tự thu thập)

### 3.1. Setup phần cứng

1. **Nạp firmware** cho 2x ESP32-S3:
   ```powershell
   # Node 1 (COM5)
   python -m esptool --chip esp32s3 --port COM5 --baud 460800 write_flash 0x0 build/esp32-csi-node.bin
   python provision.py --port COM5 --ssid "YOUR_WIFI" --password "PASS" --target-ip 192.168.1.3 --node-id 1

   # Node 2 (COM6)
   python -m esptool --chip esp32s3 --port COM6 --baud 460800 write_flash 0x0 build/esp32-csi-node.bin
   python provision.py --port COM6 --ssid "YOUR_WIFI" --password "PASS" --target-ip 192.168.1.3 --node-id 2
   ```

2. **Chạy aggregator** để nhận UDP frames:
   ```powershell
   python -m aggregator --port 5005
   ```

### 3.2. Thu thập từng activity

```bash
# 7 classes cần thu thập
# Khuyến nghị: 50-100 samples mỗi class, mỗi sample = 30 giây

python -m classifier.collect --label walking   --duration 30 --output-dir data/activities/
python -m classifier.collect --label running   --duration 30 --output-dir data/activities/
python -m classifier.collect --label lying     --duration 30 --output-dir data/activities/
python -m classifier.collect --label bending   --duration 30 --output-dir data/activities/
python -m classifier.collect --label falling   --duration 30 --output-dir data/activities/
python -m classifier.collect --label sitting   --duration 30 --output-dir data/activities/
python -m classifier.collect --label standing  --duration 30 --output-dir data/activities/
```

**Cấu trúc output:**
```
data/activities/
├── walking/
│   ├── 20250502T103045_1.npy   ← amplitude window (50, 52)
│   ├── 20250502T103045_1.json  ← metadata
│   └── ...
├── running/
├── lying/
├── bending/
├── falling/
├── sitting/
└── standing/
```

**Lưu ý quan trọng:**
- **Falling**: Cần thả ngườii xuống đệm/mattress (không an toàn nếu thả xuống sàn)
- **Sitting/Standing**: Ngồi/đứng yên, ít cử động
- Mỗi recording 30s → ~10-15 windows (50-frame, 25-step overlap)

---

## Bước 4: Fine-tune trên ESP32 Data

```bash
# Fine-tune với pre-trained weights
python -m classifier.train \
  --har-dir "llm-wiki/raw/HAR" \
  --data-dir data/activities/ \
  --output-dir models/activity \
  --epochs 100 \
  --batch-size 32 \
  --lr 1e-3 \
  --augment

# Hoặc: fine-tune không pre-train (từ scratch)
python -m classifier.train \
  --data-dir data/activities/ \
  --output-dir models/activity \
  --epochs 100
```

**Output:**
- `models/activity/model.pth` — model 7-class fine-tuned
- `models/activity/activity_scaler.json` — StandardScaler cho ESP32 data

---

## Bước 5: Cross-Validation

```bash
# 5-fold CV trên ESP32 data
python -m classifier.train \
  --data-dir data/activities/ \
  --cross-validate \
  --epochs 100 \
  --augment
```

**Output:**
```
5-fold CV: 85.43% avg accuracy
  Fold 1: 83.21%
  Fold 2: 87.65%
  Fold 3: 84.12%
  Fold 4: 86.78%
  Fold 5: 85.41%
```

---

## Bước 6: Inference Real-time

```bash
# Tích hợp vào aggregator pipeline
python -m aggregator \
  --port 5005 \
  --classifier-config '{"model_path":"models/activity/model.pth","scaler_path":"models/activity/activity_scaler.json"}'

# Hoặc: offline inference trên file .npy
python -m classifier \
  --input data/activities/walking/test.npy \
  --model models/activity/model.pth \
  --scaler models/activity/activity_scaler.json \
  --output predictions.json
```

---

## Tips & Best Practices

### 1. Data Augmentation
- **Shift**: ±10 frames (20 shifts) → 21× samples
- **Noise**: Multiplicative Gaussian → 4× samples
- **MixUp**: 30% probability, λ ~ Beta(1, 1)

### 2. Hyperparameters

| Parameter | Giá trị | Lý do |
|-----------|---------|-------|
| `epochs` | 100 | Early stopping patience=10 |
| `lr` | 1e-3 | Adam default, giảm cosine |
| `batch_size` | 32 | Cân bằng speed/memory |
| `hidden_dim` | 128 | Paper default |
| `attention_dim` | 32 | Paper default |

### 3. Troubleshooting

| Vấn đề | Nguyên nhân | Fix |
|--------|-------------|-----|
| Overfitting | val_acc << train_acc | Tăng augmentation, giảm epochs |
| Class imbalance | Một số class ít data | Thu thập thêm hoặc dùng weighted loss |
| "unknown" labels | infer.py chưa cập nhật LABEL_MAP | Kiểm tra `classifier/infer.py` |
| pcap parse lỗi | Numpy 2.x overflow | Đã fix trong `pcap_reader.py` (dùng Python list) |

### 4. Minimum Data Requirements

| Phase | Samples/Class | Tổng |
|-------|---------------|------|
| HAR Pre-train | ~200+ | ~1,200 |
| ESP32 Fine-tune | 30-50 | 210-350 |
| Production-ready | 100+ | 700+ |

---

## Quick Start (Copy-Paste)

```bash
# 1. Pre-train
python -m classifier.train --har-dir "llm-wiki/raw/HAR" --output-dir models/activity

# 2. Thu thập (chạy từng cái)
python -m classifier.collect --label walking --duration 30
python -m classifier.collect --label running --duration 30
python -m classifier.collect --label lying --duration 30
python -m classifier.collect --label bending --duration 30
python -m classifier.collect --label falling --duration 30
python -m classifier.collect --label sitting --duration 30
python -m classifier.collect --label standing --duration 30

# 3. Fine-tune
python -m classifier.train --har-dir "llm-wiki/raw/HAR" --data-dir data/activities/ --output-dir models/activity

# 4. Cross-validate
python -m classifier.train --data-dir data/activities/ --cross-validate

# 5. Run real-time
python -m aggregator --port 5005 --classifier-config '{"model_path":"models/activity/model.pth"}'
```