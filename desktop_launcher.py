from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser

from src.weather_rag.server import HOST, PORT, run


def find_port(start: int = PORT, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("没有找到可用的本地端口")


def main() -> None:
    port = find_port()
    os.environ["WEATHER_DESKTOP_SHUTDOWN_ON_IDLE"] = "1"
    server_thread = threading.Thread(target=run, kwargs={"host": HOST, "port": port}, daemon=False)
    server_thread.start()
    time.sleep(1.2)
    if os.getenv("WEATHER_DESKTOP_NO_BROWSER") != "1":
        webbrowser.open(f"http://{HOST}:{port}/")
    server_thread.join()


if __name__ == "__main__":
    main()
