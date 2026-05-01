# Phase 3: Signal Processing - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Clean raw CSI and extract features for presence detection. For Activity Recognition, minimal preprocessing (amplitude + scaler) is sufficient per Kang et al. 2025 source code analysis.

**Phase boundary:**
- IN: Structured raw CSI frames (from Phase 2 asyncio Queue)
- OUT: Clean feature vectors per 4-second window ready for Phase 4 (presence detection) and Phase 5 (HAR dataset collection)

</domain>

<decisions>
## Implementation Decisions

### Module Organization
- **D-11:** Separate `processor/` package, in-process asyncio coroutine, multi-purpose (CLI for offline testing + importable for online)
  - Processor runs as an asyncio task in the same event loop as the aggregator (same process)
  - Reads frames from D-06 asyncio.Queue (fed by CsiUdpServer)
  - Has standalone `__main__.py` CLI for offline `.npy` file testing
  - Package structure mirrors aggregator (`processor/__init__.py`, `processor/main.py`, etc.)

### Config & Orchestration
- **D-12:** Config passed from Aggregator ("nhạc trưởng")
  - Aggregator constructs config dict (window size, overlap, filter params, node list) and passes to processor on startup
  - Processor accepts config dict as constructor argument — no standalone config file or env var parsing in production
  - Defaults: 4-second window, 50% overlap (2s step), Hampel window 7 samples, MAD threshold 3.0

### Output Handoff to Phase 4
- **D-13:** Processor pushes feature vectors into a second `asyncio.Queue`
  - Phase 4 consumer pulls from this Queue (decoupled producer/consumer pattern)
  - Maintains same event loop, no serialization overhead
  - Also supports offline mode: processor CLI writes feature vectors to `.npy` or `.csv`

### Signal Processing Pipeline
- **D-14:** Both amplitude and phase processing
  - Amplitude extracted from I/Q via `sqrt(I^2+Q^2)` (already done in parser, reuse)
  - Phase extracted via `atan2(Q,I)`, then unwrap + linear detrend for presence detection breathing sensitivity
  - For HAR dataset (Phase 5): amplitude-only is sufficient per Kang et al. 2025 and ADR-014 analysis
  - Dual-track: amplitude-only vector for HAR, amplitude+phase vector for presence

### Outlier Filtering
- **D-15:** Custom Hampel filter implementation (~10-15 lines per subcarrier)
  - Running median ± scaled MAD over a sliding window
  - Applied per subcarrier independently on amplitude stream
  - No scipy dependency — pure numpy, lightweight
  - Window size and threshold configurable via D-12 config

### Feature Vector Format
- **D-16:** Dict output with metadata + flat feature array
  - Outer dict: `{"node_id": int, "window_start_ms": int, "window_end_ms": int, "features": np.ndarray}`
  - Inner `features` array: flat numpy array of shape `(n_features,)` for direct model consumption
  - Feature list per window:
    - `mean_amp[64]` — mean amplitude per subcarrier
    - `var_amp[64]` — variance per subcarrier
    - `motion_energy` — band power 0.5-3 Hz (aggregate across subcarriers)
    - `breathing_band` — band power 0.1-0.5 Hz (aggregate across subcarriers)
  - Total feature count: ~130 features (64 + 64 + 1 + 1)

### Windowing Strategy
- **D-17:** Real-time streaming primary, offline `.npy` replay secondary
  - Real-time: 4-second sliding window with 50% overlap (2s step) from live Queue
  - Offline: CLI mode reads `.npy` files from `data/raw/` and runs identical pipeline
  - Windowing implemented as a stateful sliding buffer in processor task
  - When window fills (200 frames @ 50 Hz), emit feature vector and slide by 100 frames

### Multi-Node Processing
- **D-18:** Per-node independent processing, decision-level fusion deferred to Phase 4
  - Each node gets its own processor instance or internal per-node state
  - Output: separate feature vector per node every 2 seconds (with 4s window)
  - Phase 4 fuses decisions (e.g., OR logic: presence if any node detects)
  - No cross-node signal-level fusion (avoids clock drift issues per ADR-012)

