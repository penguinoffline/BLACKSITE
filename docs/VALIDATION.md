# BLACKSITE v1.0 Verification & Validation

## Please note that automated test suites and synthetic test inputs were created with AI assistance and manually reviewed. Real world tests used external datasets.

## Purpose

The goal of my v1.0 V&V work is not to claim that BLACKSITE is a calibrated scientific tool. The goal is to make sure the behavior is repeatable, known failure modes are documented, and that the program remains stable under longer and higher rate workloads.

## Current automated core suite

Current suite:

`tests/test_blacksite_v1_validation_rev4.py`

Latest verified result:

```text
113 passed
1 skipped
1 XFAIL (expected fail)
1 XPASS (unexpected pass)
0 failures
```

The `XFAIL` is a documented DC endpoint detector limitation. The crossing tone case currently has `XPASS` after multiple tests, but that is deliberately **not** treated as proof that identity is guaranteed for crossing sources.

The suite loads core functions directly and uses the non-GUI analysis path without needing to launch the Matplotlib and Qt interface.

With the optional performance test enabled, the suite completed with 114 passed, 1 XFAIL, 1 XPASS, and 0 failures.

Coverage includes:

- production source loading and core function
- CSV input and rejection behavior
- FFT frequency resolution and amplitude normalization
- peak detection
- SNR and bandwidth behavior
- rolling duplicate window suppression
- lifecycle transitions
- acceptance and promotion behavior
- LOST track reacquisition and timeout
- multi-tone tracking
- noise only behavior
- refined frequency analysis
- spectral state logic
- drift, trend, stability, and confidence
- changing frequency and changing amplitude cases
- CSV export
- repeatability
- runtime and performance
- documented known limitations

## Performance and behavior evidence

Earlier validation produced:

- **108 / 108** close frequency separation retained evidence for both frequencies under every test case;
- **18 / 18** drift stress cases maintained the intended one ID behavior under those test conditions;
- a previous core suite revision produced 112 passes with no unexpected failures plus one XFAIL and one XPASS.

These are controlled test results, not universal guarantees outside the tested conditions.

## More stress testing

A separate test suite completed:

**556 / 556 checks passed**.

It covered loader, randomized FFT frequency/phase/amplitude/sample rate cases, tracker and state behavior, incremental refinement, comparisons between incremental and rescan refinement, history, restart, export, and the integrity of the complete analysis chain.

This exploratory run is useful evidence but is kept separate from the smaller pytest suite for this release so the formal test suite remains understandable.

## Loader

A separate final loader test suite was run again after the late cleanup work and reported **all pass**. It covers valid and invalid CSV and WAV inputs, malformed or short inputs, PCM bits, and representative 48/96/192 kHz cases.

## Manual GUI

Manual GUI checks during v1.0 include:

- launcher smoothness
- valid and invalid input handling
- dashboard open or close behavior
- track selection
- registry scrolling
- GUI and export
- pause and resume
- restart
- display frequency slider
- resizing
- export while LIVE / PAUSED / FINISHED
- user friendly and repeated export naming
- FINISHED behavior

A final post cleanup GUI smoke test was also completed successfully on a 48 kHz 24-bit stereo WAV stress input.

## Real world data

BLACKSITE has also been tested using measured real world data rather than only synthetic signals.

The test data included:

- real saxophone audio
- wrist accelerometer data from a human activity recording
- machinery vibration recordings representing a good bearing, inner race fault, outer race fault, and ball fault

These runs were used to check loading, replay, FFT behavior, tracking, display stability, track selection, FINISHED behavior, and export behavior.

The bearing recordings were used as real vibration inputs but are not evidence that BLACKSITE v1.0 can diagnose bearing faults.

The bearing qualification recordings were approximately two seconds long. They therefore tested the short FFT and normal replay path but did not have the four seconds currently required for the full long FFT refinement.

These real data tests are behavioral qualification, not diagnostic validation.

Quantitative physical and machinery diagnostic validation is planned for later BLACKSITE versions, followed by a LLM assisted diagnostic system trained and evaluated using verified signal data

## One hour GUI soak

My soak signal contained roughly:

- 3,601,000 samples
- 1,000 Hz sampling
- about 3,601 seconds of data
- three intended tracks
- amplitude modulation
- a six second dropout
- a drifting and chirping component
- light noise

The GUI completed the full run without the previously observed progressive interaction slowdown returning due to re-analyzing the buffer every 0.5s.

Processing time during the run grew from roughly 8 ms per update around the 700-1,000s mark to roughly 16 ms per update near the end, which is still far below the 500ms GUI update budget.

After the startup loading optimization, the approximately 3.6 million row CSV took about 10 seconds to load.

## High-sample-rate behavior

The project has been exercised on 48kHz, 96kHz, and 192kHz cases.

- 48 kHz: normal use is smooth under tested workloads
- 96 kHz sparse cases: smooth in testing
- 192 kHz sparse cases: usable, with some additional but mild to moderate history and click lag
- 192 kHz dense or polyphonic cases: can become CPU and UI heavy as the number of tracks and display work grow substantially.

## What this validation does not prove

v1.0 has no detection probability, false alarm probability, calibrated confidence, or identity accuracy across all signal conditions.

Particularly, current V&V does not turn these into guarantees:

- ID preservation through crossing and changing sources
- detection of weak components in every dense spectrum
- calibrated probability of confidence
- correct physical unit for every sensor type
- accuracy on strongly irregular sampled data

## Development and validation environment

- Python 3.13.5
- NumPy 2.1.3
- Matplotlib 3.10.0
- PyQt5 5.15.10
- Qt 5.15.2
- pytest 8.3.4

## macOS packaging

The macOS application was packaged using:

- PyInstaller 6.22.3

The packaged macOS application has already completed manual testing.

Tested packaged behavior included:

- application launch and reopen
- CSV loading
- replay
- pause and resume
- restart
- dashboard operation
- track selection
- display frequency slider
- tracking through FINISHED
- export during replay
- export after FINISHED

The packaged application remained functional through the tested workflow.

## Windows packaging

The Windows application was built on a GitHub hosted Windows runner with:

- Python 3.13
- PyInstaller 6.22.3

The automated validation suite has also been tested on Windows:

`113 passed, 1 skipped, 1 xfailed, 1 xpassed in 5.52s`

The packaged Windows application also completed manual GUI testing.

Tested behavior included:

- application launch and reopen
- loading the included three tone example
- replay
- pause and resume
- restart
- dashboard
- track selection
- scrolling through the Track Registry
- display frequency slider
- tracking through FINISHED
- export during replay
- export after FINISHED

The packaged Windows application remained functional through the tests.

The Windows release is unsigned. Manual GUI testing was performed on the Windows application before release.

The packaged Windows application contains:

- `BLACKSITE.exe`
- the PyQt5 Windows platform plugin `qwindows.dll`

### Release hashes

`BLACKSITE_v1.0.py`

SHA-256:

`83d36afd12ad9146a46a8be3dde71f7328736bb2b8448acc37811b8a7015b434`

Final SHA-256 checksums for the macOS and Windows releases are published with the GitHub Release so that they correspond to the exact binaries distributed.
