"""Explicit, serializable detector settings. Note indices use MIDI numbering (A4=69)."""

import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class AnalysisConfig:
    sample_rate: int = 16000
    hop_ms: float = 17.25
    window_ms: float = 69.0
    min_frames: int = 8
    fmin: float = 65.0
    fmax: float = 1100.0
    reference_key: float = 69.0
    harmonics: int = 12
    min_rms_db: float = -60.0
    min_periodicity: float = 0.65
    min_energy_ratio: float = 0.15
    max_flatness: float = 0.6
    harmonic_bandwidth_hz: float = 22.0
    channel: str = "loudest"
    nonfinite: str = "error"
    max_duration: float = 3600.0

    def __post_init__(self):
        for name in ("sample_rate", "min_frames", "harmonics"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name, value in asdict(self).items():
            if isinstance(value, (float, int)) and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 4000 <= self.sample_rate <= 192000:
            raise ValueError("sample_rate must be between 4000 and 192000 Hz")
        if not 0 < self.hop_ms <= self.window_ms <= 500:
            raise ValueError("Require 0 < hop_ms <= window_ms <= 500")
        if round(self.hop_ms * self.sample_rate / 1000) < 1:
            raise ValueError("hop_ms is shorter than one sample")
        if not 20 <= self.fmin < self.fmax < self.sample_rate / 2:
            raise ValueError("Require 20 <= fmin < fmax < Nyquist frequency")
        if self.window_ms / 1000 * self.fmin < 2:
            raise ValueError("window_ms must contain at least two cycles at fmin")
        for name in ("min_periodicity", "min_energy_ratio", "max_flatness"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if not -160 <= self.min_rms_db <= 0:
            raise ValueError("min_rms_db must be between -160 and 0 dBFS")
        if self.harmonic_bandwidth_hz <= 0 or self.max_duration <= 0:
            raise ValueError("Bandwidth and max_duration must be positive")
        if self.harmonics > 128:
            raise ValueError("harmonics must not exceed 128")
        if self.channel not in ("loudest", "mix", "left", "right"):
            raise ValueError("channel must be loudest, mix, left or right")
        if self.nonfinite not in ("error", "zero"):
            raise ValueError("nonfinite must be error or zero")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_json(cls, path):
        """Reject unknown fields and invalid values instead of guessing."""
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def preset(cls, name="general", **overrides):
        """Task/range presets; ranges describe pitch, not a person's sex."""
        presets = {
            "general": {},
            "low": {"fmin": 50.0, "fmax": 500.0, "window_ms": 86.25},
            "high": {"fmin": 130.0, "fmax": 1400.0},
            "speech": {"fmin": 65.0, "fmax": 600.0},
            "singing": {"fmin": 50.0, "fmax": 1600.0, "window_ms": 86.25},
        }
        if name not in presets:
            raise ValueError(f"Unknown preset {name!r}; choose {', '.join(presets)}")
        return replace(cls(**presets[name]), **overrides)
