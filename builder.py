#!/usr/bin/env python3
"""DIMS Dashboard Builder — launcher.

Starts the Flask wizard server and opens the browser. No-code entry point:
just run `python builder.py`.
"""
import os
import socket
import threading
import webbrowser

from app.server import create_app


def _find_free_port(preferred=5000):
    """Return `preferred` if free, otherwise an OS-assigned free port."""
    for port in (preferred,):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    port = int(os.environ.get("BUILDER_PORT") or _find_free_port(5000))
    url = f"http://localhost:{port}"
    app = create_app()

    # Open the browser shortly after the server starts. Guard against the
    # Werkzeug reloader double-launch via the WERKZEUG_RUN_MAIN sentinel.
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"\n  DIMS Dashboard Builder running at {url}\n  (Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
