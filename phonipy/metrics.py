"""The manuscript's ten global parameters, with undefined means represented by None."""

import math

from .models import Metrics, Segment


def compute_metrics(segments: list[Segment], raw_duration: float, reference_key=69.0):
    if not math.isfinite(raw_duration) or raw_duration < 0:
        raise ValueError("raw_duration must be finite and nonnegative")
    if not math.isfinite(reference_key):
        raise ValueError("reference_key must be finite")
    previous_end = 0.0
    for segment in segments:
        values = (
            segment.start,
            segment.end,
            segment.duration,
            segment.mean_energy,
            segment.mean_fractional_key,
        )
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Segment values must be finite")
        if (
            segment.start < previous_end - 1e-9
            or segment.end > raw_duration + 1e-9
            or segment.start < 0
            or segment.duration <= 0
            or not math.isclose(
                segment.duration, segment.end - segment.start, rel_tol=1e-8, abs_tol=1e-9
            )
            or not 0 <= segment.mean_energy <= 1
        ):
            raise ValueError("Segments must be ordered, disjoint and inside the recording")
        previous_end = segment.end
    count = len(segments)
    if count == 0:
        return Metrics(raw_duration, 0.0, 0.0, None, None, None, None, 0.0, 0.0, 0)
    valid = math.fsum(s.duration for s in segments)
    active = segments[-1].end - segments[0].start
    energy = math.fsum(s.duration * s.mean_energy for s in segments) / valid
    average = valid / count
    # Unweighted mean across detections, preserving fractional estimated pitch.
    offset = math.fsum(s.mean_fractional_key - reference_key for s in segments) / count
    return Metrics(
        raw_duration,
        active,
        valid,
        offset,
        energy,
        (1 - energy) * 100,
        average,
        average / valid,
        min(1.0, valid / active),
        count,
    )
