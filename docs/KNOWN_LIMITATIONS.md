# BLACKSITE v1.0 Known Limitations

These are documented limitations of v1.0, not hidden defects.

## 1. Offline and replay only

v1.0 loads prerecorded CSV and WAV data and replays it progressively. It does not yet acquire a physical live stream. Real live acquisition begins in v1.1.

## 2. Frequency based track association

The current tracker uses relatively simple one to one association based mainly on rough frequency proximity between time frames. It works well for the tested stationary and drifting cases but does not guarantee physical identity when sources cross, merge, split, or change in complicated ways.

## 3. Standard deviation based threshold calculation

Peak detection currently uses approximately:

`median(magnitude) + 3 * standard_deviation(magnitude)`

The median is robust to isolated peaks, but the standard deviation can increase when a spectrum contains many strong frequencies. This can raise the threshold and hide weaker components.

## 4. DC 0Hz endpoint detector edge case

The local maximum detector scans bins left and right of the peak. DC is therefore not handled like a normal local maximum. The expected V&V fail case is for this limitation.

## 5. Confidence is heuristic

The confidence score is a quality score, not a probability that a signal or track is real.

The current score combines SNR, frequency stability, bandwidth, strength stability, and lifecycle status with fixed thresholds and weights. Those values have not been calibrated against a physical dataset.

## 6. Absolute 1Hz frequency stability scale

The frequency stability contribution to confidence currently reaches zero at approximately 1Hz frequency standard deviation.

Because the short analysis window is one second, this corresponds approximately to one short FFT bin. It is still an absolute frequency scale rather than a relative stability model, so its meaning can differ between low and high frequencies.

## 7. SNR is linear, not dB

Current SNR uses the tracked FFT bin magnitude relative to a local noise median. It is a linear magnitude ratio. Very clean synthetic tones may therefore report extremely large values.

The current SNR should not be presented as a calibrated RF or audio measurement in dB.

## 8. CSV timestamps must be nearly uniform

CSV timestamps must be strictly increasing and each interval must remain within approximately 1% of the median interval.

This is conservative because the normal FFT path assumes uniformly sampled data. v1.0 does not automatically resample irregular logs onto a uniform grid.

## 9. Generic input errors

Many loader validation failures currently show the same message: invalid or unsupported file. The program does not yet tell the user whether the problem was a bad header, non-finite sample, timestamp order, unsupported WAV encoding, etc.

## 10. Multichannel WAV is mixed to mono

When a WAV contains multiple channels, v1.0 averages the channels to one analysis signal. Channel specific and spatial information is discarded.

## 11. Short recording refinement

The responsive short FFT needs one second of data, while the long refinement stage needs four seconds. A recording can therefore be valid for basic tracking but too short to produce full long FFT refinement.

## 12. Dense high-rate performance

Sparse 192kHz data is usable in testing, but dense or polyphonic input (such as real songs) sampled at 192kHz can create many tracks and increase CPU and UI lag substantially.

No hard maximum track cap exists yet.

## 13. Large CSV startup time

The one hour soak CSV (approximately 3.6 million rows) took roughly 10 seconds to load after the startup loading optimization.

Runtime after loading remained stable, so this is a startup cost rather than a progressive runtime slowdown.

## 14. No universal sensor calibration

BLACKSITE v1.0 does not include a universal sensor calibration layer.

Frequency and bandwidth are reported in Hz. SNR is a linear magnitude ratio.

The physical meaning and units of signal strength depend on the sensor, scaling, gain, and acquisition chain used to produce the input data.
