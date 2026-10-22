"""Batch processing in the spirit of midipy, with per-file error isolation."""

import csv
import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .analysis import analyze_file
from .config import AnalysisConfig
from .models import AnalysisResult, Metrics

EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".mp3", ".au", ".snd"}


@dataclass
class BatchResult:
    results: list[AnalysisResult]
    errors: list[dict]
    config: dict

    @property
    def rows(self):
        return [
            {
                "source": r.source,
                "status": "ok",
                **asdict(r.metrics),
                "warnings": " | ".join(r.warnings),
            }
            for r in self.results
        ]

    def save(self, path):
        """Write an atomic summary; CSV/XLSX also receive a structured error sidecar."""
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix not in (".json", ".csv", ".xlsx"):
            raise ValueError("Output extension must be .json, .csv or .xlsx")
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=suffix)
        os.close(descriptor)
        temporary = Path(temporary)
        try:
            if suffix == ".json":
                temporary.write_text(
                    json.dumps(
                        {
                            "config": self.config,
                            "results": [r.to_dict() for r in self.results],
                            "errors": self.errors,
                        },
                        indent=2,
                        allow_nan=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            else:
                columns = [
                    "source",
                    "status",
                    *[f.name for f in fields(Metrics)],
                    "warnings",
                    "error",
                ]
                rows = self.rows + [
                    {"source": e["source"], "status": "error", "error": e["error"]}
                    for e in self.errors
                ]
                if suffix == ".csv":
                    with temporary.open("w", newline="", encoding="utf-8") as handle:
                        writer = csv.DictWriter(handle, fieldnames=columns)
                        writer.writeheader()
                        writer.writerows(rows)
                else:
                    try:
                        from openpyxl import Workbook
                    except ImportError as exc:
                        raise ImportError("Install phonipy[excel] for XLSX output") from exc
                    book = Workbook()
                    sheet = book.active
                    sheet.title = "Metrics"
                    sheet.append(columns)
                    for row in rows:
                        # Force strings to text to avoid interpreting source filenames as formulas.
                        sheet.append([row.get(c) for c in columns])
                        for cell in sheet[sheet.max_row]:
                            if isinstance(cell.value, str):
                                cell.data_type = "s"
                    sheet.freeze_panes = "A2"
                    book.save(temporary)
                sidecar = path.with_suffix(path.suffix + ".metadata.json")
                sidecar.write_text(
                    json.dumps(
                        {
                            "config": self.config,
                            "errors": self.errors,
                            "recordings": [
                                {"source": r.source, "metadata": r.metadata, "warnings": r.warnings}
                                for r in self.results
                            ],
                        },
                        indent=2,
                        allow_nan=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return path


def analyze_directory(source, config=None, *, recursive=False, strict=False, progress=None):
    config = config or AnalysisConfig()
    directory = Path(source)
    if not directory.is_dir():
        raise ValueError(f"Input directory does not exist: {directory}")
    paths = sorted(
        p
        for p in (directory.rglob("*") if recursive else directory.iterdir())
        if p.is_file() and p.suffix.lower() in EXTENSIONS
    )
    if not paths:
        raise ValueError(f"No supported audio files found in {directory}")
    results, errors = [], []
    for index, path in enumerate(paths):
        try:
            results.append(analyze_file(path, config))
        except (ValueError, OSError, RuntimeError) as exc:
            if strict:
                raise
            errors.append({"source": str(path), "type": type(exc).__name__, "error": str(exc)})
        if progress:
            progress(index + 1, len(paths), str(path))
    return BatchResult(results, errors, config.to_dict())


def parser(source, metrics=None, output_format="csv", save_path="Output", **kwargs):
    """midipy-style convenience API; returns a DataFrame (requires pandas)."""
    import pandas as pd

    result = analyze_directory(source, **kwargs)
    table = pd.DataFrame(result.rows)
    if metrics is not None and metrics != ["all"]:
        unknown = set(metrics) - set(table.columns)
        if unknown:
            raise ValueError(f"Unknown metrics: {sorted(unknown)}")
        table = table.loc[:, metrics]
    if output_format not in ("csv", "json", "xlsx", "excel"):
        raise ValueError("output_format must be csv, json, xlsx or excel")
    extension = "xlsx" if output_format == "excel" else output_format
    result.save(f"{save_path}.{extension}")
    table.attrs["errors"] = result.errors
    return table
