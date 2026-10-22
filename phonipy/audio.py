"""Audio decoding and explicit input quality handling."""

from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .config import AnalysisConfig


class AudioError(ValueError):
    """A recording cannot be decoded or analyzed safely."""


def prepare_audio(samples, sample_rate, config: AnalysisConfig):
    if (
        isinstance(sample_rate, bool)
        or not isinstance(sample_rate, (int, np.integer))
        or not 1000 <= sample_rate <= 384000
    ):
        raise AudioError("sample_rate must be an integer between 1000 and 384000 Hz")
    data = np.asarray(samples)
    if data.ndim not in (1, 2) or data.size == 0 or (data.ndim == 2 and data.shape[1] == 0):
        raise AudioError("Audio must be a nonempty samples or samples-by-channels array")
    if data.dtype.kind not in "fiu":
        raise AudioError("Audio samples must be real numeric values")
    if len(data) / sample_rate > config.max_duration:
        raise AudioError(f"Recording exceeds max_duration={config.max_duration} seconds")
    if data.dtype.kind in "iu":
        info = np.iinfo(data.dtype)
        if data.dtype.kind == "u":
            midpoint = (int(info.max) + 1) / 2
            data = (data.astype(np.float64) - midpoint) / midpoint
        else:
            data = data.astype(np.float64) / max(abs(int(info.min)), int(info.max))
    else:
        data = data.astype(np.float64, copy=True)
    warnings = []
    if not np.isfinite(data).all():
        if config.nonfinite == "error":
            raise AudioError("Audio contains NaN or infinity; use nonfinite='zero' to repair")
        data[~np.isfinite(data)] = 0
        warnings.append("Nonfinite samples replaced with zero by explicit configuration")
    if np.max(np.abs(data)) > 8:
        raise AudioError("Floating audio must use normalized PCM units (approximately -1 to 1)")
    if np.any(np.abs(data) >= 0.999):
        warnings.append("Samples approach/exceed full scale; clipping may affect measurements")
    channels = 1 if data.ndim == 1 else data.shape[1]
    selected = None
    if data.ndim == 2:
        if config.channel == "mix":
            data = data.mean(axis=1)
        else:
            selected = (
                int(np.argmax(np.mean(data**2, axis=0)))
                if config.channel == "loudest"
                else int(config.channel == "right")
            )
            if selected >= channels:
                raise AudioError("Requested right channel is absent")
            data = data[:, selected]
        if channels > 1:
            warnings.append(f"Multichannel input: {config.channel} channel policy applied")
    elif config.channel == "right":
        raise AudioError("Requested right channel is absent")
    duration = len(data) / sample_rate
    if abs(np.mean(data)) > 0.01:
        warnings.append("DC offset detected; each analysis frame is mean-centered")
    if sample_rate / 2 <= config.fmax:
        raise AudioError("Input Nyquist frequency must exceed configured fmax")
    if sample_rate != config.sample_rate:
        divisor = gcd(int(sample_rate), config.sample_rate)
        data = resample_poly(data, config.sample_rate // divisor, int(sample_rate) // divisor)
    if len(data) < round(config.window_ms * config.sample_rate / 1000):
        warnings.append("Input is shorter than one analysis window; zero-padding applied")
    return (
        data,
        duration,
        warnings,
        {
            "original_sample_rate": int(sample_rate),
            "analysis_sample_rate": config.sample_rate,
            "channels": channels,
            "selected_channel": selected,
            "sample_count": len(samples),
        },
    )


def load_audio(path, config):
    path = Path(path)
    if not path.is_file():
        raise AudioError(f"Audio file does not exist: {path}")
    try:
        with sf.SoundFile(path) as handle:
            if handle.frames / handle.samplerate > config.max_duration:
                raise AudioError(f"Recording exceeds max_duration={config.max_duration} seconds")
            samples = handle.read(dtype="float64", always_2d=True)
            rate = handle.samplerate
    except AudioError:
        raise
    except (sf.LibsndfileError, OSError, ValueError) as exc:
        raise AudioError(f"Cannot decode {path.name}: {exc}") from exc
    return prepare_audio(samples, rate, config)
