"""Count people crossing a line in a video file or RTSP stream."""

from __future__ import annotations

import argparse
import time
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import cv2
import numpy as np
import torch
from ultralytics import YOLO


def parse_line(value: str) -> tuple[int, int, int, int]:
    try:
        points = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("line must be x1,y1,x2,y2") from exc
    if len(points) != 4:
        raise argparse.ArgumentTypeError("line must be x1,y1,x2,y2")
    return points


def line_from_args(line: tuple[int, int, int, int] | None, line_file: str | None, width: int, height: int) -> tuple[int, int, int, int]:
    if line and line_file:
        raise ValueError("--line and --line-file cannot be used together")
    if line_file:
        return parse_line(Path(line_file).read_text().strip())
    return line or (width // 2, 0, width // 2, height)


def line_orientation(line: tuple[int, int, int, int]) -> str:
    x1, y1, x2, y2 = line
    return "horizontal" if abs(x2 - x1) >= abs(y2 - y1) else "vertical"


def side_of_line(point: tuple[float, float], line: tuple[int, int, int, int]) -> str:
    x, y = point
    x1, y1, x2, y2 = line
    dx, dy = x2 - x1, y2 - y1
    val = dx * (y - y1) - dy * (x - x1)
    if abs(dx) >= abs(dy):
        return "north" if (val < 0 if dx >= 0 else val > 0) else "south"
    return "west" if (val > 0 if dy >= 0 else val < 0) else "east"


def crossing_direction(
    previous: tuple[float, float],
    current: tuple[float, float],
    line: tuple[int, int, int, int],
) -> str | None:
    before = side_of_line(previous, line)
    after = side_of_line(current, line)
    if before == after:
        return None
    return f"{before}_to_{after}"


def default_entering_direction(line: tuple[int, int, int, int]) -> str:
    return "north_to_south" if line_orientation(line) == "horizontal" else "west_to_east"


def current_people_after_crossing(current_people: int, direction: str, entering_direction: str) -> int:
    if direction == entering_direction:
        return current_people + 1
    return max(0, current_people - 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="video file path or RTSP URL")
    parser.add_argument("--username", help="RTSP username")
    parser.add_argument("--password", help="RTSP password")
    parser.add_argument("--output", default="counted.mp4", help="annotated output video path")
    parser.add_argument("--line", type=parse_line, help="counting line: x1,y1,x2,y2; defaults to a vertical center line")
    parser.add_argument("--line-file", help="file containing x1,y1,x2,y2")
    parser.add_argument(
        "--entering-direction",
        choices=("north_to_south", "south_to_north", "west_to_east", "east_to_west"),
        help="movement direction counted as IN; defaults to north_to_south for horizontal lines and west_to_east for vertical lines",
    )
    parser.add_argument("--display-width", type=int, default=1920, help="maximum preview width")
    parser.add_argument("--display-height", type=int, default=1080, help="maximum preview height")
    parser.add_argument("--no-preview", action="store_true", help="process without opening a preview window")
    parser.add_argument("--model", default="yolo26n.pt", help="Ultralytics model name or path")
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--device", default="cuda", help="inference device (default: cuda)")
    return parser


def source_with_credentials(source: str, username: str | None, password: str | None) -> str:
    if username is None and password is None:
        return source
    if username is None or password is None:
        raise ValueError("--username and --password must be provided together")
    parsed = urlsplit(source)
    if parsed.scheme.lower() != "rtsp":
        raise ValueError("RTSP credentials can only be used with an rtsp:// source")
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, f"{quote(username)}:{quote(password)}@{host}", parsed.path, parsed.query, parsed.fragment))


