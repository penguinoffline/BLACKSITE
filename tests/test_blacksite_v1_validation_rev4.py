"""
BLACKSITE v1.0 Core Verification & Validation Suite
===================================================

NOTE: This automated suite was created with AI assistance for convenience and
manually reviewed against the current BLACKSITE v1.0 production interfaces.

Purpose
-------
Release verification of BLACKSITE's non-GUI signal-processing core:
CSV ingestion, FFT and peak detection, SNR and bandwidth, tracking state machine,
refined-frequency separation, metrics, export integrity, and rolling behaviour.

Run
---
1. Put this file next to BLACKSITE_v1.0.py, OR set BLACKSITE_PATH.
2. Run:
       pytest -q test_blacksite_v1_validation.py
   More detail:
       pytest -vv test_blacksite_v1_validation.py
   Only release-gate tests:
       pytest -q -m "not xfail" test_blacksite_v1_validation.py

Design notes
------------
* All random tests use fixed seeds for repeatability.
* Synthetic integration tests use a 1 kHz fixture rate. At 1 kHz, BLACKSITE's
  5.0 s buffer, 1.0 s short FFT, 4.0 s long FFT, and 0.5 s hop correspond to
  5,000, 1,000, 4,000, and 500 samples respectively.
* Core functions are loaded directly from the production source AST. This avoids
  launching Qt and Matplotlib GUI code during automated DSP tests and allows the
  core suite to run on machines without Qt.
* Tests target intended behaviour, not merely current implementation. A failing
  requirement test is a useful defect signal, not something to weaken just to
  make the suite green.
"""

from __future__ import annotations

import ast
import copy
import csv
import math
import os
from pathlib import Path
import tempfile
import time as wall_time
from bisect import bisect_left, bisect_right

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Production source loader
# ---------------------------------------------------------------------------

REQUIRED_CORE_FUNCTIONS = {
    "system_input",
    "window_extract",
    "window_fft",
    "window_fft_high",
    "auto_threshold",
    "window_peak",
    "peak_detection",
    "frequency_refining",
    "track_indexing",
    "snr_bandwidth",
    "track_comparison",
    "refined_collection",
    "long_grouper",
    "persistency_analyzer",
    "same_window",
    "refined_comparison",
    "refined_decider_prep",
    "valley_analyzer",
    "valley_scoring",
    "refined_decider",
    "refined_display",
    "history_realtime",
    "frequency_drift",
    "strength_trend",
    "stability_analyzer",
    "confidence_score",
    "active_collection",
    "accepted_track",
    "export_track",
    "export_summary",
}

GUI_ONLY_FUNCTIONS = {"dashboard", "launcher", "plotting_spectrogram"}


def _find_blacksite_source() -> Path:
    env_path = os.environ.get("BLACKSITE_PATH")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"BLACKSITE_PATH does not exist: {path}")
        return path

    here = Path(__file__).resolve().parent
    candidates = sorted(
        [
            *here.glob("BLACKSITE*.py"),
            *here.glob("blacksite*.py"),
            *here.glob("BLACKSITE*.txt"),
            *here.glob("blacksite*.txt"),
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    candidates = [p for p in candidates if p.name != Path(__file__).name]
    if not candidates:
        raise FileNotFoundError(
            "Could not locate BLACKSITE source. Put this test next to BLACKSITE "
            "or set BLACKSITE_PATH=/full/path/to/BLACKSITE.py"
        )
    return candidates[0]


BLACKSITE_SOURCE = _find_blacksite_source()


def _load_core_namespace(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    function_nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name not in GUI_ONLY_FUNCTIONS
    ]

    namespace = {
        "np": np,
        "copy": copy,
        "csv": csv,
        "os": os,
        "bisect_left": bisect_left,
        "bisect_right": bisect_right,
    }
    module = ast.Module(body=function_nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, filename=str(path), mode="exec"), namespace)
    return namespace


BS = _load_core_namespace(BLACKSITE_SOURCE)


# ---------------------------------------------------------------------------
# Deterministic signal factory
# ---------------------------------------------------------------------------

FS = 1000.0
DT = 1.0 / FS
SHORT_WINDOW = 1000
LONG_WINDOW = 4000
HOP = 500
BUFFER = 5000


def timebase(duration_s: float, fs: float = FS) -> np.ndarray:
    return np.arange(0.0, duration_s, 1.0 / fs, dtype=float)


def tone(t: np.ndarray, frequency_hz: float, amplitude: float = 2.3, phase: float = 0.0) -> np.ndarray:
    return amplitude * np.sin(2.0 * np.pi * frequency_hz * t + phase)


def chirp_linear(t: np.ndarray, f_start: float, f_end: float, amplitude: float = 2.3) -> np.ndarray:
    duration = t[-1] - t[0] + DT
    k = (f_end - f_start) / duration
    phase = 2.0 * np.pi * (f_start * t + 0.5 * k * t**2)
    return amplitude * np.sin(phase)


def seeded_noise(n: int, sigma: float, seed: int = 12345) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, sigma, n)


# ---------------------------------------------------------------------------
# Rolling integration harness mirroring dashboard processing
# ---------------------------------------------------------------------------

class RollingHarness:
    """Headless reproduction of BLACKSITE's current rolling processing path."""

    def __init__(self, signal: np.ndarray, time: np.ndarray):
        self.signal = np.asarray(signal, dtype=float)
        self.time = np.asarray(time, dtype=float)
        self.live_index = 1000
        self.latest_processed_index = None

        self.completed = []
        self.lost = []
        self.terminated = []
        self.id_counter = 0

        # Persistent incremental state introduced by the performance refactor.
        self.track_history_archive = {}
        self.refined_history_archive = {}
        self.grouped_refined_archive = {}
        self.same_window_archive = {}

        self.display_summary = {}
        self.accepted_ids = []
        self.snapshots = []

    def _slice(self):
        start_sample = max(0, self.live_index - BUFFER)
        end_sample = min(self.live_index, len(self.signal))
        return (
            self.signal[start_sample:end_sample],
            self.time[start_sample:end_sample],
            start_sample,
        )

    def step_once(self):
        signal_range, time_range, start_sample = self._slice()

        windows, short_mid_time, short_window_index = BS["window_extract"](
            signal_range, time_range, start_sample, SHORT_WINDOW, HOP
        )
        short_magnitude, short_frequency, short_mid_time = BS["window_fft"](
            windows, short_mid_time, time_range
        )
        peak_magnitudes, peak_frequency, short_mid_time = BS["peak_detection"](
            short_magnitude, short_frequency, short_mid_time
        )

        if len(signal_range) >= LONG_WINDOW:
            long_magnitude, long_frequency, long_mid_time = BS["window_fft_high"](
                signal_range, time_range, start_sample, LONG_WINDOW, HOP
            )
            refined_results = BS["frequency_refining"](
                peak_frequency,
                short_frequency,
                short_mid_time,
                long_magnitude,
                long_frequency,
                long_mid_time,
            )
        else:
            long_magnitude, long_frequency, long_mid_time, refined_results = [], [], [], []

        indexed_windows = BS["track_indexing"](
            peak_magnitudes, peak_frequency, short_mid_time
        )
        indexed_windows = BS["snr_bandwidth"](
            indexed_windows, short_magnitude, short_frequency
        )

        new_indices = []
        new_windows = []
        new_times = []
        if self.latest_processed_index is None:
            for i in range(len(short_window_index)):
                new_indices.append(short_window_index[i])
                new_windows.append(indexed_windows[i])
                new_times.append(short_mid_time[i])
        else:
            for i in range(len(short_window_index)):
                if short_window_index[i] > self.latest_processed_index:
                    new_indices.append(short_window_index[i])
                    new_windows.append(indexed_windows[i])
                    new_times.append(short_mid_time[i])

        if new_indices:
            self.latest_processed_index = new_indices[-1]

        new_refined = [
            item
            for item in refined_results
            if item["short_fft_time"] in new_times
        ]

        window_count = len(self.completed)
        (
            self.completed,
            self.lost,
            self.terminated,
            self.id_counter,
        ) = BS["track_comparison"](
            new_windows,
            short_frequency,
            new_times,
            new_refined,
            self.completed,
            self.lost,
            self.terminated,
            self.id_counter,
        )
        new_track_history = self.completed[window_count:]

        refined_history, new_refined_history = BS["refined_collection"](
            new_track_history, self.refined_history_archive
        )
        BS["long_grouper"](
            new_refined_history, refined_history, self.grouped_refined_archive
        )
        persistency = BS["persistency_analyzer"](self.grouped_refined_archive)
        shared = BS["same_window"](
            self.grouped_refined_archive, self.same_window_archive
        )
        comparisons = BS["refined_comparison"](persistency, shared)
        prep = BS["refined_decider_prep"](persistency, shared)
        valleys = BS["valley_analyzer"](
            comparisons,
            self.same_window_archive,
            long_magnitude,
            long_frequency,
            long_mid_time,
        )
        valley_scores = BS["valley_scoring"](comparisons, valleys)
        decisions = BS["refined_decider"](
            time_range, valley_scores, comparisons, prep, long_frequency
        )

        summary = BS["refined_display"](
            decisions,
            new_track_history,
            self.track_history_archive,
            self.lost,
            self.terminated,
        )
        summary = BS["history_realtime"](
            new_track_history, summary, self.track_history_archive
        )
        summary = BS["frequency_drift"](summary, self.track_history_archive)
        summary = BS["strength_trend"](summary, self.track_history_archive)
        summary = BS["stability_analyzer"](summary, self.track_history_archive)
        summary = BS["confidence_score"](summary, self.track_history_archive)
        accepted = BS["accepted_track"](summary, self.track_history_archive)

        self.display_summary = summary
        self.accepted_ids = accepted
        snapshot = {
            "live_index": self.live_index,
            "time": float(time_range[-1]),
            "summary": copy.deepcopy(summary),
            "accepted": list(accepted),
            "lost": copy.deepcopy(self.lost),
            "terminated": copy.deepcopy(self.terminated),
        }
        self.snapshots.append(snapshot)
        return snapshot

    def run_to_end(self):
        while True:
            self.step_once()
            if self.live_index >= len(self.signal):
                break
            self.live_index = min(self.live_index + HOP, len(self.signal))
        return self


