import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import pathlib

def view_session(session_name: str):
    # Đường dẫn tới data/raw
    base_dir = pathlib.Path("data/raw")
    session_dir = base_dir / session_name

    if not session_dir.exists():
        print(f"❌ Lỗi: Thư mục phiên làm việc '{session_dir}' không tồn tại.")
        return

    # Tìm tất cả các file .npy
    npy_files = list(session_dir.glob("*.npy"))
    
    if not npy_files:
        print(f"⚠️ Không tìm thấy file .npy nào trong {session_dir}")
        return

    print(f"🔍 Tìm thấy {len(npy_files)} file dữ liệu. Đang chuẩn bị vẽ đồ thị...")

    # Tạo cửa sổ đồ thị với nhiều tiểu mục (subplots)
    fig, axes = plt.subplots(len(npy_files), 1, figsize=(15, 6 * len(npy_files)), squeeze=False)
    
    for i, npy_path in enumerate(npy_files):
        data = np.load(npy_path)
        ax = axes[i, 0]
        
        # Vẽ Heatmap
        im = ax.imshow(data.T, aspect='auto', cmap='jet', interpolation='nearest')
        plt.colorbar(im, ax=ax, label='Amplitude')
        
        ax.set_title(f"Node Data: {npy_path.name} (Shape: {data.shape})")
        ax.set_xlabel("Time (Frames)")
        ax.set_ylabel("Subcarriers (0-63)")

    plt.tight_layout()
    print("✅ Hiển thị đồ thị. Hãy đóng cửa sổ đồ thị để kết thúc script.")
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Nếu không nhập tên thư mục, liệt kê các thư mục đang có
        print("💡 Cách dùng: python scripts/view_csi.py <ten_thu_muc_session>")
        print("\nCác session hiện có trong data/raw:")
        base_dir = pathlib.Path("data/raw")
        if base_dir.exists():
            for d in base_dir.iterdir():
                if d.is_dir():
                    print(f" - {d.name}")
    else:
        view_session(sys.argv[1])
