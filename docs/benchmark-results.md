# PhoniPy 0.1.0 benchmark results

Run on October 22, 2026, using detector `nsdf-harmonic-v1` and the default exported configuration.
Reference note: MIDI 69 (A4). Real recordings were not pitch-matching tasks; their offsets are relative to this chosen reference, not task accuracy.

| Dataset | Files processed | File errors | With stable detections | No stable detections | Audio seconds | Processing seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Synthetic-v1 | 19 | 0 | 16 | 3 | 38.000 | 10.66 |
| FSDD, full pinned snapshot | 3000 | 0 | 840 | 2160 | 1312.303 | 8.93 |
| VOICED 1.0.0, all records | 208 | 0 | 204 | 4 | 989.400 | 8.06 |

Largest median absolute pitch error across periodic synthetic cases: **3.527 cents**.
Silence, white noise, and DC-only synthetic inputs produced no stable detections. Synthetic tones are engineering tests, not a substitute for natural voice validation.

All 3,208 real recordings processed without file errors. FSDD stable-detection coverage was 28.0%; its short spoken digits frequently do not sustain one quantized note for eight frames. VOICED stable-detection coverage was 98.1%. No-detection recordings retain zero counts/time totals and null means; they are not classified as healthy or abnormal.

Processing seconds include analysis/export overhead and are machine-specific. Synthetic timing additionally includes initial plot/font-cache setup. No clinical cutoffs, sensitivity/specificity, or ground-truth real-recording pitch accuracy are established by these runs.

## Verification

- 78 automated tests passed locally with 98% statement coverage, including browser-app upload and failure paths.
- All 78 tests also passed against the built wheel in a clean Python 3.12 environment outside the source checkout.
- Nine GitHub CI jobs passed: Ubuntu, Windows, and macOS, each on Python 3.10, 3.12, and 3.14.
- CI includes lint, tests, wheel/source builds, and Twine package validation.
- Live-browser upload, analysis, plot display, and download-control availability were verified.
- No PyPI credentials are stored in the repository or distribution.
- The tested core is commit `d659ddf66ec61b35d55647cb4151875ceac1e297`; subsequent changes add benchmark downloader/provenance/reporting only.

[Successful CI run](https://github.com/udanish50/PhoniPy/actions/runs/39807717757).

## Reproducibility files

- [Aggregate counts, runtime, environment, configuration and result hashes](benchmark-summary.json)
- Detailed per-recording tables and source provenance were delivered locally to the project owner. They are not redistributed in this repository or package.
- Reproduce detailed results locally with the scripts in `benchmarks/`; generated files are ignored by Git by default.

## Data attribution

FSDD: Jakobovski and contributors, [Free Spoken Digit Dataset](https://github.com/Jakobovski/free-spoken-digit-dataset), commit `26eb9aaf76e81b692f806f9140c2d2777410d7a1`, CC BY-SA 4.0.
VOICED: Cesari and colleagues, [VOICED Database 1.0.0](https://physionet.org/content/voiced/1.0.0/), DOI [10.13026/C25Q2N](https://doi.org/10.13026/C25Q2N), Open Data Commons Attribution License v1.0. All signal/header checksums matched the official manifest.
Benchmark tables are derived numerical outputs; upstream attribution/license terms remain associated with their respective dataset outputs. Synthetic data and code are MIT. No third-party recordings are redistributed.
