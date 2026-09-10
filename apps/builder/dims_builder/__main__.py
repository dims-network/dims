#!/usr/bin/env python3
"""DIMS Dashboard Builder — launcher.

Starts the Flask wizard and opens a browser. The no-code entry point:

    pip install "dims-network[builder]"
    dims-builder

Still runnable from a checkout with `python -m dims_builder`.
"""
import os
import socket
import threading
import webbrowser

try:
    from dims_builder.server import create_app
except ModuleNotFoundError as exc:              # pragma: no cover - install
    # The wizard's dependencies are an extra, so `pip install -e ./dims`
    # installs a `dims-builder` that cannot start. Say which install fixes it:
    # this is the first command a reader of the no-code tutorial runs, and a
    # bare ModuleNotFoundError gives them nothing to search for.
    raise SystemExit(
        f"The builder needs its extra ({exc.name} is missing). "
        "Install it with: pip install 'dims-network[builder]'"
    ) from exc


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
    # Werkzeug reloader double-launch via the WERKZEUG_RUN_MAIN sentinel, and
    # against DIMS_BUILDER_NO_BROWSER, which the end-to-end test sets: a test
    # run should not take over the screen of whoever is running it.
    if not os.environ.get("WERKZEUG_RUN_MAIN") \
            and not os.environ.get("DIMS_BUILDER_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print(f"\n  DIMS Dashboard Builder running at {url}\n  (Ctrl+C to stop)\n")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
