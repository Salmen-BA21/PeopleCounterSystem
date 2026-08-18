"""FastAPI WebSocket server for People Counter system."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import struct
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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.count_people import (
    PeopleCounter,
    line_from_args,
    line_orientation,
    parse_line,
    source_with_credentials,
)
from src import discover_cameras

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
UPLOADS_DIR = ROOT_DIR / "uploads"
REPORTS_DIR = ROOT_DIR / "reports"
DEFAULT_LINE_FILE = ROOT_DIR / "line.txt"
SOURCES_FILE = ROOT_DIR / "sources.json"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
MODEL_PRESETS = {"quick": "yolo26n.pt", "precise": "yolo26s.pt"}


class LineUpdateRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    entering_direction: str | None = None


class AddSourceRequest(BaseModel):
    source: str
    name: str | None = None


class CameraConnectRequest(BaseModel):
    host: str
    port: int = 8000
    username: str | None = None
    password: str | None = None
    profile_token: str | None = None


class ModelRequest(BaseModel):
    model: str


class RunningRequest(BaseModel):
    running: bool


class CameraProfilesRequest(BaseModel):
    host: str
    port: int = 80
    username: str
    password: str


class VideoStreamWorker:
    """Worker running in a background thread for frame capture and inference."""

    def __init__(
        self,
        source: str,
        counter: PeopleCounter,
        jpeg_quality: int = 75,
        model_name: str = "",
        model_key: str = "quick",
        source_id: str = "source",
        name: str = "source",
    ) -> None:
        self.source = source
        self.counter = counter
        self.jpeg_quality = jpeg_quality
        self.model_name = model_name
        self.model_key = model_key
        self.source_id = source_id
        self.name = name
        self.running = False
        self.paused = False
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()

        self.latest_jpeg: bytes | None = None
        self.latest_timestamp_ms: int = 0
        self.latest_counts: dict[str, Any] = counter.get_counts()
        self.frame_id: int = 0
        self.fps_measured: float = 0.0
        self.width: int = 0
        self.height: int = 0
        self.source_fps: float = 20.0

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def _log_source_opened(self, opened_at: float, source: str) -> None:
        print(
            f"[INFO] Loaded video source in {time.perf_counter() - opened_at:.2f}s  "
            f"model: {self.model_name or 'unknown'}  "
            f"fps: {self.source_fps:.2f}  resolution: {self.width}x{self.height}  "
            f"source: {source}  id: {self.source_id}"
        )

    def _run_loop(self) -> None:
        capture = None
        is_file_source = False

        frame_count = 0
        start_time = time.perf_counter()
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]

        def open_source() -> cv2.VideoCapture | None:
            opened = cv2.VideoCapture(self.source)
            if not opened.isOpened():
                opened.release()
                return None
            if self.source.startswith("rtsp://"):
                opened.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.width = int(opened.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
            self.height = int(opened.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
            self.source_fps = opened.get(cv2.CAP_PROP_FPS) or 20.0
            return opened

        if self.source:
            opened_at = time.perf_counter()
            capture = open_source()
            if capture is not None:
                is_file_source = not self.source.startswith("rtsp://") and not str(self.source).isdigit()
                self._log_source_opened(opened_at, self.source)
            else:
                print(f"[WARN] Could not open video source: {self.source}")

        consecutive_failures = 0
        try:
            while self.running:
                if self.paused:
                    time.sleep(0.05)
                    continue
                if capture is None:
                    time.sleep(0.01)
                    consecutive_failures += 1
                    # ~5s: source not available yet (e.g. camera booting)
                    if self.source and consecutive_failures >= 500:
                        consecutive_failures = 0
                        capture = open_source()
                        if capture is not None:
                            is_file_source = not self.source.startswith("rtsp://") and not str(self.source).isdigit()
                            print(f"[INFO] Reopened source: {self.source_id}")
                    continue

                ok, frame = capture.read()
                if not ok:
                    if is_file_source:
                        # Loop video file continuously
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    consecutive_failures += 1
                    if consecutive_failures >= 300:  # ~3s of failed reads: stream dropped
                        print(f"[WARN] Source lost, reopening: {self.source_id}")
                        capture.release()
                        capture = open_source()
                        is_file_source = not self.source.startswith("rtsp://") and not str(self.source).isdigit()
                        if capture is not None:
                            print(f"[INFO] Reopened source: {self.source_id}")
                        consecutive_failures = 0
                    else:
                        time.sleep(0.01)
                    continue
                consecutive_failures = 0

                # Drain RTSP buffer: pull queued frames, keep only the freshest
                if not is_file_source:
                    while True:
                        ok_next, next_frame = capture.read()
                        if not ok_next:
                            break
                        frame = next_frame

                started = time.perf_counter()
                annotated, counts = self.counter.process_frame(frame)
                now_ms = int(time.time() * 1000)

                ok_enc, jpeg_buf = cv2.imencode(".jpg", annotated, encode_param)
                if not ok_enc:
                    continue

                jpeg_bytes = jpeg_buf.tobytes()

                infer_elapsed = time.perf_counter() - started
                frame_skip = max(1, int(infer_elapsed * self.source_fps))

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

                # Frame pacing for video files
                if is_file_source and self.source_fps > 0:
                    time.sleep(max(0.001, (1.0 / self.source_fps) * 0.4))
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


class StreamManager:
    """Owns one VideoStreamWorker per source; persists sources to sources.json."""

    def __init__(self, model: str, confidence: float, device: str, jpeg_quality: int) -> None:
        self.model = model
        self.confidence = confidence
        self.device = device
        self.jpeg_quality = jpeg_quality
        self.sources: dict[str, VideoStreamWorker] = {}
        self.config_path = SOURCES_FILE

    def _next_id(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "source"
        sid = base
        n = 2
        while sid in self.sources:
            sid = f"{base}-{n}"
            n += 1
        return sid

    def add(
        self,
        source: str,
        name: str | None = None,
        *,
        line: tuple[int, int, int, int] | None = None,
        entering_direction: str | None = None,
        model: str | None = None,
    ) -> VideoStreamWorker:
        display_name = name or (Path(source).stem if not source.startswith("rtsp://") else source)
        sid = self._next_id(display_name)
        model_key = model if model in MODEL_PRESETS else None
        model_path = MODEL_PRESETS[model_key] if model_key else self.model
        counter = PeopleCounter(
            model=model_path,
            confidence=self.confidence,
            device=self.device,
            count_line=line,
            entering_direction=entering_direction,
        )
        worker = VideoStreamWorker(
            source=source,
            counter=counter,
            jpeg_quality=self.jpeg_quality,
            model_name=model_path,
            model_key=model_key or "quick",
            source_id=sid,
            name=display_name,
        )
        worker.start()
        self.sources[sid] = worker
        self._persist()
        return worker

    def remove(self, source_id: str) -> None:
        worker = self.sources.pop(source_id, None)
        if worker:
            worker.stop()
            self._persist()

    def get(self, source_id: str) -> VideoStreamWorker | None:
        return self.sources.get(source_id)

    def set_line(self, source_id: str, x1: int, y1: int, x2: int, y2: int, entering_direction: str | None = None) -> VideoStreamWorker | None:
        worker = self.sources.get(source_id)
        if not worker:
            return None
        worker.counter.set_line(x1, y1, x2, y2, entering_direction)
        self._persist()
        return worker

    def reset(self, source_id: str) -> bool:
        worker = self.sources.get(source_id)
        if not worker:
            return False
        worker.counter.reset_counts()
        return True

    def set_model(self, source_id: str, model: str) -> VideoStreamWorker | None:
        if model not in MODEL_PRESETS:
            raise ValueError(f"Unknown model: {model}")
        worker = self.sources.get(source_id)
        if not worker:
            return None
        worker.counter.replace_model(MODEL_PRESETS[model], self.confidence, self.device)
        worker.model_key = model
        worker.model_name = MODEL_PRESETS[model]
        self._persist()
        return worker

    def describe(self, worker: VideoStreamWorker) -> dict[str, Any]:
        data = worker.get_latest_counts()
        data["id"] = worker.source_id
        data["name"] = worker.name
        data["running"] = not worker.paused
        data["model"] = worker.model_key
        return data

    def list_sources(self) -> list[dict[str, Any]]:
        return [self.describe(w) for w in self.sources.values()]

    def _persist(self) -> None:
        entries = []
        for worker in self.sources.values():
            line = worker.counter.count_line
            entries.append(
                {
                    "id": worker.source_id,
                    "name": worker.name,
                    "source": worker.source,
                    "line": list(line) if line else None,
                    "entering_direction": worker.counter.entering_direction,
                    "model": worker.model_key,
                }
            )
        try:
            self.config_path.write_text(json.dumps(entries, indent=2))
        except OSError as exc:
            print(f"[WARN] Could not save sources.json: {exc}")

    def load(self) -> None:
        if not self.config_path.exists():
            return
        try:
            entries = json.loads(self.config_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[WARN] Could not read sources.json: {exc}")
            return
        for entry in entries:
            try:
                self.add(
                    entry["source"],
                    entry.get("name"),
                    line=tuple(entry["line"]) if entry.get("line") else None,
                    entering_direction=entry.get("entering_direction"),
                    model=entry.get("model"),
                )
            except Exception as exc:
                print(f"[WARN] Skipping saved source {entry.get('id', '?')}: {exc}")


manager: StreamManager | None = None


def write_daily_csv(worker: VideoStreamWorker, day: date, reports_dir: Path = REPORTS_DIR) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    counts = worker.counter.get_counts()
    path = reports_dir / f"{day.isoformat()}_{worker.source_id}.csv"
    prev_in = prev_out = 0
    if path.exists():
        try:
            with open(path, newline="") as f:
                rows = list(csv.reader(f))
            if len(rows) > 1:
                prev_in, prev_out = int(rows[1][1]), int(rows[1][2])
        except (OSError, ValueError, IndexError):
            pass
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "in", "out", "current"])
        writer.writerow([day.isoformat(), prev_in + counts["in"], prev_out + counts["out"], counts["current"]])
    return path


def _seconds_until_midnight() -> float:
    now = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (midnight - now).total_seconds()


def midnight_reset_loop(stream_manager: StreamManager) -> None:
    while True:
        day = date.today()
        try:
            time.sleep(_seconds_until_midnight() + 1.0)
            for worker in stream_manager.sources.values():
                path = write_daily_csv(worker, day)
                worker.counter.reset_counts()
                print(f"[INFO] Midnight reset — saved {path.name} and reset counters for {worker.source_id}")
        except Exception as exc:
            print(f"[WARN] Midnight reset failed: {exc}")


def create_app(stream_manager: StreamManager) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        midnight_thread = threading.Thread(target=midnight_reset_loop, args=(stream_manager,), daemon=True)
        midnight_thread.start()
        yield
        for worker in stream_manager.sources.values():
            worker.stop()
            write_daily_csv(worker, date.today())

    app = FastAPI(title="People Counter Web System", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/sources")
    async def list_sources() -> dict[str, Any]:
        return {"sources": stream_manager.list_sources()}

    @app.post("/api/sources")
    async def add_source(req: AddSourceRequest) -> dict[str, Any]:
        target = req.source.strip()
        if not target:
            raise HTTPException(status_code=400, detail="Source cannot be empty")
        resolved_path = ROOT_DIR / target
        source_str = str(resolved_path) if resolved_path.exists() else target
        worker = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: stream_manager.add(source_str, req.name),
        )
        return stream_manager.describe(worker)

    @app.delete("/api/sources/{source_id}")
    async def remove_source(source_id: str) -> dict[str, str]:
        stream_manager.remove(source_id)
        return {"status": "ok"}

    @app.post("/api/sources/{source_id}/line")
    async def set_source_line(source_id: str, req: LineUpdateRequest) -> dict[str, Any]:
        worker = stream_manager.set_line(source_id, req.x1, req.y1, req.x2, req.y2, req.entering_direction)
        if not worker:
            raise HTTPException(status_code=404, detail="Source not found")
        return {
            "status": "ok",
            "line": [req.x1, req.y1, req.x2, req.y2],
            "orientation": line_orientation((req.x1, req.y1, req.x2, req.y2)),
            "entering_direction": worker.counter.entering_direction,
        }

    @app.post("/api/sources/{source_id}/reset")
    async def reset_source_counts(source_id: str) -> dict[str, str]:
        if not stream_manager.reset(source_id):
            raise HTTPException(status_code=404, detail="Source not found")
        return {"status": "ok"}

    @app.post("/api/sources/{source_id}/model")
    async def set_source_model(source_id: str, req: ModelRequest) -> dict[str, Any]:
        if req.model not in MODEL_PRESETS:
            raise HTTPException(status_code=400, detail=f"Unknown model: {req.model}")
        try:
            worker = await asyncio.get_running_loop().run_in_executor(
                None, lambda: stream_manager.set_model(source_id, req.model)
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not load model: {exc}")
        if not worker:
            raise HTTPException(status_code=404, detail="Source not found")
        return stream_manager.describe(worker)

    @app.post("/api/sources/{source_id}/running")
    async def set_source_running(source_id: str, req: RunningRequest) -> dict[str, Any]:
        worker = stream_manager.get(source_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Source not found")
        if req.running:
            worker.resume()
        else:
            worker.pause()
        return {"status": "ok", "running": req.running}

    @app.get("/api/videos")
    async def list_videos() -> dict[str, list[str]]:
        videos = [p.name for p in ROOT_DIR.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
        if UPLOADS_DIR.exists():
            videos.extend(f"uploads/{p.name}" for p in UPLOADS_DIR.glob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
        return {"videos": sorted(set(videos))}

    @app.post("/api/upload")
    async def upload_video(file: UploadFile = File(...)) -> dict[str, Any]:
        filename = Path(file.filename).name
        ext = Path(filename).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported format. Allowed: {VIDEO_EXTENSIONS}")

        if file.size is not None and file.size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            )

        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = UPLOADS_DIR / filename
        uploaded = 0
        try:
            with open(dest_path, "wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    uploaded += len(chunk)
                    if uploaded > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File too large. Maximum size: {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
                        )
                    out.write(chunk)
        except HTTPException:
            dest_path.unlink(missing_ok=True)
            raise

        worker = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: stream_manager.add(str(dest_path), filename),
        )
        return {"status": "ok", "filename": filename, "source": stream_manager.describe(worker)}


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
            if not host or (host, port) in seen:
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
        def _run() -> tuple[dict[str, Any], str]:
            info = discover_cameras.rtsp_uri(
                req.host, req.port, req.username, req.password, req.profile_token
            )
            uri = source_with_credentials(info["rtsp_uri"], req.username, req.password)
            worker = stream_manager.add(uri, req.host)
            return stream_manager.describe(worker), req.host

        try:
            result, host = await asyncio.get_running_loop().run_in_executor(None, _run)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not connect to camera: {exc}")

        return {"status": "ok", "host": host, "source": result}


    @app.get("/api/reports")
    async def list_reports() -> dict[str, Any]:
        if not REPORTS_DIR.exists():
            return {"reports": []}
        reports = []
        for path in sorted(REPORTS_DIR.glob("*.csv"), reverse=True):
            try:
                with open(path, newline="") as f:
                    rows = list(csv.reader(f))
                if len(rows) < 2:
                    continue
                day, source_id = path.stem.split("_", 1)
                worker = stream_manager.get(source_id)
                reports.append(
                    {
                        "filename": path.name,
                        "date": day,
                        "source_id": source_id,
                        "name": worker.name if worker else source_id,
                        "in": int(rows[1][1]),
                        "out": int(rows[1][2]),
                        "current": int(rows[1][3]),
                    }
                )
            except (OSError, ValueError, IndexError):
                continue
        return {"reports": reports}

    @app.get("/api/reports/{filename}")
    async def download_report(filename: str) -> Any:
        path = REPORTS_DIR / Path(filename).name
        if not path.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        return FileResponse(path, media_type="text/csv", filename=path.name)

    @app.websocket("/ws/video/{source_id}")
    async def ws_video(websocket: WebSocket, source_id: str) -> None:
        await websocket.accept()
        worker = stream_manager.get(source_id)
        if worker is None:
            await websocket.close(code=4404)
            return
        last_sent_id = -1
        try:
            while True:
                frame_id, frame_bytes, ts_ms = worker.get_latest_frame()
                if frame_id != last_sent_id and frame_bytes is not None:
                    last_sent_id = frame_id
                    # 8-byte big-endian timestamp header + JPEG payload
                    header = struct.pack(">Q", ts_ms)
                    await websocket.send_bytes(header + frame_bytes)
                await asyncio.sleep(0.005)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    @app.websocket("/ws/counts/{source_id}")
    async def ws_counts(websocket: WebSocket, source_id: str) -> None:
        await websocket.accept()
        worker = stream_manager.get(source_id)
        if worker is None:
            await websocket.close(code=4404)
            return
        try:
            while True:
                counts_data = worker.get_latest_counts()
                await websocket.send_json(counts_data)
                await asyncio.sleep(0.05)  # 20Hz count telemetry
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    @app.websocket("/ws/{path:path}")
    async def ws_unknown(websocket: WebSocket, path: str) -> None:
        await websocket.close(code=4404)

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

    source = source_with_credentials(args.source, args.username, args.password) if args.source else ""
    initial_line = None
    line_file = args.line_file or (str(DEFAULT_LINE_FILE) if DEFAULT_LINE_FILE.exists() else None)
    if args.line or line_file:
        try:
            initial_line = line_from_args(parse_line(args.line) if args.line else None, line_file, 1280, 720)
        except Exception as e:
            print(f"[WARN] Could not parse line configuration: {e}")

    global manager
    manager = StreamManager(
        model=args.model,
        confidence=args.confidence,
        device=device,
        jpeg_quality=args.jpeg_quality,
    )
    manager.load()
    if source and not manager.sources:
        manager.add(source, entering_direction=args.entering_direction, line=initial_line)

    app = create_app(manager)
    print(f"\n[INFO] Starting People Counter Web App at http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
