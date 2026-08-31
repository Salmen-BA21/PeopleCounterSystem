"""Benchmark the detection pipeline and estimate performance on other hardware."""

import time
import sys
from pathlib import Path

import cv2
import numpy as np

# --- Run the real benchmark ---

def benchmark(source: str, model_name: str = "yolo26n.pt", device: str = "cuda", seconds: float = 5.0):
    import torch
    from ultralytics import YOLO

    print(f"=== People Counter Benchmark ===")
    print(f"Source:     {source}")
    print(f"Model:      {model_name}")
    print(f"Device:     {device}")
    print(f"PyTorch:    {torch.__version__}")
    print(f"CUDA avail: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA ver:    {torch.version.cuda}")
    print()

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"ERROR: Cannot open {source}")
        sys.exit(1)

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"Source: {src_w}x{src_h} @ {src_fps:.1f} fps")

    model = YOLO(model_name)
    model.to(device)

    # Warmup
    ok, frame = cap.read()
    if ok:
        model.track(frame, persist=True, classes=[0], conf=0.35, device=device, verbose=False)

    # Benchmark
    frame_times = []
    inference_times = []
    encode_times = []
    frames_processed = 0
    start = time.perf_counter()

    while time.perf_counter() - start < seconds:
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        t0 = time.perf_counter()
        result = model.track(frame, persist=True, classes=[0], conf=0.35, device=device, verbose=False)[0]
        t1 = time.perf_counter()
        _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        t2 = time.perf_counter()

        inference_times.append(t1 - t0)
        encode_times.append(t2 - t1)
        frame_times.append(t2 - t0)
        frames_processed += 1

    elapsed = time.perf_counter() - start
    cap.release()

    avg_frame = np.mean(frame_times) * 1000
    avg_inf = np.mean(inference_times) * 1000
    avg_enc = np.mean(encode_times) * 1000
    p95_frame = np.percentile(frame_times, 95) * 1000
    measured_fps = frames_processed / elapsed

    print(f"\n--- Results ({frames_processed} frames in {elapsed:.1f}s) ---")
    print(f"Measured FPS:    {measured_fps:.1f}")
    print(f"Avg frame time:  {avg_frame:.1f} ms")
    print(f"  inference:     {avg_inf:.1f} ms")
    print(f"  JPEG encode:   {avg_enc:.1f} ms")
    print(f"P95 frame time:  {p95_frame:.1f} ms")
    print(f"Skip needed:    {'YES' if avg_frame > (1000/src_fps) else 'NO'} (budget: {1000/src_fps:.1f} ms)")

    # Estimate for other hardware
    print(f"\n--- Estimated performance on other hardware ---")
    print(f"(Based on {model_name} @ {src_w}x{src_h})")
    print()

    profiles = [
        ("Old PC (i5-4590, GTX 750 Ti, 8GB)", 3.5, "CPU-bound + weak GPU"),
        ("Old PC (i5-6500, GTX 1050, 8GB)", 2.0, "GPU-bound"),
        ("Mid PC (i5-8400, GTX 1060 6GB, 16GB)", 1.2, "Balanced"),
        ("Your PC (baseline)", 1.0, "This machine"),
        ("Old laptop (i5-7200U, MX150, 8GB)", 2.5, "Thermal throttled"),
        ("No GPU (i5-4590, CPU only)", 8.0, "CPU inference"),
        ("No GPU (i7-8700, CPU only)", 5.0, "CPU inference"),
    ]

    print(f"{'Hardware':<45} {'Est. ms/frame':>14} {'Est. FPS':>10} {'Status':<20}")
    print("-" * 95)
    for name, factor, note in profiles:
        est_ms = avg_frame * factor
        est_fps = min(1000 / est_ms, src_fps)
        status = "OK" if est_fps >= 20 else ("Tight" if est_fps >= 15 else "TOO SLOW")
        print(f"{name:<45} {est_ms:>10.0f} ms {est_fps:>9.1f}  {status:<20}")

    # Recommendations
    print(f"\n--- Recommendations for old PCs ---")
    if avg_inf > 30:
        print(f"- Switch to yolo26n.pt (nano) if not already using it")
    print(f"- 720p is fine — don't upscale to 1080p on old hardware")
    print(f"- Frame skip is enabled — video will play at measurable FPS even if slow")
    if device == "cuda":
        print(f"- If no GPU: CPU inference works but expect 5-8x slower")
        print(f"- The app auto-detects CUDA and falls back to CPU with a warning")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="video file or RTSP URL")
    p.add_argument("--model", default="yolo26n.pt")
    p.add_argument("--device", default="cuda")
    p.add_argument("--seconds", type=float, default=5.0)
    args = p.parse_args()
    benchmark(args.source, args.model, args.device, args.seconds)
