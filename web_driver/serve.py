"""
Tiny static file server for the copied game. Runs in a background thread
so Playwright can drive it on localhost.

We can't just `python -m http.server` because:
  * we want to control lifetime from the same process as the driver
  * we want a quiet server (no log spam)
"""
from __future__ import annotations

import logging
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 — stdlib API
        # Drop all stdlib log spam. Override w/ logging if needed.
        return


def start_server(directory: str, port: int = 8765) -> HTTPServer:
    """Start an HTTP server in a daemon thread. Returns the server object
    so the caller can `httpd.shutdown()` cleanly."""
    handler = partial(_QuietHandler, directory=directory)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    logging.getLogger(__name__).info(
        "serving %s on http://127.0.0.1:%d", Path(directory).resolve(), port
    )
    return httpd
