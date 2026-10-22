import io
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from phonipy import app


def test_dashboard_initial_state():
    test = AppTest.from_file(str(Path(app.__file__))).run(timeout=20)
    assert not test.exception
    assert test.title[0].value == "PhoniPy"
    assert test.button[0].disabled
    test.selectbox[0].set_value("singing").run(timeout=20)
    assert not test.exception


def test_dashboard_uploaded_files(monkeypatch):
    class Upload(io.BytesIO):
        name = "test-voice.wav"

        @property
        def size(self):
            return len(self.getvalue())

    buffer = Upload()
    sf.write(buffer, 0.3 * np.sin(2 * np.pi * 220 * np.arange(16000) / 16000), 16000, format="WAV")
    monkeypatch.setattr("streamlit.file_uploader", lambda *a, **k: [buffer])
    test = AppTest.from_file(str(Path(app.__file__))).run(timeout=20)
    test.button[0].click().run(timeout=20)
    assert not test.exception
    assert len(test.dataframe) == 2


def test_dashboard_corrupt_file(monkeypatch):
    class Upload(io.BytesIO):
        name = "corrupt.wav"
        size = 10

    monkeypatch.setattr("streamlit.file_uploader", lambda *a, **k: [Upload(b"not audio")])
    test = AppTest.from_file(str(Path(app.__file__))).run(timeout=20)
    test.button[0].click().run(timeout=20)
    assert not test.exception
    assert test.error