### the agent's Discretion
- Exact Hampel window size and MAD threshold (within 5-15 sample window, 2.5-4.0 threshold range)
- Phase unwrapping algorithm details (numpy.unwrap vs custom)
- Band power computation method (FFT vs Welch vs simple sum of squares)
- Feature normalization (z-score, min-max, or none) before output
- Whether to cache intermediate amplitude/phase arrays for reuse

</decisions>

<specifics>
## Specific Ideas

- "Giống như hình dáng của sóng (amplitude) và vị trí chính xác (phase)" — amplitude for HAR, phase for presence breathing sensitivity
- "NgườI bảo vệ bắt tín hiệu nhảy vọt" — Hampel filter as robust outlier guard
- "Hộp quà" metadata + "Dãy số" feature array — structured dict output for debuggability
- Dashboard (Phase 6) needs smooth updates → 50% overlap gives 2s refresh rate
- Keep offline CLI for tuning without walking back and forth to sensors

</specifics>

<canonical_refs>
## Canonical References

### Signal processing algorithms
- `llm-wiki/raw/RuView/docs/adr/ADR-014-sota-signal-processing.md` — Hampel, phase unwrap, spectrogram, subcarrier selection algorithms
- `llm-wiki/raw/wallhack1.8k/datasets.py` — amplitude extraction pattern for Phase 5
- `llm-wiki/raw/prunedAttentionGRU/ARIL/aril.py` — 52/64-subcarrier input format match

### Phase 2 input contract
- `aggregator/frame.py` — CSIFrame dataclass (fields, validation)
- `aggregator/parser.py` — ADR-018 parser (amplitude/phase extraction, D-09)
- `aggregator/buffer.py` — NodeBuffer ring buffer (D-07)
- `aggregator/main.py` — asyncio event loop, Queue wiring (D-06)
- `.planning/phases/02-udp-aggregator/02-CONTEXT.md` — D-06, D-07, D-10 decisions

### Requirements
- `.planning/REQUIREMENTS.md` — SIG-03..SIG-06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aggregator/parser.py` — Amplitude and phase extraction already implemented; processor should import these values directly from CSIFrame rather than recompute
- `aggregator/frame.py` — CSIFrame dataclass with `amplitudes`, `phases`, `n_subcarriers`, `node_id` fields
- `aggregator/buffer.py` — Per-node deque ring buffer pattern; processor can adapt for window buffering
- `scripts/view_csi.py` — matplotlib heatmap visualization of `.npy` files (useful for offline verification)

### Established Patterns
- Binary frame → dataclass → Queue → consumer pipeline (established in Phase 2)
- Per-node state keyed by `node_id` (dict pattern from server.py)
- NumPy `.npy` persistence for raw data (NpyWriter in persistence.py)
- Logging via Python standard `logging` module

### Integration Points
- Phase 2 → Phase 3: `asyncio.Queue` (D-06) feeds raw CSI frames into processor
- Phase 3 → Phase 4: Second `asyncio.Queue` feeds feature vectors into presence detector
- Phase 3 → Phase 5: `.npy` amplitude matrices saved to disk for offline HAR training
- Phase 3 → Phase 6: Feature dict metadata (node_id, timestamps) usable by dashboard health display

</code_context>

<deferred>
## Deferred Ideas

- Subcarrier sensitivity selection (SpotFi-style variance ratio) — out of scope for v1, noted in ADR-014 §5
- CSI spectrogram generation for CNN input — Phase 5 uses raw amplitude + StandardScaler, no spectrogram needed per Kang et al.
- Cross-node signal-level fusion — rejected due to clock drift (~20-50 ppm), per ADR-012
- Fresnel zone breathing model — requires TX-RX geometry input, deferred to v2
- Doppler velocity profile (BVP) — needs >1s temporal history at 100+ Hz, deferred

</deferred>

---

*Phase: 03-signal-processing*
*Context gathered: 2026-05-01*
