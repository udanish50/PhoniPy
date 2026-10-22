from dataclasses import replace

import pytest

from phonipy import Segment, compute_metrics


def segment(start=0, end=1, energy=0.8, key=69.25):
    return Segment(69, start, end, end - start, energy, key, 58)


def test_all_ten_metrics_by_hand():
    actual = compute_metrics([segment(1, 3, 0.8, 69.5), segment(4, 5, 0.5, 68.5)], 6, 69)
    assert actual.raw_duration == 6
    assert actual.active_time == 4
    assert actual.valid_time == 3
    assert actual.average_offset == 0
    assert actual.average_energy == pytest.approx(0.7)
    assert actual.hoarseness == pytest.approx(30)
    assert actual.average_duration == 1.5
    assert actual.continuity == 0.5
    assert actual.sparsity == 0.75
    assert actual.breakouts == 2


def test_empty_is_undefined_not_hoarse():
    metrics = compute_metrics([], 3)
    assert metrics.valid_time == metrics.active_time == metrics.breakouts == 0
    assert metrics.average_energy is metrics.hoarseness is metrics.average_duration is None
    assert metrics.average_offset is None
    assert metrics.continuity == metrics.sparsity == 0


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf")])
def test_bad_duration(duration):
    with pytest.raises(ValueError):
        compute_metrics([], duration)


@pytest.mark.parametrize(
    "segments",
    [
        [segment(0, 2), segment(1, 3)],
        [segment(-1, 1)],
        [segment(0, 4)],
        [segment(0, 1, 2)],
        [replace(segment(), duration=0.5)],
        [replace(segment(), mean_fractional_key=float("nan"))],
    ],
)
def test_invalid_segments(segments):
    with pytest.raises(ValueError):
        compute_metrics(segments, 3)


def test_missing_reference():
    with pytest.raises(ValueError):
        compute_metrics([], 1, float("nan"))


def test_signed_offsets_unweighted_by_segment_length():
    assert compute_metrics([segment(0, 2, key=70), segment(2, 3, key=68)], 3).average_offset == 0
