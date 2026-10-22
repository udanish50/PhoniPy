# PhoniPy

**Private voice analysis for the browser and Python.**

PhoniPy measures musical-note stability, harmonic energy, and vocal continuity from solo
voice recordings. Its responsive workspace combines immediate audio playback, a waveform
preview, linked pitch and energy timelines, and ten clearly defined measurements.

[Open the voice-analysis workspace](https://umairdanish.com/software/phonipy/) ·
[Python package](https://pypi.org/project/phonipy/) ·
[Technical specification](https://github.com/udanish50/PhoniPy/blob/main/docs/methodology.md)

## Install and open

```bash
pip install --upgrade phonipy
phonipy app
```

The package includes the complete interface. No dashboard framework, account, or additional
app installation is required. `phonipy app --no-open` prints a local address without opening
a browser; `--port 8080` selects a port explicitly.

## A private workspace

- Recordings play immediately after selection, before analysis.
- The web interface computes entirely on your device, in a background browser worker.
- Audio and measurements remain in transient memory. There is no saved history, database,
  application telemetry, or automatic export.
- **Clear all**, **Clear workspace**, or closing the tab discards the current workspace.
- CSV and JSON reports are downloaded only when you explicitly choose a download action.
- The local Python launcher serves static interface assets and rejects upload requests.

Browser playback and decoding depend on the browser's installed codecs. PCM WAV is the most
portable input. The interface accepts up to ten recordings, five minutes per file, 100 MB per
file, and 150 MB per batch. Corrupt, empty, unsupported, and excessively long recordings
receive actionable messages without stopping other files in the batch.

## Python API

Python 3.10 or newer. Core dependencies are NumPy, SciPy, and SoundFile.

```python
from dataclasses import asdict
from phonipy import AnalysisConfig, analyze_file, analyze_directory

settings = AnalysisConfig.preset("speech", reference_key=57)  # A3
recording = analyze_file("voice.wav", settings)
print(asdict(recording.metrics))

batch = analyze_directory("recordings", settings, recursive=True)
print(batch.to_json())
print(batch.errors)
```

Analysis returns results in memory. It does not create files. `analyze_samples` also accepts
mono or samples-by-channels NumPy arrays. Integer PCM is scaled automatically; floating PCM
should be approximately within -1 to 1.

### DataFrame interface

```bash
pip install 'phonipy[table]'
```

```python
from phonipy import parser

table = parser("recordings", metrics=["source", "valid_time", "average_energy", "breakouts"])
print(table)
```

`parser` returns a DataFrame without saving it. To request an export explicitly, supply
both `save_path="VoiceOutput"` and `output_format="csv"` (or `"json"` / `"excel"`).

### Explicit exports

```python
recording.to_json("voice-report.json", include_frames=True)
batch.save("recordings.csv")
recording.plot("voice-timeline.png")
```

Install `phonipy[plot]` for Python plots and `phonipy[excel]` for Excel exports. Export methods
write only to destinations supplied by the caller. CSV/Excel exports include error rows
and a settings/metadata sidecar. Recordings are never copied into an output directory.

## Command line

```bash
# Process and print JSON; no files are saved.
phonipy voice.wav --reference-key 57
phonipy recordings --recursive --preset speech

# Save only when an output destination is explicitly requested.
phonipy recordings --output summary.csv
phonipy voice.wav --output report.json --details intervals --plot
```

Exit codes: **0** complete success; **1** batch completed with file errors; **2** invalid
input, settings, output, or a single-file failure. Batch runs isolate file errors by default;
`--strict` stops at the first failed recording. Console summaries go to stderr, leaving
stdout available for machine-readable JSON.

## The ten measurements

| API field | Measurement | Unit |
| --- | --- | --- |
| `raw_duration` | Total recording duration | seconds |
| `active_time` | First stable onset to final stable offset | seconds |
| `valid_time` | Total duration of stable intervals | seconds |
| `average_offset` | Mean segment pitch minus the reference note | semitones |
| `average_energy` | Duration-weighted harmonic-series / total energy | 0–1 |
| `hoarseness` | Residual-energy transform: `(1 − average_energy) × 100` | % |
| `average_duration` | Mean stable-interval duration | seconds |
| `continuity` | Mean interval duration / total stable time | dimensionless |
| `sparsity` | Stable time / active span | 0–1 |
| `breakouts` | Stable-interval count, including the first acquisition | count |

No qualifying intervals: extent/count metrics are zero and undefined means are `null`.
The interface displays undefined measurements as a dash. Continuity equals `1 / breakouts`
when detections exist; signed pitch offsets can cancel. The named hoarseness transform is
an acoustic residual-energy measure, not a perceptual or diagnostic rating.

## Method and configuration

The default detector uses a 16 kHz analysis rate, 69 ms Hann windows, a 17.25 ms hop,
and at least eight consecutive same-note frames. Normalized autocorrelation supplies a
periodic fundamental candidate. A harmonic-series energy ratio and configurable periodicity,
RMS, pitch-range, and flatness gates determine accepted frames. Fractional pitch is retained
for offset calculations; displayed note indices use MIDI numbering, with A4 = 69 = 440 Hz.

Python and browser engines share the `nsdf-harmonic-v2` specification and a radix-two FFT
grid. Cross-runtime tests compare all ten metrics, frame acceptance, pitch, and harmonic
energy on controlled inputs. Browser audio decoding/resampling and Python's libsndfile /
polyphase resampling can introduce small input-dependent differences.

Use `AnalysisConfig` or JSON configuration files for reproducibility. Presets include
`general`, `speech`, `singing`, `low`, and `high`. Stereo selects the loudest channel by
default; `mix`, `left`, and `right` are available. Nonfinite samples are rejected unless
`nonfinite="zero"` explicitly enables replacement. Python's default recording-duration
limit is one hour and can be configured.

[Read the complete methodology](https://github.com/udanish50/PhoniPy/blob/main/docs/methodology.md).

## Interpretation

Sustained vowels and single-note holds provide the clearest interpretation. Intentional
pitch changes, speech consonants, vibrato, microphone noise, and octave errors can affect
stable-note segmentation. Compare recordings with matched tasks, settings, and acquisition
conditions. These measurements are intended for research and acoustic inspection; clinical
validity and diagnostic thresholds have not been established.

## Development

```bash
pip install -e '.[test]'
pytest --cov=phonipy --cov-report=term-missing
ruff check .
python -m build
python -m twine check dist/*
```

Node.js enables the Python/browser numerical conformance tests. CI runs on Windows, Linux,
and macOS with Python 3.10, 3.12, and 3.14. No recordings or computed analysis results are
bundled in the Python distribution.

## Attribution

Developed by **Muhammad Umair Danish**. The measurement framework follows *Musical-Key Stability
Analysis of Continuous Voice: A Methodology for Quantifying Phonatory Continuity and Purity in
Neurological Disorders with Applications in Music Therapy*, by Demian Kogutek and Danish Umair
Muhammad. Implementation choices and edge-case policies are documented in the technical
specification. Code is licensed under MIT.
