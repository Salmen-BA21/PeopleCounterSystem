"""Count people crossing a line in a video file or RTSP stream."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit


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
    if abs(x2 - x1) >= abs(y2 - y1):
        line_y = y1 if x2 == x1 else y1 + (x - x1) * (y2 - y1) / (x2 - x1)
        return "north" if y < line_y else "south"
    line_x = x1 if y2 == y1 else x1 + (y - y1) * (x2 - x1) / (y2 - y1)
    return "west" if x < line_x else "east"


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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    import cv2
    import numpy as np
    import supervision as sv
    import torch
    from ultralytics import YOLO

    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but no usable NVIDIA GPU is available in this Python environment")

    try:
        source = source_with_credentials(args.source, args.username, args.password)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        raise SystemExit(f"could not open source: {args.source}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = capture.get(cv2.CAP_PROP_FPS) or 20.0
    writer = cv2.VideoWriter(
        args.output,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise SystemExit(f"could not open output: {args.output}")

    model = YOLO(args.model)
    tracker = sv.ByteTrack()
    try:
        x1, y1, x2, y2 = line_from_args(args.line, args.line_file, width, height)
    except (OSError, ValueError, argparse.ArgumentTypeError) as exc:
        raise SystemExit(str(exc)) from exc
    count_line = (x1, y1, x2, y2)
    entering_direction = args.entering_direction or default_entering_direction(count_line)
    print(f"line: {x1},{y1},{x2},{y2}")
    print(f"line orientation: {line_orientation(count_line)}")
    print(f"entering direction: {entering_direction}")
    in_count = 0
    out_count = 0
    current_people = 0
    frame_index = 0
    last_crossing = ""
    last_crossing_frame = -999
    last_centers: dict[int, tuple[float, float]] = {}
    counted_track_ids: set[int] = set()
    crossed_track_directions: dict[int, str] = {}
    track_trails: dict[int, list[tuple[int, int]]] = {}

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            result = model(
                frame,
                classes=[0],
                conf=args.confidence,
                device=args.device,
                verbose=False,
            )[0]
            detections = tracker.update_with_detections(sv.Detections.from_ultralytics(result))
            if detections.tracker_id is not None:
                for track_id, box in zip(detections.tracker_id, detections.xyxy):
                    track_id = int(track_id)
                    x_min, y_min, x_max, y_max = box
                    center = ((float(x_min) + float(x_max)) / 2, (float(y_min) + float(y_max)) / 2)
                    previous = last_centers.get(track_id)
                    if previous is not None and track_id not in counted_track_ids:
                        direction = crossing_direction(previous, center, count_line)
                        if direction:
                            last_crossing = direction
                            last_crossing_frame = frame_index
                            counted_track_ids.add(track_id)
                            if direction == entering_direction:
                                in_count += 1
                            else:
                                out_count += 1
                            current_people = current_people_after_crossing(current_people, direction, entering_direction)
                            crossed_track_directions[track_id] = direction
                    last_centers[track_id] = center
                    center_point = (int(center[0]), int(center[1]))
                    trail = track_trails.setdefault(track_id, [])
                    trail.append(center_point)
                    del trail[:-30]

                    direction = crossed_track_directions.get(track_id)
                    if direction == entering_direction:
                        color = (0, 220, 0)
                    elif direction:
                        color = (0, 0, 255)
                    else:
                        color = (255, 180, 0)

                    points = track_trails[track_id]
                    if len(points) > 1:
                        cv2.polylines(frame, [np.array(points, dtype=np.int32)], False, color, 2)
                    x_min, y_min, x_max, y_max = (int(value) for value in box)
                    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 2)
                    cv2.putText(
                        frame,
                        f"person #{track_id}",
                        (x_min, max(20, y_min - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                    )
            cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(
                frame,
                f"IN: {in_count}  OUT: {out_count}  CURRENT: {current_people}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )
            if frame_index - last_crossing_frame < int(fps * 2):
                cv2.putText(
                    frame,
                    f"last: {last_crossing}",
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2,
                )
            writer.write(frame)
            if not args.no_preview:
                scale = min(args.display_width / width, args.display_height / height, 1.0)
                preview = frame if scale == 1.0 else cv2.resize(
                    frame, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA
                )
                cv2.imshow("People Counter", preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            frame_index += 1
    finally:
        capture.release()
        writer.release()
        cv2.destroyAllWindows()

    print(f"IN: {in_count}  OUT: {out_count}  CURRENT: {current_people}")
    print(f"saved: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
