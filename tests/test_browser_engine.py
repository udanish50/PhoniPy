"""Cross-runtime numerical conformance tests for the browser and Python detectors."""

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

import phonipy
from phonipy import __version__, analyze_samples

NODE = shutil.which("node")
ENGINE = Path(phonipy.__file__).parent / "web" / "engine.mjs"


@pytest.mark.skipif(not NODE, reason="Node.js is required for browser-engine conformance tests")
@pytest.mark.parametrize(
    "kind", ["sine", "harmonics", "missing", "silence", "noise", "break", "offset"]
)
def test_browser_matches_python(kind):
    rate = 16000
    t = np.arange(8000) / rate
    if kind == "silence":
        x = np.zeros(len(t))
    elif kind == "noise":
        x = np.random.default_rng(83).normal(0, 0.08, len(t))
    elif kind == "missing":
        x = 0.12 * sum(np.sin(2 * np.pi * 220 * h * t) for h in [2, 3, 4])
    elif kind == "harmonics":
        x = 0.2 * sum(np.sin(2 * np.pi * 220 * h * t) / h for h in range(1, 6))
    else:
        frequency = 440 * 2 ** (0.25 / 12) if kind == "offset" else 220
        x = 0.4 * np.sin(2 * np.pi * frequency * t)
        if kind == "break":
            x[2800:4400] = 0
    # Browser audio samples use Float32 PCM, so compare the identical input in both engines.
    x = x.astype(np.float32)
    expected = analyze_samples(x, rate)
    script = f"""
        import {{analyzeSamples,VERSION}} from {json.dumps(ENGINE.as_uri())};
        let text='';for await (const chunk of process.stdin)text+=chunk;
        const result=analyzeSamples(Float32Array.from(JSON.parse(text)));
        console.log(JSON.stringify({{...result,version:VERSION}}));
    """
    completed = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        input=json.dumps(x.tolist()),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    actual = json.loads(completed.stdout)
    assert actual["version"] == __version__
    assert actual["metadata"]["fft_size"] == expected.metadata["fft_size"]
    assert actual["metrics"] == pytest.approx(expected.to_dict()["metrics"], abs=2e-8)
    assert len(actual["frames"]) == len(expected.frames)
    for a, b in zip(actual["frames"], expected.frames):
        assert a["key"] == b.key
        assert a["accepted"] == b.accepted
        assert a["energy_ratio"] == pytest.approx(b.energy_ratio, abs=2e-8)
        if b.frequency is not None:
            assert a["frequency"] == pytest.approx(b.frequency, abs=2e-6)