def active_tracks_near(summary: dict, frequencies, tolerance=0.51):
    result = []
    for track_id, data in summary.items():
        if data["status"] != "ACTIVE":
            continue
        if any(abs(float(data["rough_frequency"]) - f) <= tolerance for f in frequencies):
            result.append((track_id, data))
    return result


# ---------------------------------------------------------------------------
# 1. Source/API contract
# ---------------------------------------------------------------------------


def test_source_contract_required_core_functions_exist():
    missing = REQUIRED_CORE_FUNCTIONS - set(BS)
    assert not missing, f"Missing required core functions: {sorted(missing)}"


def test_source_parses_cleanly():
    ast.parse(BLACKSITE_SOURCE.read_text(encoding="utf-8"), filename=str(BLACKSITE_SOURCE))


# ---------------------------------------------------------------------------
# 2. CSV ingestion validation
# ---------------------------------------------------------------------------


def _write_csv(path: Path, header: str, rows, delimiter=","):
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for row in rows:
            f.write(delimiter.join(str(x) for x in row) + "\n")


def test_loader_accepts_valid_seconds_csv(tmp_path):
    p = tmp_path / "valid.csv"
    t = timebase(2.1)
    s = tone(t, 8.0)
    _write_csv(p, "time,signal", zip(t, s))
    result = BS["system_input"](str(p))
    assert result is not None
    signal_out, time_out = result
    assert len(signal_out) == len(t)
    assert np.allclose(time_out, t)
    assert np.allclose(signal_out, s)


def test_loader_converts_milliseconds_to_seconds(tmp_path):
    p = tmp_path / "milliseconds.csv"
    t = timebase(2.1)
    s = tone(t, 8.0)
    _write_csv(p, "time(ms),signal", zip(t * 1000.0, s))
    signal_out, time_out = BS["system_input"](str(p))
    assert np.allclose(time_out, t)
    assert np.allclose(signal_out, s)


@pytest.mark.parametrize("delimiter", [";", "\t"])
def test_loader_accepts_supported_delimiters(tmp_path, delimiter):
    p = tmp_path / "delimiter.csv"
    t = timebase(2.1)
    s = tone(t, 8.0)
    _write_csv(p, delimiter.join(["time", "signal"]), zip(t, s), delimiter=delimiter)
    result = BS["system_input"](str(p))
    assert result is not None


def test_loader_rejects_less_than_one_second_of_samples(tmp_path):
    p = tmp_path / "short.csv"
    t = timebase(0.999)
    s = tone(t, 8.0)
    _write_csv(p, "time,signal", zip(t, s))
    assert BS["system_input"](str(p)) is None


def test_loader_rejects_non_numeric_values(tmp_path):
    p = tmp_path / "bad_numeric.csv"
    t = timebase(2.1)
    rows = [(x, 1.0) for x in t]
    rows[100] = (t[100], "not_a_number")
    _write_csv(p, "time,signal", rows)
    assert BS["system_input"](str(p)) is None


def test_loader_rejects_non_finite_values(tmp_path):
    p = tmp_path / "nan.csv"
    t = timebase(2.1)
    rows = [(x, 1.0) for x in t]
    rows[100] = (t[100], "nan")
    _write_csv(p, "time,signal", rows)
    assert BS["system_input"](str(p)) is None


def test_loader_rejects_non_monotonic_time(tmp_path):
    p = tmp_path / "backward.csv"
    t = timebase(2.1)
    t[1000] = t[999]
    s = tone(t, 8.0)
    _write_csv(p, "time,signal", zip(t, s))
    assert BS["system_input"](str(p)) is None


def test_loader_rejects_time_spacing_outside_one_percent(tmp_path):
    p = tmp_path / "irregular.csv"
    t = timebase(2.1)
    t[1000:] += 0.0001  # creates a 10% spacing anomaly at the boundary
    s = tone(t, 8.0)
    _write_csv(p, "time,signal", zip(t, s))
    assert BS["system_input"](str(p)) is None


def test_loader_rejects_unsupported_time_unit(tmp_path):
    p = tmp_path / "minutes.csv"
    t = timebase(2.1)
    s = tone(t, 8.0)
    _write_csv(p, "time(minutes),signal", zip(t, s))
    assert BS["system_input"](str(p)) is None


def test_loader_rejects_ambiguous_signal_columns(tmp_path):
    p = tmp_path / "ambiguous.csv"
    t = timebase(2.1)
    rows = zip(t, np.ones_like(t), np.ones_like(t))
    _write_csv(p, "time,signal,value", rows)
    assert BS["system_input"](str(p)) is None


# ---------------------------------------------------------------------------
# 3. DSP primitives
# ---------------------------------------------------------------------------


