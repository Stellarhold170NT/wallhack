"""Unit tests for classifier/collect.py CLI collection tool."""

import json
import pathlib
import tempfile

import pytest

from classifier.collect import CsiCollector


class TestCsiCollectorInit:
    def test_collector_initializes(self):
        collector = CsiCollector(
            label="walking",
            duration=30.0,
            output_dir="data/activities",
        )
        assert collector.label == "walking"
        assert collector.duration == 30.0
        assert collector.port == 5005
        assert collector.host == "0.0.0.0"
        assert collector.min_samples == 10

    def test_collector_custom_params(self):
        collector = CsiCollector(
            label="running",
            duration=60.0,
            output_dir="/tmp/collect",
            port=9999,
            host="127.0.0.1",
            min_samples=5,
        )
        assert collector.label == "running"
        assert collector.duration == 60.0
        assert str(collector.output_dir) == str(pathlib.Path("/tmp/collect/running"))
        assert collector.port == 9999
        assert collector.host == "127.0.0.1"
        assert collector.min_samples == 5

    def test_collector_rejects_invalid_label(self):
        with pytest.raises(ValueError, match="Unknown label"):
            CsiCollector(label="jumping", duration=30)

    def test_all_valid_labels_accepted(self):
        for label in ["walking", "running", "lying", "bending", "falling", "sitting", "standing"]:
            collector = CsiCollector(label=label, duration=10)
            assert collector.label == label


class TestCsiCollectorOperations:
    def test_output_dir_uses_label_subdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = CsiCollector(
                label="walking",
                duration=5,
                output_dir=tmp,
            )
            expected = pathlib.Path(tmp) / "walking"
            assert collector.output_dir == expected

    def test_save_window_creates_npy_and_json(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            collector = CsiCollector(
                label="walking",
                duration=5,
                output_dir=tmp,
            )
            window = np.ones((50, 52), dtype=np.float32)
            collector._save_window(node_id=1, window=window)

            npy_files = list(pathlib.Path(tmp).rglob("*.npy"))
            json_files = list(pathlib.Path(tmp).rglob("*.json"))

            assert len(npy_files) >= 1
            assert len(json_files) >= 1

            loaded = np.load(npy_files[0])
            assert loaded.shape == (50, 52)

    def test_metadata_json_contains_required_fields(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            collector = CsiCollector(
                label="bending",
                duration=10,
                output_dir=tmp,
            )
            window = np.ones((50, 52), dtype=np.float32)
            collector._save_window(node_id=2, window=window)

            json_files = list(pathlib.Path(tmp).rglob("*.json"))
            assert len(json_files) >= 1

            with open(json_files[0]) as f:
                meta = json.load(f)

            assert meta["label"] == "bending"
            assert meta["node_id"] == 2
            assert meta["subcarrier_count"] == 52
            assert meta["sample_count"] == 50
            assert meta["window_size"] == 50
            assert meta["step_size"] == 25
            assert "timestamp" in meta
            assert "duration" in meta

    def test_file_naming_pattern(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp:
            collector = CsiCollector(label="lying", duration=5, output_dir=tmp)
            window = np.ones((50, 52), dtype=np.float32)
            collector._save_window(node_id=3, window=window)

            npy_files = list(pathlib.Path(tmp).rglob("*.npy"))
            name = npy_files[0].stem

            parts = name.split("_")
            assert len(parts) >= 2
            assert parts[-1] == "3"
            assert "T" in parts[0]


class TestCLI:
    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "classifier.collect", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0
        assert "--label" in result.stdout
        assert "--duration" in result.stdout
        assert "--output-dir" in result.stdout

    def test_cli_rejects_missing_label(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "classifier.collect", "--duration", "10"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0

    def test_cli_rejects_invalid_label(self):
        import subprocess
        result = subprocess.run(
            ["python", "-m", "classifier.collect", "--label", "flying", "--duration", "1"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
