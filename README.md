# PhoniPy

Reproducible musical-note stability and harmonic-purity analysis for solo voice recordings.
PhoniPy reads audio, detects stable note intervals, computes all ten parameters from
*Musical-Key Stability Analysis of Continuous Voice*, and exports recording summaries,
frame data, segment data, and composite plots.

**Research software, version 0.1.0.** The detector is an explicitly documented implementation
of the manuscript's framework, not a verified reproduction of its unavailable prototype.
The manuscript's clinical claims and thresholds are not validated by this package.

## Install

```bash
pip install phonipy
# Optional exports, plots, dashboard:
pip install 'phonipy[excel,plot,app]'
```

Python 3.10 or newer. Core dependencies: NumPy, SciPy, and SoundFile/libsndfile.
WAV, FLAC, OGG, AIFF and other libsndfile-supported formats are accepted. MP3 support
depends on the installed libsndfile build; unsupported codecs produce a per-file error.
For compressed video/audio containers such as M4A, convert to PCM WAV first.

## Python API

```python
from phonipy import AnalysisConfig, analyze_file, analyze_directory

config = AnalysisConfig.preset("speech", reference_key=57)  # A3, MIDI numbering
result = analyze_file("voice.wav", config)
print(result.metrics)
result.to_json("voice-results.json", include_frames=True)
result.plot("voice-composite.png")  # requires phonipy[plot]

batch = analyze_directory("recordings", config, recursive=True)
batch.save("results.csv")  # also JSON or XLSX; failures are retained
print(batch.errors)
```

The package also accepts NumPy arrays with `analyze_samples(samples, sample_rate, config)`.
Arrays use samples-by-channels order; integer PCM is scaled automatically. Floating PCM
should be approximately within -1 to 1. No automatic gain normalization is performed.

### Familiar midipy-style batch API

```python
from phonipy import parser

table = parser(
    "recordings",
    metrics=["source", "valid_time", "average_energy", "breakouts"],
    output_format="csv",
    save_path="VoiceOutput",
)
```

`parser` requires pandas (included with `phonipy[app]`). `metrics` selects returned DataFrame
columns; the saved analysis summary always retains all ten metrics and failures for auditing.
Prefer the core batch API when pandas is not needed. No outputs are created by analysis
functions until an explicit save/export call.

## Command line

```bash
phonipy voice.wav -o result.json --reference-key 57 --details details --plot
phonipy recordings -o results.csv --recursive --preset speech
python -m phonipy recordings -o results.xlsx --config examples/config.json
```

Exit codes: **0** complete success, **1** batch completed with failed files, **2** invalid
input/settings/output or a single-file failure. Batch processing continues after corrupt
files by default; `--strict` stops on the first failure. JSON includes settings, warnings,
and failures; CSV/XLSX include failure rows plus a `.metadata.json` sidecar. `--details`
adds full JSON and frame/segment CSVs. Duplicate filenames receive distinct numeric prefixes.

## Local dashboard

```bash
pip install 'phonipy[app]'
streamlit run "$(python -c 'import phonipy.app; print(phonipy.app.__file__)')"
```

Upload multiple files, adjust settings, view composite plots, and download CSV/JSON.
Analysis runs locally without uploads to an analysis service or telemetry from PhoniPy.
The dashboard limits each recording to five minutes and 100 MB.

## The ten metrics

Let `d_i = end_i - start_i` for each valid stable-note segment; `N` is the segment count.

| Metric | Definition | Unit |
| --- | --- | --- |
| `raw_duration` | Original sample count / original sample rate | s |
| `active_time` | Last valid offset − first valid onset | s |
| `valid_time` | Sum of valid segment durations | s |
| `average_offset` | Unweighted segment mean of fractional pitch − reference note | semitones |
| `average_energy` | Duration-weighted harmonic-energy ratio across valid intervals | 0–1 |
| `hoarseness` | `(1 - average_energy) * 100` | % |
| `average_duration` | `valid_time / N` | s |
| `continuity` | `average_duration / valid_time` | dimensionless |
| `sparsity` | `valid_time / active_time` | 0–1 |
| `breakouts` | `N`, including the initial acquisition | count |

