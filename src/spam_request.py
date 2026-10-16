#!/usr/bin/env python3
"""Advanced Web UI for Stress Testing - Pure Python Stdlib (Light Theme)"""

from __future__ import annotations

import json
import os
import http.client
import threading
import time
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

TARGET = os.environ.get("TARGET", "http://app:8000")
UI_PORT = int(os.environ.get("UI_PORT", "8080"))
ENDPOINTS = ["/", "/healthz", "/work", "/slow", "/fail", "/nope"]

CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 30.0
RATE_WINDOW_SECONDS = 5.0
MAX_WORKERS = 512

# ==========================================
# CORE LOAD ENGINE
# ==========================================

class RateWindow:
    def __init__(self, seconds: float = RATE_WINDOW_SECONDS) -> None:
        self.seconds = seconds
        self._times: deque[float] = deque()
        self._lock = threading.Lock()

    def add(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._times.append(now)
            self._prune(now)

    def rate(self) -> float:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            return len(self._times) / self.seconds

    def _prune(self, now: float) -> None:
        cutoff = now - self.seconds
        while self._times and self._times[0] < cutoff:
            self._times.popleft()

class EndpointLoad:
    def __init__(self, base_url: str, path: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.path = path
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = "idle"
        self._window = RateWindow()
        self._reset_counters()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, workers: int, rps: float, duration: int) -> None:
        if self.running: return
        with self._lock:
            self._reset_counters()
        self._window = RateWindow()
        self._stop.clear()
        self._state = "running"
        self._thread = threading.Thread(
            target=self._supervise, args=(workers, rps, duration),
            name=f"load{self.path}", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self.running:
            self._state = "stopping"
            self._stop.set()

    def snapshot(self) -> dict:
        with self._lock:
            total = self._total
            errors = self._errors
            latency_sum = self._latency_sum
            latency_max = self._latency_max
        state = self._state
        if state == "running" and self._stop.is_set():
            state = "stopping"
        return {
            "path": self.path,
            "state": state,
            "total": total,
            "errors": errors,
            "avg_ms": (latency_sum / total * 1000.0) if total else 0.0,
            "max_ms": latency_max * 1000.0,
            "rps": self._window.rate(),
        }

    def _reset_counters(self) -> None:
        self._total = 0
        self._errors = 0
        self._latency_sum = 0.0
        self._latency_max = 0.0

    def _supervise(self, workers: int, rps: float, duration: int) -> None:
        sem = threading.BoundedSemaphore(workers)
        interval = (1.0 / rps) if rps and rps > 0 else None
        deadline = (time.monotonic() + duration) if duration and duration > 0 else None
        next_at = time.perf_counter()

        def one_request() -> None:
            try: self._do_request()
            finally: sem.release()

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                while not self._stop.is_set():
                    if deadline is not None and time.monotonic() >= deadline: break
                    if not sem.acquire(timeout=0.2): continue
                    pool.submit(one_request)
                    if interval is not None:
                        next_at += interval
                        delay = next_at - time.perf_counter()
                        if delay > 0:
                            if self._stop.wait(min(delay, 0.25)): break
                        else:
                            next_at = time.perf_counter()
        finally:
            self._state = "finished"

    def _do_request(self) -> None:
        parts = urlsplit(self.base_url)
        started = time.perf_counter()
        status: int | None = None
        transport_error = False
        connection = None
        try:
            if parts.scheme == "https":
                connection = http.client.HTTPSConnection(parts.hostname, parts.port or 443, timeout=CONNECT_TIMEOUT)
            else:
                connection = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=CONNECT_TIMEOUT)
            connection.connect()
            connection.sock.settimeout(READ_TIMEOUT)
            connection.request("GET", self.path)
            response = connection.getresponse()
            status = response.status
            response.read()
        except Exception:
            transport_error = True
        finally:
            if connection is not None:
                try: connection.close()
                except Exception: pass
        elapsed = time.perf_counter() - started

        with self._lock:
            self._total += 1
            if transport_error or (status is not None and status >= 400):
                self._errors += 1
            self._latency_sum += elapsed
            if elapsed > self._latency_max:
                self._latency_max = elapsed
        self._window.add()

LOAD_ENGINES = {path: EndpointLoad(TARGET, path) for path in ENDPOINTS}

# ==========================================
# WEB FRONTEND (HTML / CSS / JS) - LIGHT THEME
# ==========================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Stress Panel</title>
    <style>
        :root {
            --primary: #0284c7;
            --primary-hover: #0369a1;
            --bg-body: #f8fafc;
            --bg-card: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --endpoint: #c2410c;
            --btn-stop: #ef4444;
            --btn-stop-hover: #dc2626;
            --state-running: #059669;
            --state-stopping: #d97706;
            --state-finished: #475569;
        }

        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg-body); color: var(--text-main); margin: 0; padding: 30px 20px; }
        .container { max-width: 1200px; margin: auto; background: var(--bg-card); padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); border: 1px solid var(--border); }
        h2 { color: var(--primary); margin-top: 0; border-bottom: 2px solid var(--bg-body); padding-bottom: 15px; font-size: 1.5rem; }
        .target-bar { margin-bottom: 25px; color: var(--primary-hover); font-size: 1.05rem; }
        
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
        th { text-align: left; padding: 12px 10px; border-bottom: 2px solid var(--border); color: var(--primary); font-weight: 600; font-size: 0.95rem; }
        td { padding: 15px 10px; border-bottom: 1px solid var(--border); vertical-align: middle; }
        
        th:nth-child(1), td:nth-child(1) { width: 12%; }
        th:nth-child(2), td:nth-child(2) { width: 10%; }
        th:nth-child(3), td:nth-child(3) { width: 12%; }
        th:nth-child(4), td:nth-child(4) { width: 12%; }
        th:nth-child(5), td:nth-child(5) { width: 12%; }
        th:nth-child(6), td:nth-child(6) { width: auto; }

        .endpoint { font-family: Consolas, monospace; font-weight: bold; color: var(--endpoint); font-size: 1.05rem; }
        
        input[type="number"] { background: var(--bg-card); border: 1px solid #cbd5e1; color: var(--text-main); padding: 8px 12px; border-radius: 6px; width: 70px; font-family: Consolas, monospace; transition: all 0.2s; }
        input[type="number"]:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.1); }
        
        button { background: #f1f5f9; border: 1px solid #cbd5e1; color: var(--text-main); padding: 8px 16px; border-radius: 6px; cursor: pointer; transition: 0.2s; font-weight: 600; width: 105px; text-align: center; }
        button:hover { background: #e2e8f0; border-color: #94a3b8; }
        .btn-running { background: var(--btn-stop); border-color: var(--btn-stop-hover); color: white; }
        .btn-running:hover { background: var(--btn-stop-hover); border-color: #b91c1c; }
        
        .status-text { font-family: Consolas, monospace; font-size: 0.95rem; color: var(--text-muted); }
        .status-running { color: var(--state-running); font-weight: bold; }
        .status-stopping { color: var(--state-stopping); font-weight: bold; }
        .status-finished { color: var(--state-finished); font-weight: bold; }
        
        .stat-block { display: inline-block; width: 100px; }
        .stat-block-wide { display: inline-block; width: 140px; }
        
        .footer { font-size: 0.85rem; color: var(--text-muted); font-style: italic; margin-top: 20px; padding-top: 15px; border-top: 1px dashed var(--border); }
    </style>
</head>
<body>
    <div class="container">
        <h2>Web Stress Panel</h2>
        <div class="target-bar">Internal Target: <strong id="targetUrl">Loading...</strong></div>
        
        <table id="loadTable">
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th>Workers</th>
                    <th>Target req/s</th>
                    <th>Duration (s)</th>
                    <th>Action</th>
                    <th>Stress State</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        </table>
        <div class="footer">/fail (500) and /nope (404) report as errors by design. Graphs lag by ~15s.</div>
    </div>

    <script>
        const ENDPOINTS = ["/", "/healthz", "/work", "/slow", "/fail", "/nope"];
        
        const tbody = document.querySelector("#loadTable tbody");
        ENDPOINTS.forEach(path => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td class="endpoint">${path}</td>
                <td><input type="number" id="workers-${path}" value="4" min="1" max="512"></td>
                <td><input type="number" id="rps-${path}" value="0" min="0" step="5"></td>
                <td><input type="number" id="duration-${path}" value="0" min="0" step="10"></td>
                <td><button id="btn-${path}" onclick="toggle('${path}')">▶ Start</button></td>
                <td><div class="status-text" id="status-${path}">idle - not started</div></td>
            `;
            tbody.appendChild(tr);
        });

        async function toggle(path) {
            const btn = document.getElementById(`btn-${path}`);
            const isRunning = btn.innerText.includes("Stop");
            
            if (isRunning) {
                await fetch('/api/stop', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ path: path })
                });
            } else {
                const workers = parseInt(document.getElementById(`workers-${path}`).value) || 4;
                const rps = parseFloat(document.getElementById(`rps-${path}`).value) || 0;
                const duration = parseInt(document.getElementById(`duration-${path}`).value) || 0;
                
                await fetch('/api/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ path, workers, rps, duration })
                });
            }
            refreshData();
        }

        async function refreshData() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('targetUrl').innerText = data.target;

                data.loads.forEach(snap => {
                    const btn = document.getElementById(`btn-${snap.path}`);
                    const stat = document.getElementById(`status-${snap.path}`);
                    
                    if (snap.state === "idle") {
                        btn.innerText = "▶ Start";
                        btn.className = "";
                        stat.innerHTML = "idle - not started";
                        stat.className = "status-text";
                    } else {
                        if (snap.state === "running" || snap.state === "stopping") {
                            btn.innerText = "■ Stop";
                            btn.className = "btn-running";
                        } else {
                            btn.innerText = "▶ Start";
                            btn.className = "";
                        }
                        
                        let stateClass = "status-text ";
                        if (snap.state === "running") stateClass += "status-running";
                        else if (snap.state === "stopping") stateClass += "status-stopping";
                        else if (snap.state === "finished") stateClass += "status-finished";
                        
                        stat.className = stateClass;
                        
                        const stateStr = `[${snap.state.toUpperCase()}]`.padEnd(10);
                        const rps = snap.rps.toFixed(1) + ' req/s';
                        const total = snap.total.toLocaleString() + ' req';
                        const errors = snap.errors.toLocaleString() + ' err';
                        const avg = 'Avg: ' + snap.avg_ms.toFixed(1) + ' ms';
                        const max = 'Max: ' + snap.max_ms.toFixed(1) + ' ms';
                        
                        stat.innerHTML = `
                            <span class="stat-block">${stateStr}</span> 
                            <span class="stat-block">${rps}</span> | 
                            <span class="stat-block">${total}</span> | 
                            <span class="stat-block">${errors}</span> | 
                            <span class="stat-block-wide">${avg}</span> | 
                            <span class="stat-block-wide">${max}</span>
                        `;
                    }
                });
            } catch (err) {
                console.error("Status check failed", err);
            }
        }

        setInterval(refreshData, 500);
        refreshData();
    </script>
</body>
</html>
"""
# ==========================================
# HTTP SERVER (API & HTML HANDLER)
# ==========================================

class WebStressHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Tắt log console cho gọn

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/":
            data = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/api/status":
            loads_data = [LOAD_ENGINES[p].snapshot() for p in ENDPOINTS]
            self._send_json({"target": TARGET, "loads": loads_data})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if self.path == "/api/start":
            path = req_data.get("path", "/")
            if path in LOAD_ENGINES:
                LOAD_ENGINES[path].start(
                    workers=min(max(int(req_data.get("workers", 4)), 1), MAX_WORKERS),
                    rps=max(float(req_data.get("rps", 0.0)), 0.0),
                    duration=max(int(req_data.get("duration", 0)), 0)
                )
                self._send_json({"status": "started"})
            else:
                self._send_json({"error": "Unknown path"}, 404)

        elif self.path == "/api/stop":
            path = req_data.get("path", "/")
            if path in LOAD_ENGINES:
                LOAD_ENGINES[path].stop()
                self._send_json({"status": "stopping"})
            else:
                self._send_json({"error": "Unknown path"}, 404)
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", UI_PORT), WebStressHandler)
    print(f"Advanced Web Stress UI running on port {UI_PORT}, targeting {TARGET}", flush=True)
    server.serve_forever()