def test_window_extract_count_midpoints_and_global_indices():
    t = timebase(5.0)
    s = tone(t, 8.0)
    windows, mid, indices = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    expected_count = 1 + (len(s) - SHORT_WINDOW) // HOP
    assert len(windows) == expected_count
    assert len(mid) == expected_count
    assert indices == list(range(expected_count))
    assert mid[0] == pytest.approx(t[SHORT_WINDOW // 2])


def test_fft_single_tone_frequency_accuracy():
    t = timebase(1.0)
    s = tone(t, 8.0, 2.3)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, _ = BS["window_fft"](windows, mid, t)
    peak_index = int(np.argmax(magnitude[0]))
    assert frequency[peak_index] == pytest.approx(8.0, abs=0.01)


def test_fft_hann_amplitude_normalization():
    t = timebase(1.0)
    amplitude = 2.3
    s = tone(t, 8.0, amplitude)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, _ = BS["window_fft"](windows, mid, t)
    peak = float(np.max(magnitude[0]))
    assert peak == pytest.approx(amplitude, rel=0.01)


def test_fft_is_one_sided_nonnegative_frequency():
    t = timebase(1.0)
    s = tone(t, 8.0)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    _, frequency, _ = BS["window_fft"](windows, mid, t)
    assert np.all(frequency >= 0)
    assert frequency[-1] < FS / 2 + 1e-9


def test_long_fft_has_quarter_hz_resolution():
    t = timebase(4.0)
    s = tone(t, 8.25)
    magnitude, frequency, mid = BS["window_fft_high"](s, t, 0, LONG_WINDOW, HOP)
    assert len(magnitude) == 1
    assert frequency[1] - frequency[0] == pytest.approx(0.25, rel=1e-3)
    peak_index = int(np.argmax(magnitude[0]))
    assert frequency[peak_index] == pytest.approx(8.25, abs=0.02)


def test_peak_detector_finds_two_well_separated_tones():
    t = timebase(1.0)
    s = tone(t, 8.0, 2.3) + tone(t, 13.0, 1.5)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, mid = BS["window_fft"](windows, mid, t)
    peak_mag, peak_freq, _ = BS["peak_detection"](magnitude, frequency, mid)
    found = [float(x) for x in peak_freq[0]]
    assert any(abs(x - 8.0) <= 0.01 for x in found)
    assert any(abs(x - 13.0) <= 0.01 for x in found)


def test_zero_signal_has_no_detected_peaks():
    t = timebase(1.0)
    s = np.zeros_like(t)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, mid = BS["window_fft"](windows, mid, t)
    _, peak_freq, _ = BS["peak_detection"](magnitude, frequency, mid)
    assert len(peak_freq[0]) == 0


def test_snr_and_bandwidth_clean_tone_are_sane():
    t = timebase(1.0)
    s = tone(t, 8.0, 2.3)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, mid = BS["window_fft"](windows, mid, t)
    peak_mag, peak_freq, mid = BS["peak_detection"](magnitude, frequency, mid)
    indexed = BS["track_indexing"](peak_mag, peak_freq, mid)
    indexed = BS["snr_bandwidth"](indexed, magnitude, frequency)
    obs = indexed[0][0]
    assert obs["snr"] is not None and obs["snr"] > 100
    assert obs["bandwidth"] == pytest.approx(2.0, abs=0.1)


def test_snr_changes_when_noise_level_changes_between_windows():
    t = timebase(2.0)
    rng = np.random.default_rng(20260916)
    s = tone(t, 8.0, 2.3)
    s[:1000] += rng.normal(0, 0.05, 1000)
    s[1000:] += rng.normal(0, 0.8, 1000)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, mid = BS["window_fft"](windows, mid, t)
    peak_mag, peak_freq, mid = BS["peak_detection"](magnitude, frequency, mid)
    indexed = BS["track_indexing"](peak_mag, peak_freq, mid)
    indexed = BS["snr_bandwidth"](indexed, magnitude, frequency)
    snrs = [w[0]["snr"] for w in indexed if w and w[0]["snr"] is not None]
    assert len(snrs) >= 2
    assert max(snrs) / min(snrs) > 2.0


# ---------------------------------------------------------------------------
# 4. Tracking state machine & rolling integration
# ---------------------------------------------------------------------------


def test_single_stationary_tone_becomes_one_active_accepted_track():
    t = timebase(8.0)
    h = RollingHarness(tone(t, 8.0), t).run_to_end()
    accepted_near_8 = [
        track_id
        for track_id in h.accepted_ids
        if abs(float(h.display_summary[track_id]["rough_frequency"]) - 8.0) <= 0.01
        and h.display_summary[track_id]["status"] == "ACTIVE"
    ]
    assert accepted_near_8 == ["01"]
    assert len(h.display_summary["01"]["time_history"]) > 5


def test_stationary_track_history_has_no_duplicate_times():
    t = timebase(8.0)
    h = RollingHarness(tone(t, 8.0), t).run_to_end()
    times = h.display_summary["01"]["time_history"]
    assert len(times) == len(set(float(x) for x in times))


def test_candidate_promotes_to_active_then_accepted():
    t = timebase(4.0)
    h = RollingHarness(tone(t, 8.0), t).run_to_end()
    first = h.snapshots[0]
    assert first["summary"]["01"]["status"] == "CANDIDATE"
    later = [s for s in h.snapshots if "01" in s["accepted"]]
    assert later, "Track never became accepted"
    assert later[0]["summary"]["01"]["status"] == "ACTIVE"


def test_missing_tone_transitions_through_coasting_and_lost():
    t = timebase(8.0)
    s = np.zeros_like(t)
    mask = t < 3.0
    s[mask] = tone(t[mask], 8.0)
    h = RollingHarness(s, t).run_to_end()
    states = [
        snap["summary"]["01"]["status"]
        for snap in h.snapshots
        if "01" in snap["summary"]
    ]
    assert "COASTING" in states
    assert "LOST" in states


def test_reacquisition_before_timeout_preserves_track_id():
    t = timebase(14.0)
    s = np.zeros_like(t)
    present = (t < 3.0) | (t > 7.0)
    s[present] = tone(t[present], 8.0)
    h = RollingHarness(s, t).run_to_end()
    active_near_8 = active_tracks_near(h.display_summary, [8.0], tolerance=0.01)
    assert len(active_near_8) == 1
    assert active_near_8[0][0] == "01"
    assert h.display_summary["01"]["status"] == "ACTIVE"


def test_reappearance_after_timeout_terminates_old_id_and_creates_new_id():
    t = timebase(20.0)
    s = np.zeros_like(t)
    present = (t < 3.0) | (t > 13.0)
    s[present] = tone(t[present], 8.0)
    h = RollingHarness(s, t).run_to_end()
    assert h.display_summary["01"]["status"] == "TERMINATED"
    newer = [
        (track_id, data)
        for track_id, data in h.display_summary.items()
        if track_id != "01"
        and data["status"] == "ACTIVE"
        and abs(float(data["rough_frequency"]) - 8.0) <= 0.01
    ]
    assert len(newer) == 1


def test_two_well_separated_tones_keep_two_active_ids():
    t = timebase(8.0)
    s = tone(t, 8.0, 2.3) + tone(t, 13.0, 1.5)
    h = RollingHarness(s, t).run_to_end()
    active = [
        (track_id, float(data["rough_frequency"]))
        for track_id, data in h.display_summary.items()
        if data["status"] == "ACTIVE"
    ]
    assert len(active) == 2
    freqs = sorted(freq for _, freq in active)
    assert freqs[0] == pytest.approx(8.0, abs=0.01)
    assert freqs[1] == pytest.approx(13.0, abs=0.01)
    assert len({track_id for track_id, _ in active}) == 2


def test_noise_only_creates_no_accepted_tracks():
    t = timebase(8.0)
    s = seeded_noise(len(t), 0.3, seed=77)
    h = RollingHarness(s, t).run_to_end()
    assert h.accepted_ids == []


def test_three_simultaneous_tones_remain_three_active_tracks():
    t = timebase(8.0)
    s = tone(t, 8.0, 2.3) + tone(t, 13.0, 1.7) + tone(t, 21.0, 1.2)
    h = RollingHarness(s, t).run_to_end()
    active_freqs = sorted(
        float(data["rough_frequency"])
        for data in h.display_summary.values()
        if data["status"] == "ACTIVE"
    )
    assert len(active_freqs) == 3
    assert active_freqs == pytest.approx([8.0, 13.0, 21.0], abs=0.01)


# ---------------------------------------------------------------------------
# 5. Refined frequency / separation logic
# ---------------------------------------------------------------------------


def test_well_separated_tracks_each_get_correct_refined_frequency():
    t = timebase(8.0)
    s = tone(t, 8.0, 2.3) + tone(t, 13.0, 1.5)
    h = RollingHarness(s, t).run_to_end()
    active = [d for d in h.display_summary.values() if d["status"] == "ACTIVE"]
    assert len(active) == 2
    refined = sorted(float(d["confirmed"][0]) for d in active if d["confirmed"])
    assert refined == pytest.approx([8.0, 13.0], abs=0.26)


def test_close_components_can_be_resolved_inside_one_rough_track():
    # Give the long-FFT persistency logic enough observation time to mature.
    t = timebase(12.0)
    s = tone(t, 8.0, 2.3) + tone(t, 8.5, 1.3)
    h = RollingHarness(s, t).run_to_end()
    active = [d for d in h.display_summary.values() if d["status"] == "ACTIVE"]
    assert len(active) == 1
    confirmed = sorted(float(x) for x in active[0]["confirmed"])
    assert len(confirmed) >= 2
    assert confirmed[0] == pytest.approx(8.0, abs=0.26)
    assert confirmed[1] == pytest.approx(8.5, abs=0.26)


def test_refined_decider_single_persistent_group_is_individual():
    prep = {"01": [{"frequency_average": 8.0, "entry_count": 3, "time_span": 4.0, "shares_window": False}]}
    comparisons = {"01": []}
    valleys = {"01": []}
    long_frequency = np.arange(0.0, 20.0, 0.25)
    t = np.arange(0.0, 6.0, 0.5)
    out = BS["refined_decider"](t, valleys, comparisons, prep, long_frequency)
    assert out["01"][0]["decision"] == "INDIVIDUAL"


def test_refined_decider_insufficient_persistence_is_uncertain():
    prep = {"01": [{"frequency_average": 8.0, "entry_count": 1, "time_span": 0.0, "shares_window": False}]}
    comparisons = {"01": []}
    valleys = {"01": []}
    long_frequency = np.arange(0.0, 20.0, 0.25)
    t = np.arange(0.0, 6.0, 0.5)
    out = BS["refined_decider"](t, valleys, comparisons, prep, long_frequency)
    assert out["01"][0]["decision"] == "UNCERTAIN"


def test_refined_decider_marks_middle_component_blended_when_bracketed_by_individuals():
    prep = {
        "01": [
            {"frequency_average": 8.0, "entry_count": 4, "time_span": 4.0, "shares_window": True},
            {"frequency_average": 8.5, "entry_count": 4, "time_span": 4.0, "shares_window": True},
            {"frequency_average": 8.25, "entry_count": 1, "time_span": 0.0, "shares_window": False},
        ]
    }
    comparisons = {
        "01": [
            {
                "group_1_index": 0,
                "group_1_freq": 8.0,
                "group_2_index": 1,
                "group_2_freq": 8.5,
                "freq_diff": 0.5,
                "shares_window": True,
                "shared_count": 3,
            }
        ]
    }
    valleys = {
        "01": [
            {
                "group_1_index": 0,
                "group_2_index": 1,
                "valley_median": 0.5,
                "measurement_count": 3,
            }
        ]
    }
    long_frequency = np.arange(0.0, 20.0, 0.25)
    t = np.arange(0.0, 6.0, 0.5)
    out = BS["refined_decider"](t, valleys, comparisons, prep, long_frequency)
    assert out["01"][0]["decision"] == "INDIVIDUAL"
    assert out["01"][1]["decision"] == "INDIVIDUAL"
    assert out["01"][2]["decision"] == "BLENDED"


# ---------------------------------------------------------------------------
# 6. Derived metrics
# ---------------------------------------------------------------------------


def _metric_summary(freqs, strengths, times, status="ACTIVE"):
    return {
        "01": {
            "frequency_history": list(freqs),
            "strength_history": list(strengths),
            "time_history": list(times),
            "status": status,
            "latest_snr": 10.0,
            "latest_bandwidth": 2.0,
        }
    }


def _stats(values):
    values = [float(x) for x in values]
    if not values:
        return {"count": 0, "mean": 0.0, "M2": 0.0}
    mean = float(np.mean(values))
    m2 = float(np.sum((np.asarray(values, dtype=float) - mean) ** 2))
    return {"count": len(values), "mean": mean, "M2": m2}


def _metric_archive(summary):
    archive = {}
    for track_id, data in summary.items():
        freqs = list(data.get("frequency_history", []))
        strengths = list(data.get("strength_history", []))
        times = list(data.get("time_history", []))
        status = data.get("status", "ACTIVE")
        active_count = len(times) if status == "ACTIVE" else 0
        archive[track_id] = {
            "time_history": times,
            "strength_history": strengths,
            "frequency_history": freqs,
            "status_history": [status] * len(times),
            "snr_history": [data.get("latest_snr")] * len(times),
            "bandwidth_history": [data.get("latest_bandwidth")] * len(times),
            "instant_freq_drift_rate": [],
            "instant_strength_change_rate": [],
            "frequency_stats": _stats(freqs),
            "strength_stats": _stats(strengths),
            "active_count": active_count,
            "active_time_history": times[:] if status == "ACTIVE" else [],
            "active_frequency_history": freqs[:] if status == "ACTIVE" else [],
        }
    return archive


def test_frequency_drift_known_linear_history():
    d = _metric_summary([8.0, 8.5, 9.0], [1, 1, 1], [0.0, 1.0, 2.0])
    archive = _metric_archive(d)
    d = BS["frequency_drift"](d, archive)
    assert d["01"]["instant_freq_drift_rate"] == pytest.approx([0.5, 0.5])
    assert d["01"]["net_freq_drift_rate"] == pytest.approx(0.5)


def test_strength_trend_known_linear_history():
    d = _metric_summary([8, 8, 8], [1.0, 2.0, 3.0], [0.0, 2.0, 4.0])
    archive = _metric_archive(d)
    d = BS["strength_trend"](d, archive)
    assert d["01"]["instant_strength_change_rate"] == pytest.approx([0.5, 0.5])
    assert d["01"]["net_strength_change_rate"] == pytest.approx(0.5)


def test_stability_analyzer_matches_numpy_standard_deviation():
    d = _metric_summary([8.0, 8.5, 9.0], [1.0, 2.0, 3.0], [0, 1, 2])
    archive = _metric_archive(d)
    d = BS["stability_analyzer"](d, archive)
    assert d["01"]["frequency_std"] == pytest.approx(np.std([8.0, 8.5, 9.0]))
    assert d["01"]["strength_std"] == pytest.approx(np.std([1.0, 2.0, 3.0]))


def test_confidence_score_is_bounded_zero_to_one():
    d = _metric_summary([8.0, 8.0, 8.0], [2.0, 2.0, 2.0], [0, 1, 2])
    archive = _metric_archive(d)
    d = BS["stability_analyzer"](d, archive)
    d = BS["confidence_score"](d, archive)
    score = d["01"]["confidence_score"]
    assert score is not None
    assert 0.0 <= score <= 1.0


def test_amplitude_ramp_produces_positive_strength_trend():
    t = timebase(10.0)
    amplitude = 1.0 + 0.15 * t
    s = amplitude * np.sin(2 * np.pi * 8.0 * t)
    h = RollingHarness(s, t).run_to_end()
    d = h.display_summary["01"]
    assert d["status"] == "ACTIVE"
    assert d["net_strength_change_rate"] is not None
    assert d["net_strength_change_rate"] > 0
    assert d["strength_history"][-1] > d["strength_history"][0]


# This is intentionally a release requirement, not xfail. BLACKSITE exposes
# frequency drift as a first-class metric; a slow, continuous chirp should not
# fragment into multiple identities merely when the rough FFT bin changes.
def test_slow_frequency_drift_preserves_identity_and_reports_positive_drift():
    t = timebase(12.0)
    s = chirp_linear(t, 8.0, 10.0, 2.3)
    h = RollingHarness(s, t).run_to_end()

    relevant = [
        (track_id, d)
        for track_id, d in h.display_summary.items()
        if 7.0 <= float(d["rough_frequency"]) <= 11.0
        and len(d["time_history"]) >= 2
    ]
    assert len(relevant) == 1, (
        "Slow chirp fragmented across track IDs: "
        + str([(track_id, d["status"], d["rough_frequency"]) for track_id, d in relevant])
    )
    _, d = relevant[0]
    assert d["net_freq_drift_rate"] is not None
    assert d["net_freq_drift_rate"] > 0.05


# ---------------------------------------------------------------------------
# 7. Export integrity
# ---------------------------------------------------------------------------


def _fake_export_summary():
    return {
        "01": {
            "status": "ACTIVE",
            "rough_frequency": 8.0,
            "strength": 2.3,
            "confirmed": [8.01, 8.02],
            "blended": [],
            "uncertain": [7.98],
            "time_history": [0.5, 1.0, 1.5],
            "frequency_history": [8.0, 8.0, 8.0],
            "strength_history": [2.2, 2.3, 2.4],
            "status_history": ["CANDIDATE", "ACTIVE", "ACTIVE"],
            "snr_history": [10.0, 11.0, 12.0],
            "bandwidth_history": [2.0, 2.0, 2.0],
            "instant_freq_drift_rate": [0.0, 0.0],
            "instant_strength_change_rate": [0.2, 0.2],
            "net_freq_drift_rate": 0.0,
            "net_strength_change_rate": 0.2,
            "frequency_std": 0.0,
            "strength_std": float(np.std([2.2, 2.3, 2.4])),
            "latest_snr": 12.0,
            "latest_bandwidth": 2.0,
            "confidence_score": 0.9,
        }
    }


def test_history_export_schema_rows_and_first_rate_na(tmp_path):
    path = tmp_path / "history.csv"
    BS["export_track"](_fake_export_summary(), str(path))
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == [
        "track_id", "time", "status", "rough_frequency", "strength",
        "snr", "bandwidth", "frequency_drift", "strength_trend"
    ]
    assert len(rows) == 4
    assert rows[1][0] == "01"
    assert rows[1][7] == "N/A"
    assert rows[1][8] == "N/A"


def test_summary_export_schema_and_refined_serialization(tmp_path):
    path = tmp_path / "summary.csv"
    BS["export_summary"](_fake_export_summary(), str(path))
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == [
        "track_id", "final_status", "latest_rough_frequency", "latest_strength",
        "confirmed_refined", "blended_refined", "uncertain_refined",
        "net_frequency_drift", "net_strength_trend", "frequency_std",
        "strength_std", "latest_snr", "latest_bandwidth", "confidence"
    ]
    assert len(rows) == 2
    assert rows[1][0] == "01"
    assert rows[1][1] == "ACTIVE"
    assert rows[1][4] == "8.01; 8.02"
    assert rows[1][5] == ""
    assert rows[1][6] == "7.98"


def test_real_pipeline_export_history_row_count_matches_observations(tmp_path):
    t = timebase(6.0)
    h = RollingHarness(tone(t, 8.0), t).run_to_end()
    path = tmp_path / "real_history.csv"
    BS["export_track"](h.display_summary, str(path))
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    expected_observations = sum(
        len(d["time_history"]) for d in h.display_summary.values()
    )
    assert len(rows) - 1 == expected_observations


# ---------------------------------------------------------------------------
# 8. Robustness / known limitations / optional performance
# ---------------------------------------------------------------------------


def test_deterministic_pipeline_same_input_same_output():
    t = timebase(6.0)
    s = tone(t, 8.0) + seeded_noise(len(t), 0.1, seed=9001)
    a = RollingHarness(s.copy(), t.copy()).run_to_end().display_summary
    b = RollingHarness(s.copy(), t.copy()).run_to_end().display_summary
    assert a.keys() == b.keys()
    for track_id in a:
        assert a[track_id]["status"] == b[track_id]["status"]
        assert a[track_id]["frequency_history"] == pytest.approx(b[track_id]["frequency_history"])
        assert a[track_id]["strength_history"] == pytest.approx(b[track_id]["strength_history"])


@pytest.mark.xfail(reason="Current local-max detector excludes endpoint bins, so DC is not a supported track.", strict=False)
def test_dc_component_detected_as_track():
    t = timebase(6.0)
    s = np.full_like(t, 2.0)
    h = RollingHarness(s, t).run_to_end()
    assert any(abs(float(d["rough_frequency"])) < 0.01 for d in h.display_summary.values())


@pytest.mark.xfail(reason="Current nearest-bin tracker is not designed to guarantee identity through crossing tones.", strict=False)
def test_crossing_tones_preserve_two_physical_identities():
    t = timebase(12.0)
    duration = t[-1] + DT
    a = chirp_linear(t, 7.0, 11.0, 2.3)
    b = chirp_linear(t, 11.0, 7.0, 1.8)
    h = RollingHarness(a + b, t).run_to_end()
    long_lived = [d for d in h.display_summary.values() if len(d["time_history"]) >= 10]
    assert len(long_lived) == 2


def test_optional_core_pipeline_runtime_budget():
    if os.environ.get("BLACKSITE_RUN_PERF") != "1":
        pytest.skip("Set BLACKSITE_RUN_PERF=1 to run hardware-dependent performance gate")
    t = timebase(12.0)
    s = tone(t, 8.0, 2.3) + tone(t, 13.0, 1.5) + seeded_noise(len(t), 0.2, seed=1)
    start = wall_time.perf_counter()
    RollingHarness(s, t).run_to_end()
    elapsed = wall_time.perf_counter() - start
    assert elapsed < 10.0, f"12 s analysis took {elapsed:.2f} s; budget is 10 s"


# ---------------------------------------------------------------------------
# 9. Boundary, regression, and qualification tests
# ---------------------------------------------------------------------------

def _make_indexed_frequency_frames(times, freqs_by_frame):
    peak_mags = []
    peak_freqs = []
    for freqs in freqs_by_frame:
        peak_freqs.append(np.asarray(freqs, dtype=float))
        peak_mags.append(np.asarray([2.0] * len(freqs), dtype=float))
    return BS["track_indexing"](peak_mags, peak_freqs, list(times))


def test_tracker_exactly_one_bin_step_preserves_identity():
    freq_axis = np.arange(0.0, 30.0, 1.0)
    times = [0.5, 1.0]
    indexed = _make_indexed_frequency_frames(times, [[8.0], [9.0]])
    completed, lost, terminated, counter = BS["track_comparison"](
        indexed, freq_axis, times, [], [], [], [], 0
    )
    assert completed[-1][0]["ID"] == "01"
    assert completed[-1][0]["frequency"] == pytest.approx(9.0)
    assert completed[-1][0]["status"] == "ACTIVE"


def test_tracker_more_than_one_bin_step_creates_new_identity():
    freq_axis = np.arange(0.0, 30.0, 1.0)
    times = [0.5, 1.0]
    indexed = _make_indexed_frequency_frames(times, [[8.0], [10.0]])
    completed, lost, terminated, counter = BS["track_comparison"](
        indexed, freq_axis, times, [], [], [], [], 0
    )
    ids_last = {obs["ID"] for obs in completed[-1]}
    assert "02" in ids_last
    assert any(obs["ID"] == "02" and obs["frequency"] == pytest.approx(10.0) for obs in completed[-1])


def test_lost_track_reacquisition_exactly_one_bin_preserves_identity():
    freq_axis = np.arange(0.0, 30.0, 1.0)
    times = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    indexed = _make_indexed_frequency_frames(times, [[8.0], [8.0], [], [], [], [9.0]])
    completed, lost, terminated, counter = BS["track_comparison"](
        indexed, freq_axis, times, [], [], [], [], 0
    )
    last = [obs for obs in completed[-1] if obs["frequency"] == pytest.approx(9.0)]
    assert len(last) == 1
    assert last[0]["ID"] == "01"
    assert last[0]["status"] == "ACTIVE"


def test_two_hz_separated_stationary_tones_are_both_represented():
    """Requirement-level separation test: representation may be rough or refined."""
    t = timebase(12.0)
    s = tone(t, 8.0, 2.3) + tone(t, 10.0, 1.8)
    h = RollingHarness(s, t).run_to_end()

    represented = []
    for data in h.display_summary.values():
        if data["status"] != "ACTIVE":
            continue
        represented.append(float(data["rough_frequency"]))
        represented.extend(float(x) for x in data["confirmed"])

    assert any(abs(f - 8.0) <= 0.26 for f in represented)
    assert any(abs(f - 10.0) <= 0.26 for f in represented), (
        "10 Hz component disappeared from both rough and confirmed refined output; "
        f"represented frequencies were {represented}"
    )


def test_downward_slow_frequency_drift_preserves_identity_and_negative_drift():
    t = timebase(12.0)
    s = chirp_linear(t, 10.0, 8.0, 2.3)
    h = RollingHarness(s, t).run_to_end()
    relevant = [
        (track_id, d)
        for track_id, d in h.display_summary.items()
        if 7.0 <= float(d["rough_frequency"]) <= 11.0
        and len(d["time_history"]) >= 2
    ]
    assert len(relevant) == 1
    _, d = relevant[0]
    assert d["net_freq_drift_rate"] is not None
    assert d["net_freq_drift_rate"] < -0.05


def test_decreasing_amplitude_produces_negative_strength_trend():
    t = timebase(10.0)
    amplitude = 2.5 - 0.12 * t
    s = amplitude * np.sin(2 * np.pi * 8.0 * t)
    h = RollingHarness(s, t).run_to_end()
    d = h.display_summary["01"]
    assert d["status"] == "ACTIVE"
    assert d["net_strength_change_rate"] is not None
    assert d["net_strength_change_rate"] < 0
    assert d["strength_history"][-1] < d["strength_history"][0]


@pytest.mark.parametrize("frequency_hz", [5.0, 8.0, 17.0, 31.0, 47.0])
def test_stationary_frequency_sweep_detects_expected_track(frequency_hz):
    t = timebase(6.0)
    s = tone(t, frequency_hz, 2.0) + seeded_noise(len(t), 0.03, seed=int(frequency_hz * 100))
    h = RollingHarness(s, t).run_to_end()
    active = [
        d for d in h.display_summary.values()
        if d["status"] == "ACTIVE"
        and abs(float(d["rough_frequency"]) - frequency_hz) <= 0.01
    ]
    assert len(active) == 1


@pytest.mark.parametrize("phase", [0.0, math.pi / 4, math.pi / 2, math.pi])
def test_fft_frequency_detection_is_phase_invariant(phase):
    t = timebase(1.0)
    s = tone(t, 13.0, 1.7, phase=phase)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, _ = BS["window_fft"](windows, mid, t)
    peak_index = int(np.argmax(magnitude[0]))
    assert frequency[peak_index] == pytest.approx(13.0, abs=0.01)


@pytest.mark.parametrize("fs, frequency_hz", [(500.0, 8.0), (800.0, 8.0), (2000.0, 8.0)])
def test_fft_frequency_accuracy_across_supported_uniform_sample_rates(fs, frequency_hz):
    t = timebase(max(2.1, SHORT_WINDOW / fs + 0.1), fs=fs)
    s = tone(t, frequency_hz, 2.0)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, _ = BS["window_fft"](windows, mid, t)
    peak_index = int(np.argmax(magnitude[0]))
    bin_width = float(frequency[1] - frequency[0])
    assert abs(float(frequency[peak_index]) - frequency_hz) <= bin_width / 2 + 1e-9


def test_off_bin_tone_quantizes_within_half_short_fft_bin():
    t = timebase(1.0)
    target = 8.4
    s = tone(t, target, 2.0)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, _ = BS["window_fft"](windows, mid, t)
    peak_index = int(np.argmax(magnitude[0]))
    bin_width = float(frequency[1] - frequency[0])
    assert abs(float(frequency[peak_index]) - target) <= bin_width / 2 + 1e-9


def test_peak_results_are_sorted_by_descending_strength():
    t = timebase(1.0)
    s = tone(t, 7.0, 0.8) + tone(t, 13.0, 2.5) + tone(t, 23.0, 1.4)
    windows, mid, _ = BS["window_extract"](s, t, 0, SHORT_WINDOW, HOP)
    magnitude, frequency, mid = BS["window_fft"](windows, mid, t)
    peak_mag, peak_freq, _ = BS["peak_detection"](magnitude, frequency, mid)
    mags = peak_mag[0]
    assert len(mags) >= 3
    assert np.all(mags[:-1] >= mags[1:])


def test_window_extract_global_indices_respect_nonzero_start_sample():
    t = timebase(5.0)
    s = tone(t, 8.0)
    start_sample = 2000
    windows, mid, indices = BS["window_extract"](s, t, start_sample, SHORT_WINDOW, HOP)
    assert indices[0] == start_sample // HOP
    assert indices == list(range(start_sample // HOP, start_sample // HOP + len(indices)))


def test_loader_accepts_exact_minimum_2000_samples(tmp_path):
    p = tmp_path / "exact_minimum.csv"
    t = timebase(2.0)
    assert len(t) == 2000
    s = tone(t, 8.0)
    _write_csv(p, "time,signal", zip(t, s))
    result = BS["system_input"](str(p))
    assert result is not None
    signal_out, time_out = result
    assert len(signal_out) == 2000
    assert len(time_out) == 2000


@pytest.mark.parametrize(
    "unit, scale",
    [("us", 1e6), ("µs", 1e6), ("ns", 1e9)],
)
def test_loader_converts_small_time_units_to_seconds(tmp_path, unit, scale):
    p = tmp_path / f"time_{unit.replace('µ','micro')}.csv"
    t = timebase(2.1)
    s = tone(t, 8.0)
    _write_csv(p, f"time({unit}),signal", zip(t * scale, s))
    result = BS["system_input"](str(p))
    assert result is not None
    signal_out, time_out = result
    assert np.allclose(time_out, t)
    assert np.allclose(signal_out, s)


def test_loader_accepts_case_and_whitespace_in_headers(tmp_path):
    p = tmp_path / "header_case.csv"
    t = timebase(2.1)
    s = tone(t, 8.0)
    _write_csv(p, "  TIME (ms)  ,  SIGNAL  ", zip(t * 1000.0, s))
    result = BS["system_input"](str(p))
    assert result is not None
    signal_out, time_out = result
    assert np.allclose(time_out, t)


def test_loader_missing_file_returns_none(tmp_path):
    assert BS["system_input"](str(tmp_path / "does_not_exist.csv")) is None


def test_loader_rejects_empty_file(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    assert BS["system_input"](str(p)) is None


def test_accepted_track_requires_two_active_history_entries():
    summary = {"01": {"status": "ACTIVE"}}
    one_active_archive = {"01": {"active_count": 1}}
    two_active_archive = {"01": {"active_count": 2}}
    assert BS["accepted_track"](summary, one_active_archive) == []
    assert BS["accepted_track"](summary, two_active_archive) == ["01"]


def test_frequency_and_strength_metrics_single_observation_return_none():
    d = _metric_summary([8.0], [2.0], [0.5])
    archive = _metric_archive(d)
    d = BS["frequency_drift"](d, archive)
    d = BS["strength_trend"](d, archive)
    d = BS["stability_analyzer"](d, archive)
    assert d["01"]["instant_freq_drift_rate"] == []
    assert d["01"]["net_freq_drift_rate"] is None
    assert d["01"]["instant_strength_change_rate"] == []
    assert d["01"]["net_strength_change_rate"] is None
    assert d["01"]["frequency_std"] is None
    assert d["01"]["strength_std"] is None


def test_frequency_drift_known_negative_linear_history():
    d = _metric_summary([10.0, 9.5, 9.0], [1, 1, 1], [0.0, 1.0, 2.0])
    archive = _metric_archive(d)
    d = BS["frequency_drift"](d, archive)
    assert d["01"]["instant_freq_drift_rate"] == pytest.approx([-0.5, -0.5])
    assert d["01"]["net_freq_drift_rate"] == pytest.approx(-0.5)


def test_strength_trend_known_negative_linear_history():
    d = _metric_summary([8, 8, 8], [3.0, 2.0, 1.0], [0.0, 2.0, 4.0])
    archive = _metric_archive(d)
    d = BS["strength_trend"](d, archive)
    assert d["01"]["instant_strength_change_rate"] == pytest.approx([-0.5, -0.5])
    assert d["01"]["net_strength_change_rate"] == pytest.approx(-0.5)


def test_confidence_active_status_scores_higher_than_lost_with_same_measurements():
    active = _metric_summary([8.0, 8.0, 8.0], [2.0, 2.0, 2.0], [0, 1, 2], status="ACTIVE")
    lost = _metric_summary([8.0, 8.0, 8.0], [2.0, 2.0, 2.0], [0, 1, 2], status="LOST")
    for d in (active, lost):
        archive = _metric_archive(d)
        BS["stability_analyzer"](d, archive)
        BS["confidence_score"](d, archive)
    assert active["01"]["confidence_score"] > lost["01"]["confidence_score"]


def test_confidence_renormalizes_when_some_metrics_are_missing():
    d = {
        "01": {
            "status": "ACTIVE",
            "latest_snr": None,
            "latest_bandwidth": None,
            "frequency_std": None,
            "strength_std": None,
            "strength_history": [2.0],
        }
    }
    archive = _metric_archive(d)
    d = BS["confidence_score"](d, archive)
    assert d["01"]["confidence_score"] == pytest.approx(1.0)


def test_refined_collection_deduplicates_long_fft_times_on_arrival():
    history = [
        [{"ID": "01", "time": 0.5, "long_fft_candidate": np.array([8.0]), "long_fft_time": 2.0}],
        [{"ID": "01", "time": 1.0, "long_fft_candidate": np.array([8.0]), "long_fft_time": 2.0}],
        [{"ID": "01", "time": 1.5, "long_fft_candidate": np.array([8.0]), "long_fft_time": 2.5}],
    ]
    archive = {}
    refined, new_refined = BS["refined_collection"](history, archive)
    assert len(refined["01"]) == 2
    assert len(new_refined["01"]) == 2
    assert [x["long_fft_time"] for x in refined["01"]] == [2.0, 2.5]

def test_long_grouper_keeps_nearby_refined_values_together_and_far_value_separate():
    new_refined = {
        "01": [
            {"time": 0.5, "long_fft_candidate": np.array([8.00]), "long_fft_time": 2.0},
            {"time": 1.0, "long_fft_candidate": np.array([8.08]), "long_fft_time": 2.5},
            {"time": 1.5, "long_fft_candidate": np.array([8.40]), "long_fft_time": 3.0},
        ]
    }
    refined = copy.deepcopy(new_refined)
    archive = {}
    BS["long_grouper"](new_refined, refined, archive)
    assert len(archive["01"]) == 2
    assert archive["01"][0]["count"] == 2
    assert archive["01"][1]["count"] == 1

def test_same_window_counts_shared_long_fft_times():
    grouped_archive = {
        "01": [
            {
                "points": [{"frequency": 8.0, "long_time": 2.0}, {"frequency": 8.0, "long_time": 2.5}],
                "frequency_sum": 16.0,
                "count": 2,
                "time_set": {2.0, 2.5},
                "new_time_set": {2.0, 2.5},
            },
            {
                "points": [{"frequency": 8.5, "long_time": 2.0}, {"frequency": 8.5, "long_time": 3.0}],
                "frequency_sum": 17.0,
                "count": 2,
                "time_set": {2.0, 3.0},
                "new_time_set": {2.0, 3.0},
            },
        ]
    }
    same_archive = {}
    shared = BS["same_window"](grouped_archive, same_archive)
    assert len(shared["01"]) == 1
    assert shared["01"][0]["shared_count"] == 1
    assert shared["01"][0]["shared_time"] == [2.0]

def test_valley_scoring_uses_median_and_counts_valid_measurements():
    comparisons = {
        "01": [
            {"group_1_index": 0, "group_2_index": 1, "group_1_freq": 8.0, "group_2_freq": 8.5,
             "freq_diff": 0.5, "shares_window": True, "shared_count": 3}
        ]
    }
    valleys = {
        "01": [
            {"group_1_index": 0, "group_2_index": 1, "shared_time": 2.0, "valley_ratio": 0.4},
            {"group_1_index": 0, "group_2_index": 1, "shared_time": 2.5, "valley_ratio": 0.8},
            {"group_1_index": 0, "group_2_index": 1, "shared_time": 3.0, "valley_ratio": None},
        ]
    }
    out = BS["valley_scoring"](comparisons, valleys)
    assert out["01"][0]["valley_median"] == pytest.approx(0.6)
    assert out["01"][0]["measurement_count"] == 2


def test_refined_display_uses_current_track_decision_without_rewriting_history():
    track_archive = {
        "01": {
            "frequency_history": [8.0, 8.0],
            "strength_history": [2.0, 2.0],
            "status_history": ["ACTIVE", "ACTIVE"],
        }
    }
    decision = {"01": [{"frequency": 8.02, "decision": "INDIVIDUAL"}]}
    out = BS["refined_display"](decision, [], track_archive, [], [])
    assert out["01"]["confirmed"] == [8.02]
    assert out["01"]["blended"] == []
    assert out["01"]["uncertain"] == []

def test_refined_display_lost_status_overrides_last_history_status():
    track_archive = {
        "01": {
            "frequency_history": [8.0],
            "strength_history": [2.0],
            "status_history": ["ACTIVE"],
        }
    }
    lost = [{"ID": "01"}]
    out = BS["refined_display"]({}, [], track_archive, lost, [])
    assert out["01"]["status"] == "LOST"


def test_summary_export_two_tracks_emits_one_row_per_track(tmp_path):
    summary = _fake_export_summary()
    summary["02"] = copy.deepcopy(summary["01"])
    summary["02"]["status"] = "LOST"
    summary["02"]["rough_frequency"] = 13.0
    path = tmp_path / "summary_two.csv"
    BS["export_summary"](summary, str(path))
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 3
    assert {rows[1][0], rows[2][0]} == {"01", "02"}


def test_export_functions_raise_oserror_for_directory_destination(tmp_path):
    with pytest.raises(OSError):
        BS["export_track"](_fake_export_summary(), str(tmp_path))
    with pytest.raises(OSError):
        BS["export_summary"](_fake_export_summary(), str(tmp_path))


@pytest.mark.parametrize("seed", [101, 202, 303, 404, 505])
def test_noise_only_multiple_seeds_produces_no_accepted_tracks(seed):
    t = timebase(6.0)
    s = seeded_noise(len(t), 0.3, seed=seed)
    h = RollingHarness(s, t).run_to_end()
    assert h.accepted_ids == []


def test_five_simultaneous_well_separated_tones_remain_distinct():
    t = timebase(8.0)
    freqs = [6.0, 12.0, 18.0, 24.0, 30.0]
    amps = [2.5, 2.2, 1.9, 1.6, 1.3]
    s = sum(tone(t, f, a) for f, a in zip(freqs, amps))
    h = RollingHarness(s, t).run_to_end()
    active_freqs = sorted(
        float(data["rough_frequency"])
        for data in h.display_summary.values()
        if data["status"] == "ACTIVE"
    )
    assert active_freqs == pytest.approx(freqs, abs=0.01)


def test_tone_appearing_mid_recording_is_acquired_without_corrupting_prior_history():
    t = timebase(10.0)
    s = np.zeros_like(t)
    mask = t >= 4.0
    s[mask] = tone(t[mask], 8.0, 2.3)
    h = RollingHarness(s, t).run_to_end()
    active = [
        (track_id, d) for track_id, d in h.display_summary.items()
        if d["status"] == "ACTIVE" and abs(float(d["rough_frequency"]) - 8.0) <= 0.01
    ]
    assert len(active) == 1
    _, d = active[0]
    assert min(float(x) for x in d["time_history"]) >= 3.5


def test_pipeline_repeated_stationary_tone_has_monotonic_history_times():
    t = timebase(10.0)
    h = RollingHarness(tone(t, 8.0), t).run_to_end()
    times = [float(x) for x in h.display_summary["01"]["time_history"]]
    assert all(b > a for a, b in zip(times, times[1:]))


def test_no_frame_assigns_same_track_id_to_two_observations():
    t = timebase(8.0)
    s = tone(t, 8.0, 2.3) + tone(t, 13.0, 1.8) + tone(t, 21.0, 1.2)
    h = RollingHarness(s, t).run_to_end()
    for frame in h.completed:
        ids = [obs["ID"] for obs in frame]
        assert len(ids) == len(set(ids))


def test_static_regression_export_timer_is_created_from_canvas():
    source = BLACKSITE_SOURCE.read_text(encoding="utf-8")
    assert "export_timer = fig.canvas.new_timer(" in source
    assert "export_timer = fig.new_timer(" not in source


def test_tracker_one_bin_boundary_tolerates_floating_point_roundoff():
    """One-bin association must not fail because of sub-picohertz representation error."""
    freq_axis = np.arange(0.0, 30.0, 1.0)
    times = [0.5, 1.0]
    indexed = _make_indexed_frequency_frames(times, [[8.0], [9.0 + 1e-12]])
    completed, lost, terminated, counter = BS["track_comparison"](
        indexed, freq_axis, times, [], [], [], [], 0
    )
    current = [obs for obs in completed[-1] if abs(float(obs["frequency"]) - 9.0) < 1e-6]
    assert len(current) == 1
    assert current[0]["ID"] == "01"


def test_lost_reacquisition_one_bin_boundary_tolerates_floating_point_roundoff():
    """LOST reacquisition uses the same numerical one-bin boundary contract."""
    freq_axis = np.arange(0.0, 30.0, 1.0)
    times = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    indexed = _make_indexed_frequency_frames(
        times, [[8.0], [8.0], [], [], [], [9.0 + 1e-12]]
    )
    completed, lost, terminated, counter = BS["track_comparison"](
        indexed, freq_axis, times, [], [], [], [], 0
    )
    current = [obs for obs in completed[-1] if abs(float(obs["frequency"]) - 9.0) < 1e-6]
    assert len(current) == 1
    assert current[0]["ID"] == "01"
    assert current[0]["status"] == "ACTIVE"


def test_active_collection_returns_only_active_observations():
    archive = {
        "01": {"active_time_history": [0.5, 1.0], "active_frequency_history": [8.0, 8.0]},
        "02": {"active_time_history": [], "active_frequency_history": []},
    }
    times, freqs, ids = BS["active_collection"](archive, np.array([0.0, 1.5]))
    assert times == [0.5, 1.0]
    assert freqs == [8.0, 8.0]
    assert ids == ["01", "01"]

def test_summary_export_covers_empty_and_blended_refined_fields(tmp_path):
    summary = _fake_export_summary()
    summary["01"]["confirmed"] = []
    summary["01"]["blended"] = [8.25, 8.50]
    summary["01"]["uncertain"] = []
    path = tmp_path / "summary_blended.csv"
    BS["export_summary"](summary, str(path))
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[1][4] == ""
    assert rows[1][5] == "8.25; 8.5"
    assert rows[1][6] == ""


def test_loader_accepts_bracketed_millisecond_unit(tmp_path):
    p = tmp_path / "bracket_ms.csv"
    t = timebase(2.1)
    s = tone(t, 8.0)
    _write_csv(p, "time[ms],signal", zip(t * 1000.0, s))
    result = BS["system_input"](str(p))
    assert result is not None
    _, time_out = result
    assert np.allclose(time_out, t)


def test_loader_rejects_non_finite_time_values(tmp_path):
    p = tmp_path / "nan_time.csv"
    t = timebase(2.1)
    rows = [(x, 1.0) for x in t]
    rows[100] = ("nan", 1.0)
    _write_csv(p, "time,signal", rows)
    assert BS["system_input"](str(p)) is None


def test_valley_analyzer_adjacent_bins_returns_none_ratio():
    long_frequency = np.arange(0.0, 20.0, 0.25)
    long_mid_time = np.array([2.0])
    mag = np.zeros_like(long_frequency)
    mag[np.argmin(np.abs(long_frequency - 8.0))] = 2.0
    mag[np.argmin(np.abs(long_frequency - 8.25))] = 1.8
    comparisons = {
        "01": [{
            "group_1_index": 0,
            "group_2_index": 1,
            "group_1_freq": 8.0,
            "group_2_freq": 8.25,
            "freq_diff": 0.25,
            "shares_window": True,
            "shared_count": 1,
        }]
    }
    shared_archive = {
        "01": {
            (0, 1): {
                "group_1_index": 0,
                "group_2_index": 1,
                "share_time": [2.0],
                "share_time_set": {2.0},
            }
        }
    }
    out = BS["valley_analyzer"](
        comparisons, shared_archive, [mag], long_frequency, long_mid_time
    )
    assert out["01"][0]["valley_ratio"] is None


def test_frequency_and_strength_net_rates_none_when_time_span_is_zero():
    d = _metric_summary([8.0, 9.0], [1.0, 2.0], [1.0, 1.0])
    archive = _metric_archive(d)
    d = BS["frequency_drift"](d, archive)
    d = BS["strength_trend"](d, archive)
    assert d["01"]["instant_freq_drift_rate"] == [None]
    assert d["01"]["instant_strength_change_rate"] == [None]
    assert d["01"]["net_freq_drift_rate"] is None
    assert d["01"]["net_strength_change_rate"] is None


def test_frequency_drift_duplicate_timestamp_preserves_alignment_without_nan():
    d = _metric_summary([8.0, 9.0], [1.0, 1.0], [1.0, 1.0])
    archive = _metric_archive(d)
    out = BS["frequency_drift"](d, archive)
    assert out["01"]["instant_freq_drift_rate"] == [None]
    assert out["01"]["net_freq_drift_rate"] is None


def test_strength_trend_duplicate_timestamp_preserves_alignment_without_nan():
    d = _metric_summary([8.0, 8.0], [1.0, 2.0], [1.0, 1.0])
    archive = _metric_archive(d)
    out = BS["strength_trend"](d, archive)
    assert out["01"]["instant_strength_change_rate"] == [None]
    assert out["01"]["net_strength_change_rate"] is None


def test_snr_none_when_no_neighbor_bins_exist():
    indexed = [[{"frequency": 0.0, "snr": None, "bandwidth": None}]]
    out = BS["snr_bandwidth"](indexed, [np.array([1.0])], np.array([0.0]))
    assert out[0][0]["snr"] is None
    assert out[0][0]["bandwidth"] is None


def test_snr_none_when_neighbor_median_is_zero():
    frequency = np.arange(0.0, 7.0, 1.0)
    magnitude = np.zeros(7)
    magnitude[3] = 2.0
    indexed = [[{"frequency": 3.0, "snr": None, "bandwidth": None}]]
    out = BS["snr_bandwidth"](indexed, [magnitude], frequency)
    assert out[0][0]["snr"] is None


def test_confidence_zero_snr_and_unknown_status_paths():
    d = {
        "01": {
            "status": "UNRECOGNIZED",
            "latest_snr": 1.0,
            "latest_bandwidth": 2.0,
            "frequency_std": 0.0,
            "strength_std": 0.0,
            "strength_history": [2.0, 2.0],
        }
    }
    archive = _metric_archive(d)
    out = BS["confidence_score"](d, archive)
    assert out["01"]["confidence_score"] is not None
    assert 0.0 <= out["01"]["confidence_score"] <= 1.0


def test_refined_display_collects_blended_component():
    track_archive = {
        "01": {
            "frequency_history": [8.0],
            "strength_history": [2.0],
            "status_history": ["ACTIVE"],
        }
    }
    decision = {"01": [{"frequency": 8.25, "decision": "BLENDED"}]}
    out = BS["refined_display"](decision, [], track_archive, [], [])
    assert out["01"]["blended"] == [8.25]


# ---------------------------------------------------------------------------
# Release regression added after nearest-rough refined assignment redesign
# ---------------------------------------------------------------------------

def test_refined_peak_assignment_does_not_duplicate_between_rough_tracks():
    """A refined long-FFT peak shall belong to only its nearest rough track."""
    t = timebase(12.0)
    s = tone(t, 8.0, 2.3) + tone(t, 10.5, 1.8)
    h = RollingHarness(s, t).run_to_end()

    active = sorted(
        (d for d in h.display_summary.values() if d["status"] == "ACTIVE"),
        key=lambda d: float(d["rough_frequency"]),
    )
    assert len(active) == 2

    low_confirmed = [float(x) for x in active[0]["confirmed"]]
    high_confirmed = [float(x) for x in active[1]["confirmed"]]

    assert any(abs(x - 8.0) <= 0.26 for x in low_confirmed)
    assert not any(abs(x - 10.5) <= 0.26 for x in low_confirmed)
    assert any(abs(x - 10.5) <= 0.26 for x in high_confirmed)
    assert not any(abs(x - 8.0) <= 0.26 for x in high_confirmed)
