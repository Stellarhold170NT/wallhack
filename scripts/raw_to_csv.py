import numpy as np
import json
import pandas as pd
import argparse
import os

def convert_to_csv(npy_path, json_path, output_path):
    print(f"Loading data from {npy_path}...")
    
    # Load CSI matrix
    data = np.load(npy_path)
    
    # Load metadata
    with open(json_path, 'r') as f:
        meta = json.load(f)
    
    node_id = meta.get("node_id", "unknown")
    
    # Create column names: subcarrier_0, subcarrier_1, ...
    num_subcarriers = data.shape[1]
    columns = [f"sc_{i}" for i in range(num_subcarriers)]
    
    # Convert to DataFrame
    df = pd.DataFrame(data, columns=columns)
    
    # Add metadata columns at the beginning
    df.insert(0, "node_id", node_id)
    df.insert(1, "frame_index", range(len(df)))
    
    # Save to CSV
    print(f"Saving to {output_path}...")
    df.to_csv(output_path, index=False)
    print("Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Directory containing .npy and .json files")
    parser.add_argument("--output", help="Output CSV filename (optional)")
    args = parser.parse_args()
    
    # Find the files
    npy_files = [f for f in os.listdir(args.dir) if f.endswith(".npy")]
    
    for npy_file in npy_files:
        base_name = npy_file.replace(".npy", "")
        json_file = base_name + ".json"
        
        npy_path = os.path.join(args.dir, npy_file)
        json_path = os.path.join(args.dir, json_file)
        
        if os.path.exists(json_path):
            output_path = args.output or os.path.join(args.dir, base_name + ".csv")
            convert_to_csv(npy_path, json_path, output_path)
        else:
            print(f"Warning: Metadata file {json_file} not found for {npy_file}")
