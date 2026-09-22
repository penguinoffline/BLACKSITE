# Changelog

All notable BLACKSITE release changes will be recorded here.

## [1.0.0] - 2026-09-23

### Added
- Offline, replay signal analysis workstation.
- CSV and uncompressed PCM WAV input with requirements.
- Sample rate independent 1s short and 4s long FFT pipeline.
- Persistent track IDs and lifecycle handling.
- LOST track reacquisition and termination behavior.
- Multi-resolution refined frequency analysis with long FFT.
- INDIVIDUAL / BLENDED / UNCERTAIN spectral states.
- Strength, SNR, bandwidth, drift, trend, stability, and confidence metrics.
- Rolling waveform, spectrum, spectrogram, registry, telemetry, and history panels.
- Clickable and scrollable track selection, pause/resume, restart, display frequency control, and FINISHED state.
- Summary and history CSV exports.
- 8, 16, 24, and 32-bit PCM WAV support and multichannel to mono conversion.
- Incremental buffer processing and bounded display for improved long run performance.
- Automated testing, stress testing, real data checks, and a one hour GUI soak test.
- Improved startup loading performance for very large CSV files.
- Packaged macOS and Windows applications.
- MIT License.

### Known limitations
- No physical live acquisition in v1.0 yet.
- Frequency based tracking does not guarantee track identity through difficult source crossings.
- DC (0Hz) endpoint is a documented edge case due to algorithm design.
- Detection and confidence thresholds are engineering heuristics rather than calibrated statistical probabilities.
- CSV timestamps must be approximately uniformly sampled.
- Dense 192kHz inputs can produce heavy CPU and UI lag.
