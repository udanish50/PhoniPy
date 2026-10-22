"""Download pinned public benchmarks; no credentials needed and no raw data committed."""

import argparse
import hashlib
import json
import re
import shutil
import ssl
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.request import urlopen

import certifi

FSDD_COMMIT = "26eb9aaf76e81b692f806f9140c2d2777410d7a1"
FSDD_URL = f"https://codeload.github.com/Jakobovski/free-spoken-digit-dataset/zip/{FSDD_COMMIT}"
VOICED_URL = "https://physionet.org/files/voiced/1.0.0/"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, path, expected=None):
    if path.exists() and (expected is None or sha256_file(path) == expected):
        return
    partial = path.with_name(path.name + ".part")
    for attempt in range(3):
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urlopen(url, timeout=60, context=context) as response, partial.open("wb") as out:
                shutil.copyfileobj(response, out)
            if expected is not None and sha256_file(partial) != expected:
                raise ValueError(f"Official checksum mismatch: {path.name}")
            partial.replace(path)
            return
        except (URLError, OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def file_manifest(output, root):
    return [
        {"file": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(output.rglob("*"))
        if path.is_file()
    ]


def fetch_fsdd(root):
    archive = root / "fsdd.zip"
    print("Downloading/extracting pinned FSDD...", flush=True)
    download(FSDD_URL, archive)
    output = root / "fsdd"
    output.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            path = PurePosixPath(member.filename)
            if member.is_dir() or ".." in path.parts or path.is_absolute():
                continue
            if "recordings" not in path.parts and path.name not in ("README.md", "LICENSE"):
                continue
            relative = (
                Path("recordings") / path.name if "recordings" in path.parts else Path(path.name)
            )
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(member) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    return {
        "dataset": "fsdd",
        "url": FSDD_URL,
        "snapshot": FSDD_COMMIT,
        "archive_sha256": sha256_file(archive),
        "license": "CC-BY-SA-4.0",
        "files": file_manifest(output, root),
    }


def fetch_voiced(root):
    output = root / "voiced"
    output.mkdir(exist_ok=True)
    download(VOICED_URL + "RECORDS", output / "RECORDS")
    download(VOICED_URL + "SHA256SUMS.txt", output / "SHA256SUMS.txt")
    expected = {}
    for line in (output / "SHA256SUMS.txt").read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        expected[PurePosixPath(filename.lstrip("*")).name] = digest
    records = (output / "RECORDS").read_text().splitlines()
    if len(records) != 208 or not all(re.fullmatch(r"voice\d{3}", r) for r in records):
        raise ValueError("Unexpected VOICED record manifest")
    files = [r + suffix for r in records for suffix in (".hea", ".dat")]
    if not all(name in expected for name in files):
        raise ValueError("VOICED is missing official signal/header checksums")

    def fetch(name):
        download(VOICED_URL + name, output / name, expected[name])

    print("Downloading 208 VOICED signals and headers (four connections)...", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, _ in enumerate(pool.map(fetch, files), 1):
            if index % 50 == 0:
                print(f"VOICED: {index}/{len(files)} files", flush=True)
    return {
        "dataset": "voiced",
        "url": VOICED_URL,
        "snapshot": "1.0.0",
        "license": "Open Data Commons Attribution License v1.0",
        "doi": "10.13026/C25Q2N",
        "files": file_manifest(output, root),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("benchmarks/data"))
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    manifest = [fetch_fsdd(args.data_dir), fetch_voiced(args.data_dir)]
    (args.data_dir / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("All benchmark downloads complete; official VOICED checksums verified", flush=True)


if __name__ == "__main__":
    main()
