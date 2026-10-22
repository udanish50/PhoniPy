"""Compute all ten metrics on complete public corpora and known synthetic signals."""

import argparse
import json
import platform
import sys
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np
from download import sha256_file

from phonipy import AnalysisConfig, analyze_file, analyze_samples, frequency_to_key
from phonipy.batch import BatchResult


def synthetic_cases():
    rate = 16000
    t = np.arange(2 * rate) / rate
    rng = np.random.default_rng(20261022)
    cases = []
    for f in [82.4069, 110, 130.8128, 220, 261.6256, 440, 880]:
        for count in [1, 5]:
            x = sum(np.sin(2 * np.pi * f * h * t) / h for h in range(1, count + 1))
            x = x / np.max(np.abs(x)) * 0.5
            cases.append((f"tone-{f}-{count}harmonics", x, f))
    signal = 0.4 * np.sin(2 * np.pi * 220 * t)
    interrupted = signal.copy()
    interrupted[12000:20000] = 0
    cases.extend(
        [
            ("silence", np.zeros(len(t)), None),
            ("white-noise", rng.normal(0, 0.1, len(t)), None),
            ("interrupted-A3", interrupted, 220),
            ("noisy-A3", signal + rng.normal(0, 0.07, len(t)), 220),
            ("DC-only", np.full(len(t), 0.1), None),
        ]
    )
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("benchmarks/data"))
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results"))
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=["synthetic", "fsdd", "voiced"],
        default=["synthetic", "fsdd", "voiced"],
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    config = AnalysisConfig()
    versions = {p: version(p) for p in ["phonipy", "numpy", "scipy", "soundfile", "wfdb"]}
    previous_path = args.output / "summary.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    if previous and (previous["config"] != config.to_dict() or previous["versions"] != versions):
        raise SystemExit("Use a separate output directory for different settings/dependencies")
    summaries = previous.get("datasets", {})
    provenance = args.data_dir / "provenance.json"
    if not provenance.exists() and any(d != "synthetic" for d in args.datasets):
        raise SystemExit("Run benchmarks/download.py first")
    if provenance.exists():
        (args.output / "provenance.json").write_bytes(provenance.read_bytes())
    groups = {
        "synthetic": synthetic_cases(),
        "fsdd": sorted((args.data_dir / "fsdd" / "recordings").glob("*.wav")),
        "voiced": sorted((args.data_dir / "voiced").glob("*.hea")),
    }
    pitch_errors = (
        []
        if "synthetic" in args.datasets
        else [previous.get("synthetic_max_median_pitch_error_cents", 0)]
    )
    for group, items in groups.items():
        if group not in args.datasets:
            continue
        expected = {"synthetic": 19, "fsdd": 3000, "voiced": 208}[group]
        if len(items) != expected:
            raise SystemExit(f"Incomplete dataset {group}: {len(items)}; expected {expected}")
        started = time.perf_counter()
        results, errors = [], []
        extra = []
        for index, item in enumerate(items):
            try:
                if group == "synthetic":
                    name, samples, truth = item
                    result = analyze_samples(samples, 16000, config, source=name)
                    if truth is not None:
                        target = frequency_to_key(truth)
                        valid_pitch = [f.fractional_key for f in result.frames if f.accepted]
                        cents = (
                            float(np.median(np.abs(np.array(valid_pitch) - target))) * 100
                            if valid_pitch
                            else None
                        )
                        extra.append(
                            {
                                "source": name,
                                "true_hz": truth,
                                "median_absolute_pitch_error_cents": cents,
                            }
                        )
                        if cents is not None:
                            pitch_errors.append(cents)
                elif group == "fsdd":
                    result = analyze_file(item, config)
                    result.source = item.name
                else:
                    import wfdb

                    record = wfdb.rdrecord(str(item.with_suffix("")))
                    result = analyze_samples(
                        record.p_signal, int(record.fs), config, source=item.stem
                    )
                results.append(result)
            except (ValueError, RuntimeError, OSError) as exc:
                errors.append({"source": str(item), "type": type(exc).__name__, "error": str(exc)})
            if (index + 1) % 100 == 0:
                print(f"{group}: {index + 1}/{len(items)}", flush=True)
        # Release frame memory after each corpus's detailed summary has been saved.
        batch = BatchResult(results, errors, config.to_dict())
        batch.save(args.output / f"{group}.csv")
        batch.save(args.output / f"{group}.json")
        if group == "synthetic":
            (args.output / "synthetic-pitch-errors.json").write_text(json.dumps(extra, indent=2))
            for result in results[:2]:
                result.plot(args.output / f"{result.source}.png")
        digest = sha256_file(args.output / f"{group}.json")
        summaries[group] = {
            "files": len(items),
            "processed": len(results),
            "errors": len(errors),
            "with_valid_detections": sum(r.metrics.breakouts > 0 for r in results),
            "without_valid_detections": sum(r.metrics.breakouts == 0 for r in results),
            "audio_seconds": sum(r.metrics.raw_duration for r in results),
            "valid_seconds": sum(r.metrics.valid_time for r in results),
            "processing_seconds": time.perf_counter() - started,
            "results_sha256": digest,
        }
        print(group, summaries[group], flush=True)
        del batch, results
    metadata = {
        "python": sys.version,
        "platform": platform.platform(),
        "versions": versions,
        "config": config.to_dict(),
        "datasets": summaries,
        "synthetic_max_median_pitch_error_cents": max(pitch_errors),
        "interpretation": "Technical coverage only; no clinical accuracy claim",
    }
    (args.output / "summary.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
