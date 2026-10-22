import json
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf

from phonipy import (
    AnalysisConfig,
    AudioError,
    analyze_directory,
    analyze_file,
    analyze_samples,
    parser,
)
from phonipy.audio import prepare_audio
from phonipy.cli import main


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "voice.WAV"
    sf.write(path, 0.4 * np.sin(2 * np.pi * 220 * np.arange(16000) / 16000), 16000)
    return path


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sample_rate": 100},
        {"sample_rate": True},
        {"min_frames": 0},
        {"min_frames": 1.5},
        {"harmonics": 129},
        {"hop_ms": 0},
        {"hop_ms": 0.0001},
        {"window_ms": 1},
        {"fmin": 0},
        {"fmax": 10000},
        {"channel": "bad"},
        {"nonfinite": "bad"},
        {"min_periodicity": 2},
        {"min_energy_ratio": -1},
        {"max_flatness": float("nan")},
        {"min_rms_db": 1},
        {"max_duration": 0},
        {"harmonic_bandwidth_hz": 0},
    ],
)
def test_config_invalid(kwargs):
    with pytest.raises(ValueError):
        AnalysisConfig(**kwargs)


def test_presets_and_json(tmp_path):
    for name in ["general", "low", "high", "speech", "singing"]:
        assert AnalysisConfig.preset(name).min_frames == 8
    with pytest.raises(ValueError):
        AnalysisConfig.preset("missing")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(AnalysisConfig().to_dict()))
    assert AnalysisConfig.from_json(path) == AnalysisConfig()
    path.write_text('{"unknown": 1}')
    with pytest.raises(TypeError):
        AnalysisConfig.from_json(path)


@pytest.mark.parametrize(
    "data,rate",
    [
        ([], 16000),
        ([1], 1),
        ([1], True),
        ([1], 16000.5),
        ([1j], 16000),
        (["bad"], 16000),
        (np.zeros((2, 2, 2)), 16000),
        (np.zeros((2, 0)), 16000),
        ([float("nan")], 16000),
        ([float("inf")], 16000),
        ([10.0], 16000),
    ],
)
def test_bad_audio(data, rate):
    with pytest.raises(AudioError):
        analyze_samples(data, rate)


def test_repairs_and_channels():
    cfg = AnalysisConfig(nonfinite="zero")
    assert analyze_samples([float("nan"), float("inf")], 16000, cfg).warnings
    for channel in ["left", "right", "mix", "loudest"]:
        assert (
            analyze_samples(
                np.zeros((160, 2)), 16000, AnalysisConfig(channel=channel)
            ).metrics.breakouts
            == 0
        )
    with pytest.raises(AudioError):
        analyze_samples(np.zeros(160), 16000, AnalysisConfig(channel="right"))
    with pytest.raises(AudioError):
        analyze_samples(np.zeros((160, 1)), 16000, AnalysisConfig(channel="right"))
    with pytest.raises(AudioError):
        analyze_samples(np.zeros(16000), 16000, AnalysisConfig(max_duration=0.1))
    with pytest.raises(AudioError):
        analyze_samples(np.zeros(16000), 1000)


def test_integer_pcm():
    for data in [np.zeros(160, dtype=np.int16), np.full(160, 128, dtype=np.uint8)]:
        assert analyze_samples(data, 16000).metrics.breakouts == 0
    x, _, _, _ = prepare_audio(np.array([-32768, 32767], dtype=np.int16), 16000, AnalysisConfig())
    assert x[0] == -1


def test_file_batch_exports_and_errors(audio, tmp_path):
    broken = tmp_path / "broken.wav"
    broken.write_text("not audio")
    batch = analyze_directory(tmp_path)
    assert len(batch.results) == len(batch.errors) == 1
    assert batch.errors[0]["type"] == "AudioError"
    for extension in ["json", "csv", "xlsx"]:
        path = batch.save(tmp_path / f"results.{extension}")
        assert path.stat().st_size > 10
    assert json.loads((tmp_path / "results.json").read_text())["errors"]
    with pytest.raises(AudioError):
        analyze_directory(tmp_path, strict=True)
    with pytest.raises(ValueError):
        batch.save(tmp_path / "bad.abc")
    with pytest.raises(AudioError):
        analyze_file(tmp_path / "missing.wav")
    with pytest.raises(AudioError):
        analyze_file(audio, AnalysisConfig(max_duration=0.1))
    with pytest.raises(ValueError):
        analyze_directory(tmp_path / "missing")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        analyze_directory(empty)


def test_recursive_and_progress(audio, tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    sf.write(nested / "x.flac", np.zeros(1000), 16000)
    calls = []
    result = analyze_directory(tmp_path, recursive=True, progress=lambda *a: calls.append(a))
    assert len(result.results) == len(calls) == 2
    assert calls[-1][:2] == (2, 2)


def test_dataframe_parser(audio, tmp_path):
    table = parser(tmp_path, metrics=["source", "valid_time"], save_path=str(tmp_path / "summary"))
    assert list(table.columns) == ["source", "valid_time"]
    with pytest.raises(ValueError):
        parser(tmp_path, metrics=["oops"])
    with pytest.raises(ValueError):
        parser(tmp_path, output_format="bad")


def test_cli(audio, tmp_path):
    output = tmp_path / "out.csv"
    details = tmp_path / "details"
    assert (
        main(
            [
                str(audio),
                "-o",
                str(output),
                "--details",
                str(details),
                "--plot",
                "--reference-key",
                "57",
            ]
        )
        == 0
    )
    assert list(details.glob("*.png"))
    assert list(details.glob("*-frames.csv"))
    assert main([str(tmp_path / "missing.wav")]) == 2
    assert main([str(audio), "-o", str(tmp_path / "out.bad")]) == 2
    (tmp_path / "bad.wav").write_text("broken")
    assert main([str(tmp_path), "-o", str(tmp_path / "out.json")]) == 1
    with pytest.raises(SystemExit):
        main([str(audio), "--plot"])
    with pytest.raises(SystemExit):
        main([str(audio), "--preset", "low", "--config", "x"])
    completed = subprocess.run(
        [sys.executable, "-m", "phonipy", "--version"], capture_output=True, text=True
    )
    assert completed.returncode == 0
    from phonipy import __version__

    assert __version__ in completed.stdout


def test_analysis_never_saves_implicitly(audio, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))
    table = parser(tmp_path)
    assert not table.empty
    assert set(tmp_path.rglob("*")) == before
    assert main([str(audio)]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["results"][0]["metrics"]["breakouts"] == 1
    assert "No files saved" in output.err
    assert set(tmp_path.rglob("*")) == before
