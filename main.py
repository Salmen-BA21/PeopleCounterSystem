"""People Counter — pywebview desktop entry point."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import torch
import uvicorn
import webview

from src.count_people import parse_line
from src.prereqs import ensure_prerequisites, diagnose as prereq_diagnose
from src.server import (
    DEFAULT_LINE_FILE,
    VideoStreamWorker,
    PeopleCounter,
    bundled_path,
    create_app,
    resource_path,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write_diagnostics(path: Path) -> None:
    """Why-is-it-slow self-check, written beside the exe on every launch."""
    lines = [f"python: {sys.version.split()[0]}  frozen: {getattr(sys, 'frozen', False)}"]
    try:
        lines.append(f"torch: {torch.__version__}  cuda runtime: {torch.version.cuda}")
        if torch.cuda.is_available():
            free_b, total_b = torch.cuda.mem_get_info(0)
            lines.append(f"gpu: {torch.cuda.get_device_name(0)}  (CUDA active)  vram: {(total_b - free_b) / (1024**3):.1f} / {total_b / (1024**3):.1f} GB used")
        else:
            try:
                torch.cuda.init()
                lines.append("gpu: NONE — no NVIDIA device visible to PyTorch (check driver)")
            except Exception as exc:
                lines.append(f"gpu: UNUSABLE — {exc}")
    except Exception as exc:
        lines.append(f"torch import failed: {exc}")
    for name in ("yolo26n.pt", "yolo26s.pt", "yolo26m.pt", "yolo26l.pt", "yolo26x.pt"):
        where = "exe-dir" if resource_path(name).exists() else ("bundled" if bundled_path(name).exists() else "MISSING")
        lines.append(f"{name}: {where}")
    lines.append(f"web dir: {'ok' if bundled_path('web').exists() else 'MISSING'}")
    try:
        lines.append(prereq_diagnose())
    except Exception as exc:
        lines.append(f"prereqs: check failed — {exc}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class _ThreadedServer(uvicorn.Server):
    """uvicorn.Server subclass that disables signal handlers for threading."""

    def install_signal_handlers(self):
        pass


def _write_error(path: Path, exc: Exception, runtime: str) -> None:
    """Append a traceback block to the error log for later diagnosis."""
    lines = [
        f"--- webview.start() failed (runtime={runtime}) ---",
        f"Exception: {exc}",
        "Traceback:",
        traceback.format_exc(),
        "",
    ]
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass

    # Also print for console builds / --diag
    print(f"[WARN] webview.start() failed (runtime={runtime}): {exc}")


def _msgbox_browser_fallback(error_log: Path) -> None:
    """Tell the user via Win32 MessageBox that the app will open in the browser."""
    import ctypes

    detail = ""
    if error_log.exists():
        try:
            text = error_log.read_text(encoding="utf-8")
            # Show only the last error block (most recent failure)
            blocks = text.strip().split("--- webview.start() failed")
            if blocks:
                last = blocks[-1].strip()
                # Trim to first 3 lines of the last block
                short = "\n".join(last.splitlines()[:5])
                detail = f"\n\nLast error:\n{short}"
        except OSError:
            pass

    ctypes.windll.user32.MessageBoxW(
        0,
        f"The native window could not be started.\n"
        f"The app will open in your browser instead.\n\n"
        f"Full details: {error_log.name}{detail}",
        "People Counter",
        0x00000030,  # MB_ICONWARNING
    )


def main() -> None:
    try:
        write_diagnostics(resource_path("exe_diag.txt"))
    except OSError:
        pass

    if "--diag" in sys.argv:
        return

    port = _find_free_port()

    device = "cuda"
    if not torch.cuda.is_available():
        print("[WARN] CUDA not available, falling back to CPU.")
        device = "cpu"

    model_file = "yolo26n.pt"

    initial_line = None
    if DEFAULT_LINE_FILE.exists():
        try:
            initial_line = parse_line(DEFAULT_LINE_FILE.read_text().strip())
        except (OSError, ValueError) as exc:
            print(f"[WARN] Could not read saved line: {exc}")

    counter = PeopleCounter(model=model_file, confidence=0.35, device=device, count_line=initial_line)
    worker = VideoStreamWorker(source="", counter=counter, jpeg_quality=75, model_name=model_file)
    app = create_app(worker)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = _ThreadedServer(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    time.sleep(1.0)

    ensure_prerequisites()

    window = webview.create_window(
        title="People Counter",
        url=f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        resizable=True,
    )

    # --- Attempt 1: default runtime (netfx) ---
    error_log = resource_path("webview_error.txt")
    try:
        webview.start()
        sys.exit(0)
    except Exception as exc:
        _write_error(error_log, exc, runtime="netfx")

    # --- Attempt 2: coreclr fallback (.NET Core runtime) ---
    os.environ["PYTHONNET_RUNTIME"] = "coreclr"
    try:
        # Re-import clr with the new runtime setting
        import importlib
        import clr as _clr_mod  # noqa: F401
        importlib.reload(_clr_mod)

        window2 = webview.create_window(
            title="People Counter",
            url=f"http://127.0.0.1:{port}",
            width=1280,
            height=800,
            resizable=True,
        )
        webview.start()
        sys.exit(0)
    except Exception as exc:
        _write_error(error_log, exc, runtime="coreclr")

    # --- Both runtimes failed: fall back to browser ---
    _msgbox_browser_fallback(error_log)
    webbrowser.open(f"http://127.0.0.1:{port}")
    try:
        while True:
            time.sleep(3600)  # keep serving while the tab is open
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
