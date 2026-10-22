"""Serve the bundled on-device interface. The server never receives audio or results."""

import argparse
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class PrivateStaticHandler(SimpleHTTPRequestHandler):
    """Read-only static assets without request logs, uploads, or persistent caches."""

    def log_message(self, format, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404)
        return None


def create_server(port=0):
    directory = str(Path(__file__).with_name("web"))
    handler = partial(PrivateStaticHandler, directory=directory)
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open the PhoniPy voice-analysis workspace")
    parser.add_argument(
        "--port", type=int, default=0, help="Local port; default chooses a free port"
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Print the URL without opening a browser"
    )
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        server = create_server(args.port)
    except OSError as exc:
        print(f"phonipy: cannot start the interface: {exc}")
        return 2
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"PhoniPy is available at {url}", flush=True)
    print(
        "Audio and analysis stay in browser memory. Press Ctrl+C to close the server.", flush=True
    )
    try:
        if not args.no_open:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