No valid detections: time totals, breakouts, continuity and sparsity are zero; undefined
means and hoarseness are `null` in JSON and blank in CSV/XLSX. **Continuity equals `1/N`**
whenever N > 0; it is retained exactly as specified, not presented as an independent metric.
The manuscript uses two inconsistent descriptions of breakouts; this package follows
Appendix A's segment count. Signed pitch offsets can cancel. `hoarseness` is the manuscript's
name for an acoustic residual-energy transform, not a clinical hoarseness rating.

## Detector and reproducibility

- Default analysis rate: 16 kHz; hop: 17.25 ms (276 samples); Hann window: 69 ms.
- Normalized autocorrelation supplies candidate periods; the earliest sufficiently strong
  local peak is refined with parabolic interpolation. This makes the fundamental candidate
  stage explicit where the manuscript only says "strongest harmonic series."
- Harmonic-series energy is measured from a one-sided Hann-windowed power spectrum in
  nonoverlapping frequency bands around up to 12 harmonics; total energy includes all bins.
- RMS, periodicity, spectral flatness, pitch range, and harmonic ratio gate detections.
- The identical rounded MIDI note must persist for at least eight frames. Accepted runs are
  backdated to their first frame, not the eighth. Invalid/unvoiced frames end a run.
- Each frame represents a hop interval. Durations use disjoint intervals and the last interval
  is clipped to the original duration. Forward-looking windows are zero-padded at the end.
  Overlapping spectral windows do not create overlapping measured durations.
- Fractional pitch is retained separately for pitch offset. A4=440 Hz is MIDI note 69;
  traditional 88-key piano index = MIDI number minus 20. Differences are identical.
- All effective settings, sample rates, channel selection, and warnings are exported.

See [methodology](docs/methodology.md) for equations and limitations.

## Input handling and limits

Stereo/multichannel recordings select the loudest channel by default to avoid phase cancellation.
Choose `channel="mix"`, `"left"`, or `"right"` explicitly if desired. Resampling is polyphase.
NaN/infinite samples raise an error unless `nonfinite="zero"` explicitly enables replacement.
Empty/corrupt inputs, absent channels, invalid ranges, unavailable codecs, and excessive
durations produce actionable errors. Clipping/DC offset and short input produce warnings.
The default one-hour duration cap is configurable. Audio and frame results are held in memory;
split very large recordings into tasks. Output failures are surfaced rather than silently ignored.

Use quiet, solo voice recordings with consistent microphones and levels. Stable vowels and
single-note holds are the clearest tasks. Speech has natural unvoiced intervals and singing
has intentional pitch changes; their scores should not be directly compared with vowel scores.
Noise, reverberation, vibrato, note-boundary quantization, and octave errors can affect results.
No automatic recovery can reconstruct information absent from a recording.

## Tests and benchmarks

```bash
pip install -e '.[test,app,benchmark]'
pytest --cov=phonipy --cov-report=term-missing
ruff check .
python benchmarks/download.py --data-dir benchmarks/data
python benchmarks/run.py --data-dir benchmarks/data --output benchmarks/results
python -m build
python -m twine check dist/*
```

The benchmark scripts analyze synthetic signals with known pitch/timing, all 3,000 recordings
in a pinned Free Spoken Digit Dataset snapshot, and all 208 VOICED sustained-vowel records.
They record source hashes, settings, dependency versions, wall time, failures, and per-file metrics.
Real recordings have no ground-truth values for these novel metrics: those runs demonstrate
processing coverage, not clinical accuracy or disease classification.
See [benchmark protocol](benchmarks/README.md) and [results](docs/benchmark-results.md).

## Attribution and license

Implementation: Muhammad Umair Danish. Scientific framework: the user-supplied manuscript
*Musical-Key Stability Analysis of Continuous Voice: A Methodology for Quantifying Phonatory
Continuity and Purity in Neurological Disorders with Applications in Music Therapy*, by
Demian Kogutek and Danish Umair Muhammad. The manuscript itself is not redistributed.

Code: MIT. Benchmark recordings retain their upstream licenses and are not bundled in
the wheel/source distribution. See the benchmark protocol for dataset citations.
