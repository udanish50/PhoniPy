"""Deterministic short-window harmonic detector and consecutive-note segmentation."""

import math

import numpy as np
from scipy.fft import irfft, next_fast_len, rfft, rfftfreq
from scipy.signal import find_peaks

from .audio import load_audio, prepare_audio
from .config import AnalysisConfig
from .metrics import compute_metrics
from .models import AnalysisResult, Frame, Segment


def frequency_to_key(frequency):
    """Fractional MIDI note number, A4=69. Piano-key numbering equals MIDI minus 20."""
    value = np.asarray(frequency, dtype=float)
    if np.any(~np.isfinite(value)) or np.any(value <= 0):
        raise ValueError("Frequency must be positive and finite")
    answer = 69 + 12 * np.log2(value / 440)
    return float(answer) if answer.ndim == 0 else answer


def key_to_frequency(key):
    value = np.asarray(key, dtype=float)
    if np.any(~np.isfinite(value)):
        raise ValueError("Key must be finite")
    with np.errstate(over="ignore", under="ignore"):
        answer = 440 * 2 ** ((value - 69) / 12)
    if np.any(~np.isfinite(answer)) or np.any(answer <= 0):
        raise ValueError("Key is outside the representable frequency range")
    return float(answer) if answer.ndim == 0 else answer


class _Detector:
    def __init__(self, config):
        self.config = config
        self.size = round(config.window_ms * config.sample_rate / 1000)
        self.window = np.hanning(self.size)
        self.nfft = next_fast_len(4 * self.size)
        self.frequencies = rfftfreq(self.nfft, 1 / config.sample_rate)
        self.min_lag = max(1, math.ceil(config.sample_rate / config.fmax))
        self.max_lag = min(self.size - 2, math.floor(config.sample_rate / config.fmin))
        # Original window, not zero-padded FFT, sets physical spectral resolution.
        self.bandwidth = max(config.harmonic_bandwidth_hz, 1.5 * config.sample_rate / self.size)

    def detect(self, frame):
        cfg = self.config
        centered = frame - np.mean(frame)
        rms = float(np.sqrt(np.mean(centered**2)))
        rms_db = max(-300.0, 20 * math.log10(max(rms, 1e-15)))
        if rms_db < cfg.min_rms_db:
            return None, None, None, 0.0, 0.0, rms_db, False
        # Normalized square difference/autocorrelation supplies periodicity candidates.
        spectrum = rfft(centered, self.nfft)
        acf = irfft(np.abs(spectrum) ** 2, self.nfft)[: self.size]
        energy = np.concatenate(([0.0], np.cumsum(centered**2)))
        lags = np.arange(self.size)
        denominator = energy[self.size - lags] + energy[-1] - energy[lags]
        nsdf = np.divide(2 * acf, denominator, out=np.zeros_like(acf), where=denominator > 1e-20)
        peaks, _ = find_peaks(nsdf[self.min_lag - 1 : self.max_lag + 2])
        peaks = peaks + self.min_lag - 1
        peaks = peaks[(peaks >= self.min_lag) & (peaks <= self.max_lag)]
        if not len(peaks):
            return None, None, None, 0.0, 0.0, rms_db, False
        best = float(np.max(nsdf[peaks]))
        if best < cfg.min_periodicity:
            return None, None, None, 0.0, max(0.0, best), rms_db, False
        candidates = peaks[nsdf[peaks] >= max(cfg.min_periodicity, 0.9 * best)]
        # Earliest strong periodicity peak avoids selecting integer period multiples.
        lag = int(candidates[0])
        a, b, c = nsdf[lag - 1 : lag + 2]
        divisor = a - 2 * b + c
        adjustment = 0.5 * (a - c) / divisor if abs(divisor) > 1e-15 else 0.0
        frequency = float(cfg.sample_rate / (lag + np.clip(adjustment, -0.5, 0.5)))
        power = np.abs(rfft(centered * self.window, self.nfft)) ** 2
        power[1:-1] *= 2  # one-sided spectral power
        total = float(np.sum(power))
        if total <= 1e-20:
            return None, None, None, 0.0, best, rms_db, False
        mask = np.zeros(len(power), dtype=bool)
        width = min(self.bandwidth, 0.35 * frequency)
        for harmonic in range(1, cfg.harmonics + 1):
            target = harmonic * frequency
            if target >= cfg.sample_rate / 2:
                break
            left = np.searchsorted(self.frequencies, target - width)
            right = np.searchsorted(self.frequencies, target + width, side="right")
            mask[left:right] = True
        ratio = float(np.clip(np.sum(power[mask]) / total, 0, 1))
        band = power[(self.frequencies >= cfg.fmin) & (self.frequencies <= cfg.sample_rate / 2)]
        flatness = float(np.exp(np.mean(np.log(band + 1e-30))) / (np.mean(band) + 1e-30))
        fractional = frequency_to_key(frequency)
        key = int(np.floor(fractional + 0.5))
        accepted = (
            cfg.fmin <= frequency <= cfg.fmax
            and ratio >= cfg.min_energy_ratio
            and flatness <= cfg.max_flatness
        )
        return frequency, key, fractional, ratio, min(1.0, best), rms_db, bool(accepted)


