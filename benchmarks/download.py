"""Download pinned public benchmarks; no credentials needed and no raw data committed."""

import argparse
import hashlib
import json
import shutil
import ssl
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.request import urlopen

import certifi

FSDD_COMMIT = "26eb9aaf76e81b692f806f9140c2d2777410d7a1"
SOURCES = {
    "fsdd": f"https://codeload.github.com/Jakobovski/free-spoken-digit-dataset/zip/{FSDD_COMMIT}",
    "voiced": "https://physionet.org/static/published-projects/voiced/voiced-database-1.0.0.zip",
}


def download(url, path):
    if path.exists() and zipfile.is_zipfile(path):
        return
    for attempt in range(3):
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with (
                urlopen(url, timeout=120, context=context) as response,
                path.with_suffix(".part").open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
            path.with_suffix(".part").replace(path)
            if not zipfile.is_zipfile(path):
                raise ValueError(f"Downloaded resource is not a ZIP: {url}")
            return
        except (URLError, OSError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("benchmarks/data"))
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, url in SOURCES.items():
        archive = args.data_dir / f"{name}.zip"
        print(f"Downloading {name}...", flush=True)
        download(url, archive)
        output = args.data_dir / name
        output.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as handle:
            for member in handle.infolist():
                parts = PurePosixPath(member.filename).parts
                if member.is_dir() or ".." in parts or member.filename.startswith("/"):
                    continue
                path = PurePosixPath(member.filename)
                if name == "fsdd":
                    if "recordings" not in parts and path.name not in ("README.md", "LICENSE"):
                        continue
                    relative = (
                        Path("recordings") / path.name if "recordings" in parts else Path(path.name)
                    )
                else:
                    if path.suffix not in (".hea", ".dat") and path.name not in (
                        "RECORDS",
                        "LICENSE.txt",
                        "LICENSE",
                        "SHA256SUMS.txt",
                    ):
                        continue
                    relative = Path(path.name)
                destination = output / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                with handle.open(member) as src, destination.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        files = []
        for path in sorted(output.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "file": path.relative_to(args.data_dir).as_posix(),
                        "sha256": sha256_file(path),
                    }
                )
        # Verify official checksums when provided by PhysioNet.
        checksums = output / "SHA256SUMS.txt"
        if checksums.exists():
            expected = {}
            for line in checksums.read_text().splitlines():
                digest, filename = line.split(maxsplit=1)
                expected[Path(filename.lstrip("*")).name] = digest
            for item in files:
                filename = Path(item["file"]).name
                if filename in expected and item["sha256"] != expected[filename]:
                    raise ValueError(f"Official SHA256 mismatch: {filename}")
        digest = sha256_file(archive)
        manifest.append(
            {
                "dataset": name,
                "url": url,
                "archive_sha256": digest,
                "snapshot": FSDD_COMMIT if name == "fsdd" else "1.0.0",
                "files": files,
            }
        )
        print(f"Extracted {len(files)} files for {name}", flush=True)
    (args.data_dir / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
