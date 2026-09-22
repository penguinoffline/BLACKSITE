# BLACKSITE v1.0 Input Requirements

## CSV

BLACKSITE v1.0 accepts delimited text files using comma, semicolon, or tab separators.

### Required structure

The file must contain:

- one recognized time column
- one recognized signal or value column
- finite numeric data
- the same number of time and signal values
- strictly increasing timestamps
- approximately uniform sample spacing
- at least one second of data

### Time units

Time unit text may be supplied in parentheses or square brackets in the header.

Supported units:

- seconds: `s`, `sec`, `secs`, `second`, `seconds`
- milliseconds: `ms`, `millisecond`, `milliseconds`
- microseconds: `us`, `µs`, `microsecond`, `microseconds`
- nanoseconds: `ns`, `nanosecond`, `nanoseconds`

A recognized time column with no unit is treated as seconds.

### Timestamp rule

Sampling rate is estimated from the reciprocal of the median timestamp spacing.

v1.0 rejects the file if any timestamp step differs from the median step by more than approximately ±1%. The FFT path assumes uniformly sampled data, so irregular CSV timestamps are rejected instead of being resampled.

### Recognized column names

The loader recognizes several variants. Examples include:

Time:
`time`, `timestamp`, `t`, `time_s`, `elapsed_time`, `sample_time`, `relative_time`

Signal:
`signal`, `amplitude`, `value`, `sample`, `measurement`, `reading`, `sensor_value`, `channel_1`, `ch1`, `input`

The loader requires exactly one recognized time column and exactly one recognized signal column.

## WAV

BLACKSITE v1.0 accepts standard uncompressed PCM WAV files.

Supported sample widths:

- 8-bit unsigned PCM
- 16-bit signed little-endian PCM
- 24-bit signed little-endian PCM
- 32-bit signed little-endian PCM

24-bit PCM is reconstructed manually (see note inside the source code) because NumPy has no native signed 24-bit integer dtype.

### Channels

Mono and multichannel files are accepted. Multichannel data is averaged across channels into a single signal.

### Duration

The WAV must contain at least one second of audio or signal data.

## Not supported in v1.0 yet

- compressed WAV codecs
- arbitrary binary sensor formats
- MP3/AAC/etc
- irregular CSV sampling with automatic resampling
- multiple independent signal columns in one run
- channel preserving multichannel analysis