def segment_frames(frames, min_frames=8):
    """Backdate accepted runs to their first frame; invalid frames always end a run."""
    if isinstance(min_frames, bool) or not isinstance(min_frames, int) or min_frames < 1:
        raise ValueError("min_frames must be a positive integer")
    segments = []
    run = []

    def close():
        if len(run) >= min_frames:
            duration = run[-1].end - run[0].start
            weights = np.array([f.end - f.start for f in run])
            segments.append(
                Segment(
                    run[0].key,
                    run[0].start,
                    run[-1].end,
                    duration,
                    float(np.average([f.energy_ratio for f in run], weights=weights)),
                    float(np.average([f.fractional_key for f in run], weights=weights)),
                    len(run),
                )
            )

    for frame in frames:
        if run and (
            not frame.accepted
            or frame.key != run[-1].key
            or not math.isclose(frame.start, run[-1].end, abs_tol=1e-8)
        ):
            close()
            run = []
        if frame.accepted:
            run.append(frame)
    close()
    return segments


def _analyze(prepared, config, source):
    samples, duration, warnings, metadata = prepared
    detector = _Detector(config)
    hop = round(config.sample_rate * config.hop_ms / 1000)
    frames = []
    for start in range(0, len(samples), hop):
        time = start / config.sample_rate
        if time >= duration:
            break
        chunk = samples[start : start + detector.size]
        if len(chunk) < detector.size:
            chunk = np.pad(chunk, (0, detector.size - len(chunk)))
        frequency, key, fractional, ratio, periodicity, rms_db, accepted = detector.detect(chunk)
        frames.append(
            Frame(
                time,
                min((start + hop) / config.sample_rate, duration),
                frequency,
                key,
                fractional,
                ratio,
                periodicity,
                rms_db,
                accepted,
            )
        )
    segments = segment_frames(frames, config.min_frames)
    if not segments:
        warnings.append("No stable detections; means and hoarseness are undefined (null)")
    metadata.update(
        {
            "version": "0.1.0",
            "detector": "nsdf-harmonic-v1",
            "effective_hop_ms": 1000 * hop / config.sample_rate,
            "effective_window_ms": 1000 * detector.size / config.sample_rate,
            "nominal_minimum_run_ms": 1000 * hop * config.min_frames / config.sample_rate,
            "key_numbering": "MIDI: A4=69; piano-key index = MIDI-20",
            "frame_count": len(frames),
        }
    )
    return AnalysisResult(
        source,
        compute_metrics(segments, duration, config.reference_key),
        segments,
        frames,
        config.to_dict(),
        metadata,
        warnings,
    )


def analyze_samples(samples, sample_rate, config=None, *, source="<array>"):
    """Analyze mono/stereo PCM arrays. Integer PCM is scaled to floating PCM units."""
    config = config or AnalysisConfig()
    return _analyze(prepare_audio(samples, sample_rate, config), config, source)


def analyze_file(path, config=None):
    """Decode a supported audio file and return all metrics, segments and frames."""
    config = config or AnalysisConfig()
    return _analyze(load_audio(path, config), config, str(path))
