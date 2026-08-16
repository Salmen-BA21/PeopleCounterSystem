"""Click two points on a video frame to define a counting line (x1,y1,x2,y2)."""

from __future__ import annotations

import argparse

import cv2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="video file path")
    parser.add_argument("--frame", type=int, default=0, help="frame index to pause on")
    parser.add_argument("--output", default="line.txt", help="file to write the line to")
    args = parser.parse_args(argv)

    capture = cv2.VideoCapture(args.source)
    if not capture.isOpened():
        raise SystemExit(f"could not open source: {args.source}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, args.frame)
    ok, frame = capture.read()
    if not ok:
        raise SystemExit(f"could not read frame {args.frame}")
    capture.release()

    points: list[tuple[int, int]] = []
    overlay = frame.copy()

    def on_click(event: int, x: int, y: int, flags: int, param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        points.append((x, y))
        cv2.circle(overlay, (x, y), 4, (0, 255, 255), -1)
        if len(points) == 2:
            cv2.line(overlay, points[0], points[1], (0, 255, 255), 2)

    cv2.namedWindow("Pick two points; press q when done")
    cv2.setMouseCallback("Pick two points; press q when done", on_click)
    while True:
        cv2.imshow("Pick two points; press q when done", overlay)
        key = cv2.waitKey(20) & 0xFF
        if key == ord("q") and len(points) == 2:
            break
        if key == ord("r"):
            points.clear()
            overlay = frame.copy()
    cv2.destroyAllWindows()

    if len(points) != 2:
        raise SystemExit("need exactly two clicks")

    x1, y1 = points[0]
    x2, y2 = points[1]
    line = f"{x1},{y1},{x2},{y2}"
    with open(args.output, "w") as fh:
        fh.write(line)
    print(f"line: {line}")
    print(f"saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
