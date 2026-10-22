from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from phonipy import app
from phonipy.cli import main


def test_static_interface_serves_assets_and_rejects_uploads():
    server = app.create_server()
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{server.server_port}"
    try:
        for resource in ["/", "/app.mjs", "/engine.mjs", "/worker.mjs", "/styles.css"]:
            with urlopen(root + resource) as response:
                assert response.status == 200
                assert response.headers["Cache-Control"] == "no-store"
                assert response.headers["X-Content-Type-Options"] == "nosniff"
        with pytest.raises(HTTPError) as error:
            urlopen(Request(root + "/", data=b"audio bytes", method="POST"))
        assert error.value.code == 501
        with pytest.raises(HTTPError):
            urlopen(root + "/../_version.py")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_launcher_entrypoint(monkeypatch):
    calls = []

    class Server:
        server_port = 8844

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            calls.append("closed")

    monkeypatch.setattr(app, "create_server", lambda port: Server())
    monkeypatch.setattr(app.webbrowser, "open", calls.append)
    assert main(["app"]) == 0
    assert calls == ["http://127.0.0.1:8844/", "closed"]
    calls.clear()
    assert app.main(["--no-open", "--port", "8844"]) == 0
    assert calls == ["closed"]
    with pytest.raises(SystemExit):
        app.main(["--port", "70000"])


def test_launcher_bind_error(monkeypatch):
    def fail(port):
        raise OSError("Address in use")

    monkeypatch.setattr(app, "create_server", fail)
    assert app.main(["--no-open"]) == 2


def test_packaged_interface_has_playback_and_local_processing():
    root = Path(app.__file__).with_name("web")
    page = (root / "index.html").read_text()
    assert '<audio id="player" controls' in page
    assert "connect-src 'none'" in page
    assert 'type="module" src="./app.mjs"' in page
