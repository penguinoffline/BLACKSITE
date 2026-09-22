# BLACKSITE v1.0

**Persistent spectral tracking and signal-analysis workstation**

**Created by:** penguinoffline

>> Status: **v1.0 release candidate. Source engineering and source testing are complete. Packaging and final release checks remain.**

![BLACKSITE v1.0 dashboard](docs/screenshots/dashboard_v1.png)

Hiya! I built BLACKSITE to be a Python signal analysis and persistent spectral tracking workstation. v1.0 is intentionally an **offline/replay system** by design: it loads prerecorded CSV or WAV data, replays it progressively like a live source, detects peaks, maintains track identity through time, refines frequency structure, calculates signal metrics, and then presents everything in one operator dashboard.

The part I worked on the most is tracking. BLACKSITE is not just detecting **peaks in an FFT frame**. It tries to present an idea of **if the same signal was seen before, what has changed, did it disappear, and did it come back**

## What v1.0 does

- simulated live replay from prerecorded data
- short window FFT for rough detection and longer window for frequency refinement
- persistent track IDs
- **CANDIDATE -> ACTIVE -> COASTING -> LOST -> TERMINATED** lifecycle handling
- LOST track reacquisition before termination
- refined spectral states including **INDIVIDUAL**, **BLENDED**, and **UNCERTAIN**
- signal strength, SNR, bandwidth, frequency drift, strength trend, stability, and confidence metrics
- rolling waveform, spectrum, spectrogram, track registry, telemetry, and history panels
- Clickable and scrollable track selection, pause/resume, restart, configurable display-frequency control, and end of input state
- summary and track history CSV export
- CSV and uncompressed PCM WAV input with requirements
- incremental processing and bounded display rendering for performance

## Core pipeline

```text
INPUT
  -> rolling replay buffer
  -> short FFT + long FFT
  -> peak detection
  -> persistent rough frequency tracking
  -> lifecycle handling
  -> frequency refinement
  -> persistency + spectral state analysis
  -> track histories + signal metrics
  -> dashboard + CSV export
```

A more detailed architecture description is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Analysis time

v1.0 defines analysis time in seconds so sample sizes scale with the input sample rate:

| Stage | Duration |
|---|---:|
| Short analysis window | 1.0s |
| Long refinement window | 4.0s |
| Hop | 0.5s |
| Rolling buffer | 5.0s |
| Main GUI update timer | 500ms |

For example, at 48 kHz the short FFT uses 48,000 samples, the long FFT uses 192,000 samples, and the hop is 24,000 samples.

## Supported input

### CSV

BLACKSITE expects exactly one recognized time column and one recognized signal column. It accepts comma, semicolon, or tab delimiters. Time may be specified in seconds, milliseconds, microseconds, or nanoseconds through the column header (unitless recognized time columns are treated as seconds)

CSV data must contain finite numeric values, strictly increasing timestamps, approximately uniform spacing, and at least one second of data. v1.0 currently rejects timestamp spacing that differs by more than approximately 1% from the median spacing.

### WAV

v1.0 supports **uncompressed PCM WAV** with:

- 8-bit PCM
- 16-bit PCM
- 24-bit PCM
- 32-bit PCM
- mono or multichannel input

Multichannel WAV input is averaged to mono for analysis. Input must also be at least one second long.

See [`docs/INPUT_REQUIREMENTS.md`](docs/INPUT_REQUIREMENTS.md) for the full list of requirements.

## Running from source

BLACKSITE v1.0 has been developed and tested with Python 3.13.5 on macOS. Dependencies to install:

```bash
python3 -m pip install -r requirements.txt
```

I used Matplotlib's Qt compatibility layer, so a supported Qt Python binding is also required. BLACKSITE uses Matplotlib with PyQt5 as the Qt interface backend.

Run:

```bash
python3 BLACKSITE_v1.0.py
```

The launcher lets you select a supported CSV or WAV file and opens the dashboard after validation.

## Dashboard controls

- **BROWSE / LAUNCH** — select and load an input file
- **PAUSE / RESUME** — stop or continue replay
- **RESTART** — restart analysis from the beginning of the recording
- **DISPLAY Hz** — change the visible frequency range on graphs without changing the measurement data
- **Track Registry** — scroll through accepted tracks and click a track to inspect its telemetry and history
- **EXPORT** — write paired summary and history CSV output at the time of export

At end of input, BLACKSITE enters **FINISHED** while keeping the final analysis visible.

## Track lifecycle

