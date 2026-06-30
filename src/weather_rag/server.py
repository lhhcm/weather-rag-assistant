from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .assistant import health_payload
from .graph_assistant import GraphWeatherRagAssistant
from .risk_engine import evaluate_activity_plan


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = PROJECT_ROOT / "static"
HOST = "127.0.0.1"
PORT = 8765
DESKTOP_HEARTBEAT_TIMEOUT = 12

assistant = GraphWeatherRagAssistant()


class WeatherRagHandler(BaseHTTPRequestHandler):
    server_version = "WeatherRAG/1.0"

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self.write_json(health_payload(assistant))
            return

        if self.path == "/" or self.path.startswith("/static/"):
            requested = "mobile.html" if self.path == "/" else self.path.removeprefix("/static/")
            self.serve_static(requested)
            return

        self.write_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        if self.path == "/api/desktop-heartbeat":
            self.server.last_desktop_heartbeat = time.monotonic()  # type: ignore[attr-defined]
            self.write_json({"ok": True})
            return

        if self.path not in {"/api/ask", "/api/activity-risk"}:
            self.write_json({"error": "Not found"}, status=404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            if self.path == "/api/ask":
                question = str(payload.get("question", ""))
                self.write_json(assistant.ask(question))
            else:
                self.write_json(evaluate_activity_plan(payload))
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=500)

    def serve_static(self, requested: str) -> None:
        safe_name = requested.replace("\\", "/").lstrip("/")
        file_path = (STATIC_DIR / safe_name).resolve()
        if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
            self.write_json({"error": "Invalid path"}, status=400)
            return
        if not file_path.exists() or file_path.is_dir():
            self.write_json({"error": "Static file not found"}, status=404)
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        if file_path.suffix == ".webmanifest":
            content_type = "application/manifest+json"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type = f"{content_type}; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Max-Age", "86400")

    def log_message(self, format: str, *args: Any) -> None:
        if sys.stderr:
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))


def run(host: str = HOST, port: int = PORT) -> None:
    httpd = ThreadingHTTPServer((host, port), WeatherRagHandler)
    httpd.last_desktop_heartbeat = time.monotonic()
    httpd.desktop_shutdown = os.getenv("WEATHER_DESKTOP_SHUTDOWN_ON_IDLE") == "1"
    if httpd.desktop_shutdown:
        start_desktop_shutdown_monitor(httpd)
    if sys.stdout:
        print(f"Outdoor Activity Weather Risk Decision Assistant running at http://{host}:{port}")
    httpd.serve_forever()


def start_desktop_shutdown_monitor(httpd: ThreadingHTTPServer) -> None:
    def monitor() -> None:
        while True:
            time.sleep(2)
            last_heartbeat = getattr(httpd, "last_desktop_heartbeat", time.monotonic())
            if time.monotonic() - last_heartbeat > DESKTOP_HEARTBEAT_TIMEOUT:
                httpd.shutdown()
                return

    threading.Thread(target=monitor, daemon=True).start()


if __name__ == "__main__":
    env_host = os.getenv("WEATHER_SERVER_HOST", HOST)
    env_port = int(os.getenv("WEATHER_SERVER_PORT", str(PORT)))
    run(env_host, env_port)