class PeopleCounter:
    """Manages tracking and line-crossing counting on video frames."""

    def __init__(
        self,
        model: str | Any = "yolo26n.pt",
        confidence: float = 0.35,
        device: str = "cuda",
        count_line: tuple[int, int, int, int] | None = None,
        entering_direction: str | None = None,
        fps: float = 20.0,
    ) -> None:
        self.model = YOLO(model) if isinstance(model, str) else model
        self.confidence = confidence
        self.device = device
        self.fps = fps

        self.count_line = count_line
        self.entering_direction = entering_direction or (default_entering_direction(count_line) if count_line else None)

        self.in_count = 0
        self.out_count = 0
        self.current_people = 0
        self.frame_index = 0
        self.last_crossing = ""
        self.last_crossing_frame = -999
        self.last_centers: dict[int, tuple[float, float]] = {}
        self.crossed_track_directions: dict[int, str] = {}
        self.track_trails: dict[int, deque[tuple[int, int]]] = {}
        self.last_seen: dict[int, int] = {}

    def replace_model(self, model: str | Any, confidence: float | None = None, device: str | None = None) -> None:
        self.model = YOLO(model) if isinstance(model, str) else model
        if confidence is not None:
            self.confidence = confidence
        if device is not None:
            self.device = device

    def set_line(self, x1: int, y1: int, x2: int, y2: int, entering_direction: str | None = None) -> None:
        self.count_line = (x1, y1, x2, y2)
        self.entering_direction = entering_direction or default_entering_direction(self.count_line)
        self.reset_counts()

    def reset_counts(self) -> None:
        self.in_count = 0
        self.out_count = 0
        self.current_people = 0
        self.last_crossing = ""
        self.last_crossing_frame = -999
        self.last_centers.clear()
        self.crossed_track_directions.clear()
        self.track_trails.clear()
        self.last_seen.clear()

    def get_counts(self) -> dict[str, Any]:
        return {
            "in": self.in_count,
            "out": self.out_count,
            "current": self.current_people,
            "last_crossing": self.last_crossing,
            "frame_index": self.frame_index,
        }

    def process_frame(self, frame: Any) -> tuple[Any, dict[str, Any]]:
        annotated = frame.copy()
        height, width = frame.shape[:2]

        if self.count_line is None:
            self.set_line(width // 2, 0, width // 2, height, self.entering_direction)

        count_line = self.count_line
        entering_direction = self.entering_direction or default_entering_direction(count_line)

        track_fn = getattr(self.model, "track", self.model)
        result = track_fn(
            frame,
            persist=True,
            classes=[0],
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )[0]

        boxes = getattr(result, "boxes", None)
        if boxes is not None and getattr(boxes, "id", None) is not None:
            track_ids = boxes.id.int().cpu().tolist() if hasattr(boxes.id, "int") else [int(x) for x in boxes.id]
            xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy
            for track_id, box in zip(track_ids, xyxy):
                track_id = int(track_id)
                x_min, y_min, x_max, y_max = box
                center = ((float(x_min) + float(x_max)) / 2, (float(y_min) + float(y_max)) / 2)
                previous = self.last_centers.get(track_id)
                if previous is not None:
                    direction = crossing_direction(previous, center, count_line)
                    if direction:
                        self.last_crossing = direction
                        self.last_crossing_frame = self.frame_index
                        if direction == entering_direction:
                            self.in_count += 1
                        else:
                            self.out_count += 1
                        self.current_people = current_people_after_crossing(
                            self.current_people, direction, entering_direction
                        )
                        self.crossed_track_directions[track_id] = direction
                self.last_centers[track_id] = center
                self.last_seen[track_id] = self.frame_index
                trail = self.track_trails.setdefault(track_id, deque(maxlen=30))
                trail.append((int(center[0]), int(center[1])))

                direction = self.crossed_track_directions.get(track_id)
                color = (0, 220, 0) if direction == entering_direction else ((0, 0, 255) if direction else (255, 180, 0))

                if len(trail) > 1:
                    cv2.polylines(annotated, [np.array(trail, dtype=np.int32)], False, color, 2)
                x_min, y_min, x_max, y_max = map(int, box)
                cv2.rectangle(annotated, (x_min, y_min), (x_max, y_max), color, 2)
                cv2.putText(
                    annotated,
                    f"person #{track_id}",
                    (x_min, max(20, y_min - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

        x1, y1, x2, y2 = count_line
        cv2.line(annotated, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(
            annotated,
            f"IN: {self.in_count}  OUT: {self.out_count}  CURRENT: {self.current_people}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        if self.frame_index - self.last_crossing_frame < int(self.fps * 2):
            cv2.putText(
                annotated,
                f"last: {self.last_crossing}",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )
        self.frame_index += 1
        stale = [tid for tid, seen in self.last_seen.items()
                 if self.frame_index - seen > int(self.fps * 5)]
        for tid in stale:
            self.last_seen.pop(tid, None)
            self.last_centers.pop(tid, None)
            self.crossed_track_directions.pop(tid, None)
            self.track_trails.pop(tid, None)
        return annotated, self.get_counts()



def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but no usable NVIDIA GPU is available in this Python environment")

    try:
        source = source_with_credentials(args.source, args.username, args.password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    load_started = time.perf_counter()
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        raise SystemExit(f"could not open source: {args.source}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 20.0
    print(f"loaded source in {time.perf_counter() - load_started:.2f}s  fps: {fps:.2f}  resolution: {width}x{height}")
    writer = cv2.VideoWriter(
        args.output,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise SystemExit(f"could not open output: {args.output}")

    try:
        x1, y1, x2, y2 = line_from_args(args.line, args.line_file, width, height)
    except (OSError, ValueError, argparse.ArgumentTypeError) as exc:
        raise SystemExit(str(exc)) from exc
    count_line = (x1, y1, x2, y2)
    entering_direction = args.entering_direction or default_entering_direction(count_line)
    print(f"line: {x1},{y1},{x2},{y2}")
    print(f"line orientation: {line_orientation(count_line)}")
    print(f"entering direction: {entering_direction}")

    counter = PeopleCounter(
        model=args.model,
        confidence=args.confidence,
        device=args.device,
        count_line=count_line,
        entering_direction=entering_direction,
        fps=fps,
    )

    try:
        processed = 0
        process_started = time.perf_counter()
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            annotated, counts = counter.process_frame(frame)
            processed += 1
            writer.write(annotated)
            if not args.no_preview:
                scale = min(args.display_width / width, args.display_height / height, 1.0)
                preview = (
                    annotated
                    if scale == 1.0
                    else cv2.resize(annotated, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
                )
                cv2.imshow("People Counter", preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        capture.release()
        writer.release()
        cv2.destroyAllWindows()

    counts = counter.get_counts()
    elapsed = time.perf_counter() - process_started
    measured_fps = processed / elapsed if elapsed > 0 else 0.0
    print(f"IN: {counts['in']}  OUT: {counts['out']}  CURRENT: {counts['current']}")
    print(f"processed {processed} frames in {elapsed:.2f}s  ({measured_fps:.1f} fps, {elapsed / processed * 1000:.1f} ms/frame)")
    print(f"saved: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

