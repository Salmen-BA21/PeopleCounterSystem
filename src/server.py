"""FastAPI WebSocket server for People Counter system."""

from __future__ import annotations

import argparse
import asyncio
import csv
import ctypes
import os
import platform
import struct
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import torch
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.count_people import (
    PeopleCounter,
    default_entering_direction,
    line_from_args,
    line_orientation,
    parse_line,
    source_with_credentials,
)
from src import discover_cameras


def resource_path(relative: str) -> Path:
    """Resolve a path that works in both dev and PyInstaller-frozen mode."""
    if getattr(sys, "frozen", False):
        # When frozen, resolve relative to the EXE directory (allows user-replaceable files)
        return Path(sys.executable).parent / relative
    return Path(__file__).resolve().parent.parent / relative


def bundled_path(relative: str) -> Path:
    """Resolve bundled read-only data (web/, models) — lives in the temp extraction dir."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent / relative


ROOT_DIR = resource_path(".")
WEB_DIR = bundled_path("web")
UPLOADS_DIR = resource_path("uploads")
REPORTS_DIR = resource_path("reports")
DEFAULT_LINE_FILE = resource_path("line.txt")
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class LineUpdateRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    entering_direction: str | None = None


class SourceChangeRequest(BaseModel):
    source: str


class CameraConnectRequest(BaseModel):
    host: str
    port: int = 80
    username: str
    password: str
    profile_token: str | None = None


class CameraProfilesRequest(BaseModel):
    host: str
    port: int = 80
    username: str
    password: str


class ModelChangeRequest(BaseModel):
    model: str


class DeviceChangeRequest(BaseModel):
    device: str


YOLO26_MODELS = [
    {"file": "yolo26n.pt", "name": "Nano", "label": "Fast", "speed": "39 ms", "accuracy": "40.9%", "params": "2.4 M"},
    {"file": "yolo26s.pt", "name": "Small", "label": "Balanced", "speed": "87 ms", "accuracy": "48.6%", "params": "9.5 M"},
    {"file": "yolo26m.pt", "name": "Medium", "label": "Accurate", "speed": "220 ms", "accuracy": "53.1%", "params": "20.4 M"},
    {"file": "yolo26l.pt", "name": "Large", "label": "High accuracy", "speed": "286 ms", "accuracy": "55.0%", "params": "24.8 M"},
    {"file": "yolo26x.pt", "name": "X-Large", "label": "Maximum", "speed": "526 ms", "accuracy": "57.5%", "params": "55.7 M"},
]


def _resolve_model_path(filename: str) -> str:
    """Resolve a model filename to an absolute path, checking root then bundled."""
    for resolver in (resource_path, bundled_path):
        p = resolver(filename)
        if p.exists():
            return str(p)
    return filename  # let Ultralytics handle download


def canonical_device(device: str) -> str:
    """One name per device so UI chip comparisons always match ("cuda" == "cuda:0")."""
    return "cuda:0" if device == "cuda" else device


_switch_lock = threading.Lock()  # ponytail: single lock — model/device switches are rare


def restart_worker_with(worker_instance: VideoStreamWorker, job) -> None:
    """Stop the worker, apply job() off-thread, restart. Serialized; restarts even if job fails."""
    with _switch_lock:
        worker_instance.stop()
        try:
            job()
        finally:
            worker_instance.start()


class VideoStreamWorker:
    """Worker running in a background thread for frame capture and inference."""

    def __init__(
        self,
        source: str,
        counter: PeopleCounter,
        jpeg_quality: int = 75,
        model_name: str = "",
    ) -> None:
        self.source = source
        self.counter = counter
        self.jpeg_quality = jpeg_quality
        self.model_name = model_name
        self.running = False
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.switch_source_requested: str | None = None
        self.generation = 0  # bumped by start(); a stale loop exits even if stop()'s join timed out

        self.latest_jpeg: bytes | None = None
        self.latest_timestamp_ms: int = 0
        self.latest_counts: dict[str, Any] = counter.get_counts()
        self.frame_id: int = 0
        self.fps_measured: float = 0.0
        self.width: int = 0
        self.height: int = 0
        self.source_fps: float = 20.0
        self.last_frame_work: float = 0.0

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.generation += 1
        if sys.platform == "win32":
            ctypes.windll.winmm.timeBeginPeriod(1)  # default 15.6ms sleep granularity ruins frame pacing
        self.thread = threading.Thread(target=self._run_loop, args=(self.generation,), daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if sys.platform == "win32":
            ctypes.windll.winmm.timeEndPeriod(1)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def set_source(self, new_source: str) -> None:
        with self.lock:
            self.switch_source_requested = new_source

    def _log_source_opened(self, opened_at: float, source: str) -> None:
        print(
            f"[INFO] Loaded video source in {time.perf_counter() - opened_at:.2f}s  "
            f"model: {self.model_name or 'unknown'}  "
            f"fps: {self.source_fps:.2f}  resolution: {self.width}x{self.height}  source: {source}"
        )

    def _run_loop(self, generation: int) -> None:
        capture = None
        is_file_source = False

        frame_count = 0
        start_time = time.perf_counter()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]

        if self.source:
            opened_at = time.perf_counter()
            capture = cv2.VideoCapture(self.source)
            if capture.isOpened():
                self.width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
                self.height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
                self.source_fps = capture.get(cv2.CAP_PROP_FPS) or 20.0
                is_file_source = not self.source.startswith("rtsp://") and not str(self.source).isdigit()
                self._log_source_opened(opened_at, self.source)
            else:
                print(f"[WARN] Could not open video source: {self.source}")
                capture.release()
                capture = None

        try:
            while self.running and generation == self.generation:
                # Handle dynamic source switch
                with self.lock:
                    if self.switch_source_requested is not None:
                        new_target = self.switch_source_requested
                        self.switch_source_requested = None
                        if capture:
                            capture.release()
                        switch_started = time.perf_counter()
                        new_cap = cv2.VideoCapture(new_target)
                        if new_cap.isOpened():
                            capture = new_cap
                            self.source = new_target
                            self.counter.reset_counts()
                            self.width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
                            self.height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
                            self.source_fps = capture.get(cv2.CAP_PROP_FPS) or 20.0
                            is_file_source = not self.source.startswith("rtsp://") and not str(self.source).isdigit()
                            self._log_source_opened(switch_started, new_target)
                        else:
                            print(f"[WARN] Failed to open switched source: {new_target}")
                            capture = cv2.VideoCapture(self.source) if self.source else None

                if capture is None:
                    time.sleep(0.01)
                    continue

                # Skip queued frames when we can't keep up — keeps output FPS
                # near native for files, and keeps counts current for live sources.
                if self.source_fps > 0 and self.last_frame_work > (1.0 / self.source_fps):
                    skips = min(int(self.last_frame_work * self.source_fps) - 1, 5)
                    for _ in range(skips):
                        if not capture.grab():
                            break

                frame_started = time.perf_counter()
                ok, frame = capture.read()
                if not ok:
                    if is_file_source:
                        # Loop video file continuously
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        time.sleep(0.01)
                        continue

                annotated, counts = self.counter.process_frame(frame)
                now_ms = int(time.time() * 1000)

                ok_enc, jpeg_buf = cv2.imencode(".jpg", annotated, encode_param)
                if not ok_enc:
                    continue

                jpeg_bytes = jpeg_buf.tobytes()

                frame_count += 1
                elapsed = time.perf_counter() - start_time
                if elapsed >= 1.0:
                    self.fps_measured = round(frame_count / elapsed, 1)
                    frame_count = 0
                    start_time = time.perf_counter()

                with self.lock:
                    self.latest_jpeg = jpeg_bytes
                    self.latest_timestamp_ms = now_ms
                    self.latest_counts = counts
                    self.frame_id += 1

                # Real-time pacing for video files: sleep only the leftover time
                self.last_frame_work = time.perf_counter() - frame_started
                if is_file_source and self.source_fps > 0:
                    time.sleep(max(0.001, (1.0 / self.source_fps) - self.last_frame_work))
        finally:
            if capture is not None:
                capture.release()

    def get_latest_frame(self) -> tuple[int, bytes | None, int]:
        with self.lock:
            return self.frame_id, self.latest_jpeg, self.latest_timestamp_ms

    def get_latest_counts(self) -> dict[str, Any]:
        with self.lock:
            data = dict(self.latest_counts)
            data["fps"] = self.fps_measured
            if self.counter.count_line:
                data["line"] = list(self.counter.count_line)
            data["resolution"] = [self.width, self.height]
            data["source"] = self.source
            return data


worker: VideoStreamWorker | None = None


def write_daily_csv(worker: VideoStreamWorker, day: date, reports_dir: Path = REPORTS_DIR) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    counts = worker.counter.get_counts()
    path = reports_dir / f"{day.isoformat()}.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "in", "out", "current"])
        writer.writerow([day.isoformat(), counts["in"], counts["out"], counts["current"]])
    return path


def _seconds_until_midnight() -> float:
    now = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (midnight - now).total_seconds()


def midnight_reset_loop(worker: VideoStreamWorker) -> None:
    while True:
        day = date.today()
        time.sleep(_seconds_until_midnight() + 1.0)
        write_daily_csv(worker, day)
        worker.counter.reset_counts()
        print(f"[INFO] Midnight reset — saved {day.isoformat()}.csv and reset counters")


def create_app(worker_instance: VideoStreamWorker) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        worker_instance.start()
        midnight_thread = threading.Thread(target=midnight_reset_loop, args=(worker_instance,), daemon=True)
        midnight_thread.start()
        yield
        worker_instance.stop()

    app = FastAPI(title="People Counter Web System", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/config")
    async def get_config() -> dict[str, Any]:
        line = worker_instance.counter.count_line
        return {
            "source": worker_instance.source,
            "line": list(line) if line else None,
            "orientation": line_orientation(line) if line else None,
            "entering_direction": worker_instance.counter.entering_direction,
            "width": worker_instance.width,
            "height": worker_instance.height,
            "fps": worker_instance.fps_measured,
            "running": worker_instance.running,
            "device": canonical_device(worker_instance.counter.device),
            "model": Path(worker_instance.model_name).name if worker_instance.model_name else "",
        }

    @app.get("/api/videos")
    async def list_videos() -> dict[str, list[str]]:
        videos = [p.name for p in ROOT_DIR.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
        if UPLOADS_DIR.exists():
            videos.extend(f"uploads/{p.name}" for p in UPLOADS_DIR.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
        return {"videos": sorted(set(videos))}

    @app.post("/api/source")
    async def change_source(req: SourceChangeRequest) -> dict[str, Any]:
        target = req.source.strip()
        if not target:
            raise HTTPException(status_code=400, detail="Source cannot be empty")
        
        # If relative path, resolve against root
        resolved_path = ROOT_DIR / target
        if resolved_path.exists():
            target_str = str(resolved_path)
        else:
            target_str = target

        worker_instance.set_source(target_str)
        return {"status": "ok", "source": target}

    @app.post("/api/upload")
    async def upload_video(file: UploadFile = File(...)) -> dict[str, Any]:
        filename = Path(file.filename or "upload.mp4").name
        ext = Path(filename).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported format. Allowed: {VIDEO_EXTENSIONS}")

        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = UPLOADS_DIR / filename
        content = await file.read()
        dest_path.write_bytes(content)

        worker_instance.set_source(str(dest_path))
        return {"status": "ok", "filename": filename, "source": f"uploads/{filename}"}


    @app.get("/api/cameras")
    async def discover_cameras_endpoint(timeout: float = 3.0) -> dict[str, Any]:
        from urllib.parse import urlparse

        def _normalize(dev: dict[str, Any]) -> tuple[str | None, int | None]:
            host = dev.get("host")
            port = dev.get("port")
            if not host:
                xaddrs = dev.get("xaddrs")
                if isinstance(xaddrs, list):
                    xaddrs = xaddrs[0] if xaddrs else None
                if xaddrs:
                    try:
                        parsed = urlparse(str(xaddrs))
                        host, port = parsed.hostname, parsed.port
                    except ValueError:
                        pass
            if not host:
                return None, None
            return str(host), int(port or 80)

        def _run() -> list[dict[str, Any]]:
            return discover_cameras.discover(timeout)

        devices = await asyncio.get_running_loop().run_in_executor(None, _run)
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for dev in devices:
            host, port = _normalize(dev)
            if not host or port is None or (host, port) in seen:
                continue
            seen.add((host, port))
            result.append(
                {
                    "host": host,
                    "port": port,
                    "name": dev.get("Name") or dev.get("name"),
                }
            )
        return {"devices": result}

    @app.post("/api/cameras/profiles")
    async def camera_profiles(req: CameraProfilesRequest) -> dict[str, Any]:
        def _run() -> list[dict[str, Any]]:
            return discover_cameras.list_profiles(req.host, req.port, req.username, req.password)

        try:
            profiles = await asyncio.get_running_loop().run_in_executor(None, _run)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not load profiles: {exc}")

        return {"profiles": profiles}

    @app.post("/api/cameras/connect")
    async def connect_camera(req: CameraConnectRequest) -> dict[str, Any]:
        def _run() -> str:
            info = discover_cameras.rtsp_uri(
                req.host, req.port, req.username, req.password, req.profile_token
            )
            return source_with_credentials(info["rtsp_uri"], req.username, req.password)

        try:
            uri = await asyncio.get_running_loop().run_in_executor(None, _run)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not connect to camera: {exc}")

        worker_instance.set_source(uri)
        return {"status": "ok", "host": req.host}


    @app.get("/api/models")
    async def list_models() -> dict[str, Any]:
        current = Path(worker_instance.model_name).name if worker_instance.model_name else ""
        models = []
        for m in YOLO26_MODELS:
            resolved = _resolve_model_path(m["file"])
            downloaded = Path(resolved).exists() if resolved != m["file"] else (Path(m["file"]).exists() or bundled_path(m["file"]).exists())
            models.append({**m, "downloaded": downloaded, "active": m["file"] == current})
        return {"models": models, "current": current}

    @app.post("/api/model")
    async def change_model(req: ModelChangeRequest) -> dict[str, Any]:
        target = req.model.strip()
        if not any(m["file"] == target for m in YOLO26_MODELS):
            raise HTTPException(status_code=400, detail=f"Unknown model: {target}")
        model_path = _resolve_model_path(target)

        def _work() -> None:
            worker_instance.counter.set_model(model_path)
            worker_instance.model_name = model_path

        try:
            # YOLO() load takes seconds — run off the event loop, worker stopped meanwhile
            await asyncio.get_running_loop().run_in_executor(None, restart_worker_with, worker_instance, _work)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not load model: {exc}")
        return {"status": "ok", "model": target}

    @app.get("/api/hardware")
    async def get_hardware() -> dict[str, Any]:
        gpus = []
        cuda_error = None
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                free_b, _total_b = torch.cuda.mem_get_info(i)
                gpus.append({
                    "index": i,
                    "name": torch.cuda.get_device_name(i),
                    "vram_gb": round(props.total_memory / (1024 ** 3), 1),
                    # low free VRAM => Windows spills CUDA to RAM => massive slowdown
                    "vram_free_gb": round(free_b / (1024 ** 3), 1),
                })
        else:
            try:
                torch.cuda.init()
                cuda_error = "No NVIDIA GPU visible to PyTorch"
            except Exception as exc:
                cuda_error = str(exc)
        return {
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": str(torch.version.cuda) if torch.cuda.is_available() else None,
            "cuda_error": cuda_error,
            "gpus": gpus,
            "cpu": platform.processor() or "Unknown CPU",
            "current_device": canonical_device(worker_instance.counter.device),
        }

    @app.post("/api/device")
    async def change_device(req: DeviceChangeRequest) -> dict[str, Any]:
        device = canonical_device(req.device.strip())
        if device.startswith("cuda"):
            if not torch.cuda.is_available():
                raise HTTPException(status_code=400, detail="CUDA is not available on this system")
            if ":" in device:
                idx = int(device.split(":")[1])
                if idx >= torch.cuda.device_count():
                    raise HTTPException(status_code=400, detail=f"GPU {idx} not found")
        elif device != "cpu":
            raise HTTPException(status_code=400, detail=f"Invalid device: {device}")

        def _work() -> None:
            worker_instance.counter.set_device(device)

        try:
            await asyncio.get_running_loop().run_in_executor(None, restart_worker_with, worker_instance, _work)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not switch device: {exc}")
        return {"status": "ok", "device": device}


    @app.get("/api/line")
    async def get_line() -> dict[str, Any]:
        line = worker_instance.counter.count_line
        return {
            "line": list(line) if line else None,
            "orientation": line_orientation(line) if line else None,
            "entering_direction": worker_instance.counter.entering_direction,
        }

    @app.post("/api/line")
    async def set_line(req: LineUpdateRequest) -> dict[str, Any]:
        x1, y1, x2, y2 = req.x1, req.y1, req.x2, req.y2
        worker_instance.counter.set_line(x1, y1, x2, y2, req.entering_direction)
        try:
            DEFAULT_LINE_FILE.write_text(f"{x1},{y1},{x2},{y2}\n")
        except OSError:
            pass
        return {
            "status": "ok",
            "line": [x1, y1, x2, y2],
            "orientation": line_orientation((x1, y1, x2, y2)),
            "entering_direction": worker_instance.counter.entering_direction,
        }

    @app.post("/api/reset")
    async def reset_counts() -> dict[str, str]:
        worker_instance.counter.reset_counts()
        return {"status": "ok"}

    @app.websocket("/ws/video")
    async def ws_video(websocket: WebSocket) -> None:
        await websocket.accept()
        last_sent_id = -1
        try:
            while True:
                frame_id, frame_bytes, ts_ms = worker_instance.get_latest_frame()
                if frame_id != last_sent_id and frame_bytes is not None:
                    last_sent_id = frame_id
                    # 8-byte big-endian timestamp header + JPEG payload
                    header = struct.pack(">Q", ts_ms)
                    await websocket.send_bytes(header + frame_bytes)
                await asyncio.sleep(0.005)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    @app.websocket("/ws/counts")
    async def ws_counts(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                counts_data = worker_instance.get_latest_counts()
                await websocket.send_json(counts_data)
                await asyncio.sleep(0.05)  # 20Hz count telemetry
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="People Counter Web Server")
    parser.add_argument("--source", default=None, help="Video file or RTSP stream URL (omit to pick one from the web app)")
    parser.add_argument("--username", help="RTSP username")
    parser.add_argument("--password", help="RTSP password")
    parser.add_argument("--model", default="yolo26n.pt", help="YOLO model file")
    parser.add_argument("--confidence", type=float, default=0.35, help="Detection confidence")
    parser.add_argument("--device", default="cuda", help="Inference device (cuda or cpu)")
    parser.add_argument("--line", help="Line x1,y1,x2,y2")
    parser.add_argument("--line-file", help="Path to line text file")
    parser.add_argument("--entering-direction", help="Direction considered as IN")
    parser.add_argument("--host", default="0.0.0.0", help="Web server host")
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    parser.add_argument("--jpeg-quality", type=int, default=75, help="MJPEG encoding quality (1-100)")
    args = parser.parse_args()

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        print("[WARN] CUDA not available, falling back to CPU.")
        device = "cpu"

    model_path = args.model
    if not Path(model_path).is_absolute():
        exe_dir = resource_path(model_path)
        bundled = bundled_path(model_path)
        if exe_dir.exists():
            model_path = str(exe_dir)
        elif bundled.exists():
            model_path = str(bundled)

    source = source_with_credentials(args.source, args.username, args.password) if args.source else ""
    initial_line = None
    line_file = args.line_file or (str(DEFAULT_LINE_FILE) if DEFAULT_LINE_FILE.exists() else None)
    if args.line or line_file:
        try:
            initial_line = line_from_args(parse_line(args.line) if args.line else None, line_file, 1280, 720)
        except Exception as e:
            print(f"[WARN] Could not parse line configuration: {e}")

    counter = PeopleCounter(
        model=model_path,
        confidence=args.confidence,
        device=device,
        count_line=initial_line,
        entering_direction=args.entering_direction,
    )

    global worker
    worker = VideoStreamWorker(
        source=source,
        counter=counter,
        jpeg_quality=args.jpeg_quality,
        model_name=model_path,
    )

    app = create_app(worker)
    print(f"\n[INFO] Starting People Counter Web App at http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
