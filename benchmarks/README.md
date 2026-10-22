# Benchmark protocol

Run from the repository root after `pip install -e '.[test,benchmark]'`.

```bash
python benchmarks/download.py --data-dir benchmarks/data
python benchmarks/run.py --data-dir benchmarks/data --output benchmarks/results
```

Use `--datasets synthetic fsdd` or `--datasets voiced` to run selected corpora. Runs in the
same output directory merge summaries only when configuration and dependency versions match.

## Sources

1. **Free Spoken Digit Dataset (FSDD)**, Jakobovski and contributors:
   https://github.com/Jakobovski/free-spoken-digit-dataset
   Snapshot: `26eb9aaf76e81b692f806f9140c2d2777410d7a1`.
   CC BY-SA 4.0; 3,000 8-kHz English digit recordings from six speakers.
   All files are processed; no training or classification is performed.
2. **VOICED Database**, version 1.0.0:
   https://physionet.org/content/voiced/1.0.0/
   DOI: https://doi.org/10.13026/C25Q2N
   License: Open Data Commons Attribution License v1.0.
   208 sustained-vowel records, including healthy and pathological voices.
   All records are processed as a technical coverage benchmark; no disease labels are predicted.
   WFDB `p_signal` is decoded using the record's physical gain/baseline. It is not
   per-recording peak-normalized, so amplitude gating remains an explicit limitation.
3. **PhoniPy synthetic-v1**: generated sines, harmonic tones, interrupted holds, noise,
   and silence with fixed RNG seed. Code is MIT, with known pitch for periodic cases.

Downloads use HTTPS with verification, timeout/retry, safe selective FSDD archive extraction,
and SHA-256 provenance manifests. VOICED signals/headers are checked against PhysioNet's
official SHA256SUMS. Raw third-party recordings are never included in package
distributions or committed. Dataset hashes and per-file result hashes are saved with results.
The benchmark writes all ten metrics for each recording, failure manifests, summaries,
dependency/platform metadata, and synthetic pitch-error measurements. Low/zero detection
coverage is reported, never hidden as a successful clinical measurement.

No ground-truth values for the ten manuscript metrics are supplied by these corpora. Real-data
results measure executability and detector coverage, not pitch-estimation accuracy, clinical
validity, or sensitivity/specificity. Use a separate annotated pitch corpus and clinical study
before making those claims.
