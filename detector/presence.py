"""Per-node presence detection with adaptive baseline and hysteresis.

Implements a state machine that learns the empty-room noise floor and
detects occupancy when a weighted combination of motion_energy and
breathing_band deviates from the learned baseline.

Design decisions:
  D-21: Adaptive baseline via EMA of combined score (when room is empty)
  D-22: Combined score = 0.7 * motion + 0.3 * breathing
  D-24: Enter threshold 2.5 sigma, exit threshold 1.5 sigma (hysteresis gap)
  D-25: 3 consecutive frames to confirm OCCUPIED, 5 to confirm EMPTY
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger("detector.presence")


class DetectionState(Enum):
    """Hysteresis state machine states for presence detection.

    The intermediate CONFIRMING_* states prevent rapid flapping
    by requiring consecutive frames before committing to a change.
    """

    EMPTY = "empty"
    CONFIRMING_OCCUPIED = "confirming_occupied"
    OCCUPIED = "occupied"
    CONFIRMING_EMPTY = "confirming_empty"


class PresenceDetector:
    """Per-node presence detector with adaptive baseline and hysteresis.

    Learns the empty-room noise floor automatically and detects
    occupancy when the combined motion+breathing score deviates
    beyond configurable sigma thresholds.  Hysteresis prevents
    rapid state flipping at detection boundaries.

    Feature vector layout (from processor/main.py)::

        indices [0:N]      → mean_amp per subcarrier
        indices [N:2*N]    → var_amp per subcarrier
        index  [2*N]       → motion_energy  (scalar)
        index  [2*N + 1]   → breathing_band (scalar)

    where *N* is the number of subcarriers (typically 64).

    Parameters:
        node_id:
            Unique identifier for the CSI node this detector monitors.
        enter_threshold_sigma:
            Sigma above baseline to begin entering OCCUPIED (D-24: 2.5).
        exit_threshold_sigma:
            Sigma below baseline to begin exiting OCCUPIED (D-24: 1.5).
        enter_frames:
            Consecutive above-threshold frames required to confirm
            OCCUPIED (D-25: 2 for 10 fps ESP32-S3).
        exit_frames:
            Consecutive below-threshold frames required to confirm
            EMPTY (D-25: 3 for 10 fps ESP32-S3).
        baseline_alpha:
            EMA smoothing factor for baseline mean and std updates.
        min_baseline_frames:
            Minimum frames before baseline is considered valid.
        baseline_skip_threshold_sigma:
            Frames exceeding mean + N*std during initial build are skipped
            to avoid motion contaminating the baseline (default 2.0).
        baseline_skip_threshold_sigma:
            During initial baseline build, frames with score > mean + N*std
            are rejected to prevent motion from contaminating the noise-floor
            estimate (default 2.0).
    """

    def __init__(
        self,
        node_id: int,
        enter_threshold_sigma: float = 2.5,
        exit_threshold_sigma: float = 1.5,
        enter_frames: int = 2,
        exit_frames: int = 3,
        baseline_alpha: float = 0.15,
        min_baseline_frames: int = 6,
        baseline_skip_threshold_sigma: float = 2.0,
    ) -> None:
        # ---- Configuration ----
        self.node_id = node_id
        self.enter_threshold_sigma = enter_threshold_sigma
        self.exit_threshold_sigma = exit_threshold_sigma
        self.enter_frames = enter_frames
        self.exit_frames = exit_frames
        self.baseline_alpha = baseline_alpha
        self.min_baseline_frames = min_baseline_frames
        self.baseline_skip_threshold_sigma = baseline_skip_threshold_sigma

        # ---- Adaptive baseline (D-21) ----
        self._baseline_mean: float = 0.0
        self._baseline_std: float = 1.0   # non-zero to avoid div-by-zero
        self._frame_count: int = 0
        self._baseline_ready: bool = False
        self._m2: float = 0.0             # Welford M2 accumulator

        # ---- State machine (D-24, D-25) ----
        self._state: DetectionState = DetectionState.EMPTY
        self._trigger_counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_baseline_ready(self) -> bool:
        """Return ``True`` once the baseline has been built from
        enough empty-room frames."""
        return self._baseline_ready

    @property
    def state(self) -> DetectionState:
        """Current state machine state."""
        return self._state

    def reset_baseline(self) -> None:
        """Force baseline re-learning.

        Resets all accumulated statistics, the readiness flag, and
        the state machine back to EMPTY.  Useful for testing,
        re-calibration, or environment changes.
        """
        logger.debug(
            "Node %d: baseline reset requested",
            self.node_id,
        )
        self._baseline_mean = 0.0
        self._baseline_std = 1.0
        self._frame_count = 0
        self._baseline_ready = False
        self._m2 = 0.0
        self._state = DetectionState.EMPTY
        self._trigger_counter = 0

    def update(self, feature_vector: np.ndarray) -> Optional[dict]:
        """Process a single feature vector and advance the state machine.

        Parses the flat feature array to extract motion energy and
        breathing band, computes a weighted combined score, updates
        the adaptive baseline, and runs the hysteresis state machine.

        Args:
            feature_vector: 1-D ``float64`` array of shape
                ``(2*N + 2,)`` where *N* is the number of subcarriers.
                Motion energy sits at index ``2*N``, breathing band
                at ``2*N + 1``.

        Returns:
            A ``dict`` on state transitions with keys ``node_id``,
            ``status``, ``confidence``, ``trigger_feature``, ``sigma``.
            Returns ``None`` when no transition occurred or when the
            input is invalid (NaN / Inf / malformed shape).
        """
        # ---- Input validation (threat T-04-01) ----
        fv = np.asarray(feature_vector, dtype=np.float64)

        if np.any(np.isnan(fv)) or np.any(np.isinf(fv)):
            logger.warning(
                "Node %d: NaN/Inf in feature vector, discarding frame",
                self.node_id,
            )
            return None

        if fv.ndim != 1:
            logger.warning(
                "Node %d: expected 1-D feature vector, got shape %s",
                self.node_id,
                fv.shape,
            )
            return None

        N = (len(fv) - 2) // 2
        if N < 1 or len(fv) != 2 * N + 2:
            logger.warning(
                "Node %d: malformed feature vector length %d "
                "(expected 2*N+2 with N>=1)",
                self.node_id,
                len(fv),
            )
            return None

        # ---- Parse motion and breathing from flat array ----
        motion = float(fv[2 * N])
        breathing = float(fv[2 * N + 1])

        # Combined score (D-22): 0.7 motion + 0.3 breathing
        score = 0.7 * motion + 0.3 * breathing

        # ---- Initial baseline build phase ----
        if not self._baseline_ready:
            accepted = self._build_initial_baseline(score)
            if accepted and self._frame_count >= self.min_baseline_frames:
                self._baseline_ready = True
                logger.info(
                    "🎯 Node %d: baseline ready (mean=%.4f, std=%.4f, frames=%d)",
                    self.node_id,
                    self._baseline_mean,
                    self._baseline_std,
                    self._frame_count,
                )
            return None

        self._frame_count += 1

        # ---- Deviation from baseline ----
        sigma = (score - self._baseline_mean) / max(self._baseline_std, 1e-6)
        logger.debug(
            "📊 Node %d: score=%.4f, mean=%.4f, std=%.4f, sigma=%.2f",
            self.node_id,
            score,
            self._baseline_mean,
            self._baseline_std,
            sigma,
        )

        # ---- Run hysteresis state machine ----
        previous_state = self._state
        self._advance_state(sigma)

        if self._state in (DetectionState.EMPTY, DetectionState.CONFIRMING_EMPTY):
            self._update_baseline(score)

        # ---- Emit result only on state transition ----
        if self._state != previous_state:
            logger.info(
                "🔄 Node %d: %s → %s (sigma=%.2f, score=%.2f)",
                self.node_id,
                previous_state.value,
                self._state.value,
                sigma,
                score,
            )
            return self._build_result(sigma)

        return None

    # ------------------------------------------------------------------
    # Internal: baseline
    # ------------------------------------------------------------------

    def _build_initial_baseline(self, score: float) -> bool:
        """Online mean/variance accumulation using Welford's algorithm.

        Used during the first *min_baseline_frames* to build a stable
        initial estimate before switching to EMA tracking.

        Frames that exceed ``mean + skip_threshold * std`` are rejected
        so that motion during startup does not contaminate the baseline.

        Returns:
            ``True`` if the frame was accepted into the baseline,
            ``False`` if it was skipped.
        """
        # Skip obvious motion after the very first frame
        if self._frame_count >= 1:
            threshold = (
                self._baseline_mean
                + self.baseline_skip_threshold_sigma * self._baseline_std
            )
            if score > threshold:
                logger.debug(
                    "Node %d: skip baseline frame %d "
                    "(score=%.2f > threshold=%.2f)",
                    self.node_id,
                    self._frame_count + 1,
                    score,
                    threshold,
                )
                return False

        self._frame_count += 1
        n = self._frame_count
        delta = score - self._baseline_mean
        self._baseline_mean += delta / n
        # Track variance via M2; store std dev in _baseline_std for
        # consistency with the rest of the class.
        if n == 1:
            self._m2 = 0.0
        else:
            self._m2 += delta * (score - self._baseline_mean)
        if n > 1:
            variance = self._m2 / (n - 1)
            self._baseline_std = float(np.sqrt(max(variance, 1e-12)))
        else:
            self._baseline_std = 1.0
        return True

    def _update_baseline(self, score: float) -> None:
        """Update baseline mean and std via exponential moving average.

        D-21: EMA is applied only when the detector believes the room
        is empty (state EMPTY or CONFIRMING_EMPTY), so occupancy
        signals do not contaminate the baseline.
        """
        alpha = self.baseline_alpha
        self._baseline_mean = (
            (1.0 - alpha) * self._baseline_mean + alpha * score
        )
        # Std is EMA of absolute deviation from the *new* mean
        self._baseline_std = (
            (1.0 - alpha) * self._baseline_std
            + alpha * abs(score - self._baseline_mean)
        )

    # ------------------------------------------------------------------
    # Internal: state machine
    # ------------------------------------------------------------------

    def _advance_state(self, sigma: float) -> None:
        """Execute one step of the hysteresis state machine (D-24, D-25).

        Transitions::

            EMPTY → CONFIRMING_OCCUPIED   on sigma > enter_threshold
            CONFIRMING_OCCUPIED → OCCUPIED  after enter_frames triggers
            CONFIRMING_OCCUPIED → EMPTY      on sigma drop (fast abort)
            OCCUPIED → CONFIRMING_EMPTY      on sigma < exit_threshold
            CONFIRMING_EMPTY → EMPTY          after exit_frames triggers
            CONFIRMING_EMPTY → OCCUPIED       on sigma spike (fast abort)
        """
        if self._state == DetectionState.EMPTY:
            if sigma > self.enter_threshold_sigma:
                self._state = DetectionState.CONFIRMING_OCCUPIED
                self._trigger_counter = 1
            else:
                self._trigger_counter = 0

        elif self._state == DetectionState.CONFIRMING_OCCUPIED:
            if sigma > self.enter_threshold_sigma:
                self._trigger_counter += 1
                if self._trigger_counter >= self.enter_frames:
                    self._state = DetectionState.OCCUPIED
                    self._trigger_counter = 0
            else:
                # Sigma dropped below enter threshold → abort confirmation
                self._state = DetectionState.EMPTY
                self._trigger_counter = 0

        elif self._state == DetectionState.OCCUPIED:
            if sigma < self.exit_threshold_sigma:
                self._state = DetectionState.CONFIRMING_EMPTY
                self._trigger_counter = 1
            else:
                self._trigger_counter = 0

        elif self._state == DetectionState.CONFIRMING_EMPTY:
            if sigma < self.exit_threshold_sigma:
                self._trigger_counter += 1
                if self._trigger_counter >= self.exit_frames:
                    self._state = DetectionState.EMPTY
                    self._trigger_counter = 0
            else:
                # Sigma rose above exit threshold → abort, back to OCCUPIED
                self._state = DetectionState.OCCUPIED
                self._trigger_counter = 0

    # ------------------------------------------------------------------
    # Internal: result construction
    # ------------------------------------------------------------------

    def _build_result(self, sigma: float) -> dict:
        """Assemble the transition result dict with computed confidence."""
        confidence = self._compute_confidence(sigma)
        if self._state in (
            DetectionState.EMPTY,
            DetectionState.CONFIRMING_EMPTY,
        ):
            status = "empty"
        else:
            status = "occupied"
        return {
            "node_id": self.node_id,
            "status": status,
            "confidence": confidence,
            "trigger_feature": "combined",
            "sigma": float(sigma),
        }

    @staticmethod
    def _compute_confidence(sigma: float) -> float:
        """Map absolute deviation sigma to a [0.0, 1.0] confidence.

        Uses a sigmoid scaled by 5.0::

            sigma =  0  → ~0.50
            sigma =  5  → ~0.73
            sigma = 10  → ~0.88
            sigma = 20  → ~0.98
        """
        raw = 1.0 / (1.0 + np.exp(-abs(sigma) / 5.0))
        # Clamp is technically unnecessary (sigmoid ∈ (0,1)),
        # but included for explicit contract adherence.
        return float(np.clip(raw, 0.0, 1.0))
