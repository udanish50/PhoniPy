"""Plain data structures with JSON-safe, explicit missing measurements."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Frame:
    start: float
    end: float
    frequency: float | None
    key: int | None
    fractional_key: float | None
    energy_ratio: float
    periodicity: float
    rms_db: float
    accepted: bool


@dataclass(frozen=True)
class Segment:
    key: int
    start: float
    end: float
    duration: float
    mean_energy: float
    mean_fractional_key: float
    frame_count: int


@dataclass(frozen=True)
class Metrics:
    raw_duration: float
    active_time: float
    valid_time: float
    average_offset: float | None
    average_energy: float | None
    hoarseness: float | None
    average_duration: float | None
    continuity: float
    sparsity: float
    breakouts: int


@dataclass
class AnalysisResult:
    source: str
    metrics: Metrics
    segments: list[Segment]
    frames: list[Frame]
    config: dict
    metadata: dict
    warnings: list[str] = field(default_factory=list)

    def to_dict(self, include_frames=False):
        result = asdict(self)
        if not include_frames:
            result.pop("frames")
        return result

    def to_json(self, path=None, include_frames=False):
        value = json.dumps(self.to_dict(include_frames), indent=2, allow_nan=False)
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(value + "\n", encoding="utf-8")
        return value

    def plot(self, path=None):
        from .plotting import composite_plot

        return composite_plot(self, path)
