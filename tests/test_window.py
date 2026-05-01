"""Unit tests for SlidingWindow buffer."""

import numpy as np
import pytest
from aggregator.frame import CSIFrame
from processor.window import SlidingWindow


def make_frame(amplitudes: list[float], node_id: int = 1) -> CSIFrame:
    """Helper to create a CSIFrame with given amplitudes."""
    return CSIFrame(
        node_id=node_id,
        sequence=0,
        n_subcarriers=len(amplitudes),
        amplitudes=amplitudes,
        phases=[0.0] * len(amplitudes),
    )


class TestSlidingWindowBasics:
    """Basic sliding window operation tests."""

    def test_emits_window_after_200_frames(self):
        """Push 200 frames → expect 1 window, shape (200, 64)."""
        sw = SlidingWindow(n_subcarriers=64, window_size=200, step_size=100)
        windows = []
        for i in range(200):
            frame = make_frame([float(i)] * 64)
            w = sw.push(frame)
            if w is not None:
                windows.append(w)

        assert len(windows) == 1
        assert windows[0].shape == (200, 64)

    def test_window_content_matches_input(self):
        """Window amplitudes match the frames that were pushed."""
        sw = SlidingWindow(n_subcarriers=64, window_size=200, step_size=100)
        for i in range(200):
            frame = make_frame([float(i)] * 64)
            w = sw.push(frame)
            if w is not None:
                # Last row should be frame 199 (value 199.0)
                assert w[-1, 0] == pytest.approx(199.0)
                # First row should be frame 0 (value 0.0)
                assert w[0, 0] == pytest.approx(0.0)

    def test_300_frames_emits_two_windows(self):
        """Push 300 frames → 2 windows at frames 200 and 300."""
        sw = SlidingWindow(n_subcarriers=64, window_size=200, step_size=100)
        windows = []
        for i in range(300):
            frame = make_frame([float(i)] * 64)
            w = sw.push(frame)
            if w is not None:
                windows.append(w)

        assert len(windows) == 2
        # First window at 200, second at 300

    def test_400_frames_emits_three_windows(self):
        """Push 400 frames → 3 windows (at 200, 300, 400)."""
        sw = SlidingWindow(n_subcarriers=64, window_size=200, step_size=100)
        windows = []
        for i in range(400):
            frame = make_frame([float(i)] * 64)
            w = sw.push(frame)
            if w is not None:
                windows.append(w)

        assert len(windows) == 3
        # First window: frames 0-199
        assert windows[0][0, 0] == pytest.approx(0.0)
        assert windows[0][-1, 0] == pytest.approx(199.0)
        # Second window: frames 100-299 (slid by step_size=100)
        assert windows[1][0, 0] == pytest.approx(100.0)
        assert windows[1][-1, 0] == pytest.approx(299.0)
        # Third window: frames 200-399
        assert windows[2][0, 0] == pytest.approx(200.0)
        assert windows[2][-1, 0] == pytest.approx(399.0)

    def test_is_full_after_window_size(self):
        """is_full() returns True after window_size frames."""
        sw = SlidingWindow(n_subcarriers=64, window_size=200, step_size=100)
        assert not sw.is_full()
        for i in range(200):
            sw.push(make_frame([float(i)] * 64))
        assert sw.is_full()

    def test_reset_clears_state(self):
        """reset() clears buffer and counters."""
        sw = SlidingWindow(n_subcarriers=64, window_size=200, step_size=100)
        for i in range(200):
            sw.push(make_frame([float(i)] * 64))
        assert sw.is_full()
        sw.reset()
        assert not sw.is_full()
        # Next push should not emit
        w = sw.push(make_frame([1.0] * 64))
        assert w is None


class TestSlidingWindowEdgeCases:
    """Edge case tests."""

    def test_wrong_amplitude_length_logs_warning(self):
        """Frame with wrong n_subcarriers logs warning and returns None."""
        sw = SlidingWindow(n_subcarriers=64, window_size=10, step_size=5)
        frame = make_frame([1.0] * 10, node_id=1)  # 10 instead of 64
        w = sw.push(frame)
        assert w is None

    def test_list_amplitudes_converted(self):
        """Frame with list amplitudes is converted to array."""
        sw = SlidingWindow(n_subcarriers=3, window_size=5, step_size=2)
        frame = CSIFrame(
            node_id=1,
            sequence=0,
            n_subcarriers=3,
            amplitudes=[1.0, 2.0, 3.0],
            phases=[0.0, 0.0, 0.0],
        )
        for _ in range(5):
            w = sw.push(frame)
        # Should emit after 5 frames
        assert w is not None
        assert w.shape == (5, 3)
