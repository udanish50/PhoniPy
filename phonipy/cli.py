"""Command-line batch/single-file entry point. No network or telemetry."""

import argparse
import csv
import sys
from dataclasses import fields, replace
from pathlib import Path

from . import __version__
from .analysis import analyze_file
from .batch import BatchResult, analyze_directory
from .config import AnalysisConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description="PhoniPy voice stability analysis")
    parser.add_argument("input", type=Path, help="Audio file or directory")
    parser.add_argument("-o", "--output", type=Path, default=Path("phonipy-results.json"))
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument("--preset", choices=["general", "low", "high", "speech", "singing"])
    parser.add_argument("--reference-key", type=float, help="Fractional MIDI note; A4=69")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Stop on the first failed file")
    parser.add_argument("--details", type=Path, help="Directory for frame/segment JSON and CSV")
    parser.add_argument("--plot", action="store_true", help="Save composite PNGs in --details")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if args.config and args.preset:
        parser.error("Choose --config or --preset, not both")
    if args.plot and not args.details:
        parser.error("--plot requires --details DIR")
    try:
        config = (
            AnalysisConfig.from_json(args.config)
            if args.config
            else AnalysisConfig.preset(args.preset or "general")
        )
        if args.reference_key is not None:
            config = replace(config, reference_key=args.reference_key)
        if args.input.is_dir():
            batch = analyze_directory(
                args.input, config, recursive=args.recursive, strict=args.strict
            )
        else:
            batch = BatchResult([analyze_file(args.input, config)], [], config.to_dict())
        batch.save(args.output)
        if args.details:
            args.details.mkdir(parents=True, exist_ok=True)
            for index, result in enumerate(batch.results):
                # Numeric prefix prevents collisions between equal filenames in subfolders.
                name = f"{index:05d}-{Path(result.source).stem}"
                result.to_json(args.details / f"{name}.json", include_frames=True)
                for label in ("frames", "segments"):
                    records = getattr(result, label)
                    if records:
                        from dataclasses import asdict

                        with (args.details / f"{name}-{label}.csv").open(
                            "w", newline="", encoding="utf-8"
                        ) as handle:
                            writer = csv.DictWriter(
                                handle, fieldnames=[f.name for f in fields(records[0])]
                            )
                            writer.writeheader()
                            writer.writerows(asdict(record) for record in records)
                if args.plot:
                    import matplotlib.pyplot as plt

                    figure = result.plot(args.details / f"{name}.png")
                    plt.close(figure)
        print(
            f"Analyzed {len(batch.results)} file(s); {len(batch.errors)} error(s). "
            f"Saved {args.output}"
        )
        return 1 if batch.errors else 0
    except (ValueError, OSError, RuntimeError, ImportError, TypeError) as exc:
        print(f"phonipy: {exc}", file=sys.stderr)
        return 2
