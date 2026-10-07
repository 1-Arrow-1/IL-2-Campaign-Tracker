"""
test_service_record_port.py
---------------------------
Tests for campaign_service_record.app.choose_port().

The Service Record used to exit silently when another program held its port
(e.g. the Salad service on 5000). choose_port() now falls back to a free port
and reuses an already running Service Record instead of starting a second one.

Scenarios covered
-----------------
1. Preferred port free          → preferred port, not running
2. Preferred port foreign-held  → first free fallback port
3. Own server on preferred port → reused (already_running)
4. Own server in other mode     → not reused
5. Own server on a fallback port while the preferred port is foreign-held → reused
"""

import json
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from campaign_service_record import app as csr_app

HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


class _FakeServer:
    """A local HTTP server; answers /api/identity when identity is given."""

    def __init__(self, port, identity=None):
        body = json.dumps(identity).encode() if identity else b"not the tracker"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if identity else 404)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = HTTPServer((HOST, port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


class TestChoosePort(unittest.TestCase):

    def setUp(self):
        # Use high, currently free ports so the test does not depend on 5000/5050.
        self.preferred = _free_port()
        self.fallback = _free_port()
        self._orig = csr_app.FALLBACK_PORTS
        csr_app.FALLBACK_PORTS = [self.fallback, _free_port()]

    def tearDown(self):
        csr_app.FALLBACK_PORTS = self._orig

    def test_preferred_port_free(self):
        self.assertEqual(csr_app.choose_port(HOST, self.preferred, "campaign"), (self.preferred, False))

    def test_foreign_program_on_preferred_port_falls_back(self):
        with _FakeServer(self.preferred):
            self.assertEqual(csr_app.choose_port(HOST, self.preferred, "campaign"), (self.fallback, False))

    def test_own_server_is_reused(self):
        with _FakeServer(self.preferred, {"app": csr_app.APP_ID, "mode": "campaign"}):
            self.assertEqual(csr_app.choose_port(HOST, self.preferred, "campaign"), (self.preferred, True))

    def test_own_server_in_other_mode_is_not_reused(self):
        with _FakeServer(self.preferred, {"app": csr_app.APP_ID, "mode": "career"}):
            self.assertEqual(csr_app.choose_port(HOST, self.preferred, "campaign"), (self.fallback, False))

    def test_own_server_on_fallback_port_is_reused(self):
        with _FakeServer(self.preferred), \
                _FakeServer(self.fallback, {"app": csr_app.APP_ID, "mode": "campaign"}):
            self.assertEqual(csr_app.choose_port(HOST, self.preferred, "campaign"), (self.fallback, True))


if __name__ == "__main__":
    unittest.main()