A new detection begins as **CANDIDATE**. Repeated detection turns it to **ACTIVE**. Short gaps move an active track into **COASTING**; longer absence moves it to **LOST**. A signal can reacquire the same ID before the LOST timeout expires. After timeout, the track becomes **TERMINATED**.

The current association method is deliberately simple and frequency-dominant. Difficult source crossings are a known limitation and are planned for a later tracking version rather than being hidden behind increasingly fragile v1.0 heuristics.

## Metrics

BLACKSITE currently reports or stores:

- rough frequency
- refined frequency / spectral state
- strength
- SNR
- bandwidth
- frequency drift
- strength trend
- frequency standard deviation
- strength standard deviation
- lifecycle history
- confidence / quality score

The current confidence value is an **engineering quality score, not a calibrated probability that a track is real**. SNR is currently a **linear magnitude ratio**, not dB.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full metric and state definitions.

## Verification and validation

I did not want v1.0 to be a program that only worked on one screenshot.

Current validation evidence includes:

- automated non-GUI core V&V
- deterministic DSP and tracker regression tests
- separation and drift characterization
- dedicated loader regression inputs
- measured saxophone audio, human motion accelerometer data, and machinery vibration data
- GUI/manual qualification
- high sample rate stress cases
- a full one-hour GUI soak test

Full scope is documented in [`docs/VALIDATION.md`](docs/VALIDATION.md). 

The test suite is under [`tests/`](tests/).

## Performance

BLACKSITE now reduces waveform and spectrogram display data before rendering and avoids reprocessing old rolling window detections. Heavy GUI work is split across deferred one shot Qt timers so the main update callback can return control to the event loop quickly.

48kHz normal use was smooth under the tested workloads. Sparse 96kHz cases were also smooth in testing. Sparse 192kHz input was usable, but dense signals with many simultaneous frequencies at 192kHz will significantly increase CPU use and UI lag.

Large plain text CSV files also have a startup cost. The one hour 3.6 million row soak CSV took roughly 10 seconds to load in the development environment. This is a startup limitation, not the old progressive runtime slowdown.

## Known limitations

v1.0's important limitations include:

- prerecorded replay only, so no physical live acquisition yet
- frequency based association does not guarantee physical identity through difficult crossings
- the detector uses a median + 3 standard deviation threshold, which can become too strict in very dense spectra
- DC (0Hz) is an endpoint edge case for the current local-maximum detector
- confidence thresholds are heuristic and not physically calibrated
- the frequency stability part of confidence currently uses an absolute 1 Hz scale
- CSV input assumes a nearly uniform timebase and does not resample irregular data
- multichannel WAV data is averaged to mono
- generic loader errors do not yet tell the user the exact validation rule that failed
- very dense high sample rate cases can stress the GUI
- short recordings may not contain enough data for the 4 second refinement window

See [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) for more detail.

## Example data

[`examples/three_tone_demo.csv`](examples/three_tone_demo.csv) is a small synthetic input included only to make first run testing easy. It was generated specifically for this repository.

## Repository layout

```text
BLACKSITE/
├── BLACKSITE_v1.0.py
├── README.md
├── LICENSE
├── CHANGELOG.md
├── requirements.txt
├── .gitignore
├── docs/
│   ├── ARCHITECTURE.md
│   ├── INPUT_REQUIREMENTS.md
│   ├── VALIDATION.md
│   └── KNOWN_LIMITATIONS.md
├── tests/
│   ├── README.md
│   └── test_blacksite_v1_validation_rev4.py
└── examples/
    ├── README.md
    └── three_tone_demo.csv
```

v1.0 intentionally remains mostly a single Python source file. Modularization is planned to begin gradually in v1.1+.

## Roadmap

The long term goal is for BLACKSITE to become a **portable autonomous multi-modal sensing platform** that can detect, track, characterize, and eventually localize physical and RF signal sources, combine measurements from multiple sensors, and decide what measurement or movement should happen next.

The immediate roadmap moves through real live acquisition, embedded sensing, stronger quantitative tracking, actuated sensing, distributed nodes, physical calibration, signal cleaning, diagnostics, AI-assisted classification, mobile autonomy, SDR/RF sensing, direction finding, localization, and eventually multi-sensor autonomous investigation.

## Release status

The Python source has completed the current cleanup and regression cycle. Before `v1.0.0` is published, the remaining release gates are:

1. pin the final runtime and build dependency versions;
2. build and test the macOS application;
3. build and test the Windows executable;
4. add the chosen license;
5. update this README from "release candidate" to "released";
6. tag `v1.0.0` and attach the tested binaries.

## License

**Not selected yet.** A license must be chosen before the public release. I am intentionally not putting a random license on the project before deciding what rights I want to grant.
