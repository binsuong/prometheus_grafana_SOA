"""
Run locally:   python app.py
Inspect:       curl http://localhost:8000/metrics
"""

from __future__ import annotations

import os
import random
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

PORT = int(os.environ.get("PORT", "8000"))

# ---------------------------------------------------------------------------
# Metric definitions
#
# Naming convention: <namespace>_<subsystem>_<name>_<unit>. Prometheus never
# rewrites names, so getting the convention right is worth the two seconds:
#   * counters end in _total
#   * histograms expose _bucket / _sum / _count
#   * units are base units (seconds, bytes) and go at the end
# ---------------------------------------------------------------------------

# Counter(name, documentation, labelnames=(), namespace='', subsystem='', unit='', registry=REGISTRY)
# REQUESTS = Counter("requests_total", "Total requests", ["method", "status"], namespace='demo', subsystem='http')
REQUESTS = Counter("demo_http_requests_total", 
                   "Total requests", 
                   ["method", "path", "status"])

#A Gauge tracks a value that can go up and down. Use it for things you sample at a point in time — active connections, queue depth, memory usage, temperature.
IN_PROGRESS = Gauge("demo_http_requests_in_progress",
                    "Requests currently in progress",)

#A Histogram samples observations and counts them in configurable buckets. Use it when you want to track distributions
#  — request latency, response sizes — and need to calculate quantiles (p50, p95, p99) in your queries.
REQUEST_LATENCY = Histogram("demo_http_request_duration_seconds",
                            "HTTP request latency",
                            ["path"],
                            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 3.0, 4.5, 5.0, 6.0))

class Handler(BaseHTTPRequestHandler):

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]

        if path == "/metrics":
            data = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        IN_PROGRESS.inc()
        time_start = time.perf_counter()

        try:
            status, body = self._handle(path)
        except Exception as exception:
            status, body = 500, f"Server error: {exception}\n"
        finally: IN_PROGRESS.dec()

        REQUESTS.labels(method="GET", path=path, status=str(status)).inc()
        REQUEST_LATENCY.labels(path=path).observe(time.perf_counter() - time_start)
        
        return self._response(status, body)


    def _handle(self, path: str) -> Tuple[int, str]:
        if path == "/": return 200, "Demo"

        if path == "/health": return 200, "Ok\n"

        if path == "/work": 
            output = "Ok" if random.random() < 0.9 else "Error"
            time.sleep(random.uniform(0.01, 0.5))

            return (200 if output == "Ok" else 500), f"{output}\n"
        
        if path == "/slow":
            time.sleep(random.uniform(1.0, 5.0))
            return 200, "Slow request\n"
        
        if path == "/fail": return 500, "Failure\n"
        return 404, "Not found\n"


    def _response(self, status: int, body: str):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    stop_event = threading.Event()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)

    def shutdown(signum, frame):
        print(f"[app] signal {signum} received, shutting down", flush=True)
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    server.serve_forever()

if __name__ == "__main__":
    main()