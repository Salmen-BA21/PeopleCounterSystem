"""People Counter — pywebview desktop entry point."""

from __future__ import annotations

import socket
import sys
import threading
import time

import uvicorn
import webview

from src.server import create_app, VideoStreamWorker, PeopleCounter, source_with_credentials
from src.count_people import line_from_args, parse_line


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _ThreadedServer(uvicorn.Server):
    """uvicorn.Server subclass that disables signal handlers for threading."""

    def install_signal_handlers(self):
        pass


def main() -> None:
    port = _find_free_port()

    counter = PeopleCounter(model="yolo26n.pt", confidence=0.35, device="cpu")
    worker = VideoStreamWorker(source="", counter=counter, jpeg_quality=75, model_name="yolo26n.pt")
    app = create_app(worker)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = _ThreadedServer(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    time.sleep(1.0)

    window = webview.create_window(
        title="People Counter",
        url=f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        resizable=True,
    )
    webview.start()
    sys.exit(0)


if __name__ == "__main__":
    main()
