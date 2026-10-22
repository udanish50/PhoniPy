import json
from dataclasses import replace

import numpy as np
import pytest

from phonipy import AnalysisConfig, Frame, analyze_samples, frequency_to_key, key_to_frequency
from phonipy.analysis import segment_frames


def tone(frequency=220, duration=1, rate=16000, harmonics=1):
    time = np.arange(round(rate * duration)) / rate
    signal = sum(np.sin(2 * np.pi * frequency * n * time) / n for n in range(1, harmonics + 1))
    return 0.5 * signal / np.max(np.abs(signal))


@pytest.mark.parametrize("frequency", [82.4069, 110, 130.8128, 220, 261.6256, 440, 880])
@pytest.mark.parametrize("harmonics", [1, 5])
def test_known_pitches(frequency, harmonics):
    result = analyze_samples(tone(frequency, harmonics=harmonics), 16000)
    assert result.metrics.valid_time > 0.8
    assert abs(result.metrics.average_offset - (frequency_to_key(frequency) - 69)) < 0.08
    assert result.metrics.average_energy > 0.9
    assert result.metrics.breakouts == 1
    assert 0 <= result.metrics.sparsity <= 1


def test_missing_fundamental():
    t = np.arange(16000) / 16000
    x = 0.2 * (
        np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 660 * t) + np.sin(2 * np.pi * 880 * t)
    )
    result = analyze_samples(x, 16000)
    assert result.segments[0].key == 57  # 220 Hz fundamental


def test_noise_rejected_and_purity_degrades():
    rng = np.random.default_rng(42)
    signal = tone(harmonics=5)
    clean = analyze_samples(signal, 16000)
    noisy = analyze_samples(signal + rng.normal(0, 0.07, len(signal)), 16000)
    noise = analyze_samples(rng.normal(0, 0.1, len(signal)), 16000)
    assert noisy.metrics.average_energy < clean.metrics.average_energy
    assert noise.metrics.breakouts == 0


def test_silence_short_and_dc():
    for data in [np.zeros(16000), np.zeros(1), np.ones(16000) * 0.1]:
        result = analyze_samples(data, 16000)
        assert result.metrics.breakouts == 0
        json.loads(result.to_json(include_frames=True))


@pytest.mark.parametrize("rate", [8000, 22050, 44100, 48000])
def test_resampling(rate):
    result = analyze_samples(tone(rate=rate), rate)
    assert result.metrics.raw_duration == 1
    assert abs(result.metrics.average_offset + 12) < 0.05


def test_stereo_antiphase_does_not_cancel_by_default():
    mono = tone()
    result = analyze_samples(np.column_stack([mono, -mono]), 16000)
    assert result.metrics.valid_time > 0.8
    assert result.metadata["selected_channel"] == 0
    mixed = analyze_samples(np.column_stack([mono, -mono]), 16000, AnalysisConfig(channel="mix"))
    assert mixed.metrics.valid_time == 0


def test_hop_minimum_and_backdated_onset():
    frames = [
        Frame(i * 0.01725, (i + 1) * 0.01725, 440, 69, 69.1, 0.9, 1, -10, True) for i in range(8)
    ]
    assert segment_frames(frames[:7]) == []
    segments = segment_frames(frames)
    assert segments[0].start == 0
    assert segments[0].end == pytest.approx(0.138)
    assert segments[0].frame_count == 8
    assert len(segment_frames(frames + [replace(frames[-1], accepted=False)])) == 1
    with pytest.raises(ValueError):
        segment_frames(frames, 0)


def test_key_change_and_invalid_frame_split():
    frames = [
        Frame(
            i * 0.01725,
            (i + 1) * 0.01725,
            440,
            69 if i < 8 else 70,
            69 if i < 8 else 70,
            0.9,
            1,
            -10,
            i != 16,
        )
        for i in range(25)
    ]
    assert len(segment_frames(frames)) == 3


def test_timing_bounds_and_repeatability():
    data = np.concatenate([tone(duration=0.5), np.zeros(8000), tone(330, 0.5)])
    a = analyze_samples(data, 16000)
    b = analyze_samples(data, 16000)
    assert a.to_dict(True) == b.to_dict(True)
    assert a.metrics.breakouts == 2
    assert a.metrics.valid_time <= a.metrics.active_time <= a.metrics.raw_duration
    assert all(f.end <= 1.5 for f in a.frames)


def test_conversion():
    assert frequency_to_key(440) == 69
    assert key_to_frequency(69) == 440
    assert np.allclose(key_to_frequency(frequency_to_key([220, 440])), [220, 440])
    for value in [0, -1, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            frequency_to_key(value)
    for value in [float("nan"), 1e9]:
        with pytest.raises(ValueError):
            key_to_frequency(value)
