# People Count System

Real-time people detection, tracking, and bidirectional line-crossing counting with both a **Web Dashboard UI** and a **CLI tool**. Supports local video files and RTSP IP camera streams.

---

## ⚡ Features

- **Ultralytics YOLO** for person detection.
- **Supervision ByteTrack** for robust multi-object tracking.
- **Directional Crossing Logic**: Automatically detects crossing vectors (`north_to_south`, `south_to_north`, `west_to_east`, `east_to_west`) and tracks `IN`, `OUT`, and net `CURRENT` occupancy.
- **Real-Time Web Dashboard**:
  - Low-latency binary MJPEG video streaming via WebSockets (`/ws/video`).
  - High-frequency telemetry feed via WebSockets (`/ws/counts`).
  - Interactive click-and-drag counting line adjustment directly on the browser canvas.
  - Video selector and drag-and-drop video uploader.
  - Counter reset and hot-switching video sources without restarting the server.
- **Hardware Acceleration**: Automatic PyTorch CUDA GPU acceleration with CPU fallback.
- **ONVIF / RTSP Integration**: Discover network cameras and extract RTSP stream endpoints.

---

## 📂 Project Layout

```text
├── src/
│   ├── count_people.py       # Core PeopleCounter pipeline & CLI tool
│   ├── server.py             # FastAPI backend with WebSockets & REST API
│   ├── pick_line.py          # OpenCV GUI helper to click points and save line.txt
│   └── discover_cameras.py   # ONVIF camera discovery & RTSP URI resolver
├── web/                      # Web frontend (HTML5 / Vanilla CSS / Vanilla JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/                    # Unit and integration test suites
│   ├── test_count_people.py
│   └── test_server.py
├── uploads/                  # Uploaded videos storage directory
├── line.txt                  # Saved counting line: x1,y1,x2,y2
├── test1.mp4                 # Sample test video
└── requirements.txt          # Python dependencies
```

---

## 🚀 Getting Started

### 1. Setup Environment

Activate the virtual environment and install dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Verify GPU acceleration (optional):

```powershell
.venv\Scripts\python.exe -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

### Building the Windows app on a new PC

- Install from `requirements.lock.txt` (not `requirements.txt`) — it pins exact versions including `torch 2.11.0+cu128`. Unpinned installs silently get CPU-only torch, which is the #1 cause of "works on my machine but slow elsewhere".
- The target PC needs an NVIDIA driver **≥ 525** for CUDA 12.x. RTX GPUs are fully supported.
- The native window needs **.NET Framework 4.7.2+** (built into Win10 1809+). On older PCs the app no longer crashes: it opens in the default browser instead — or install the [.NET Framework 4.8 runtime](https://dotnet.microsoft.com/download/dotnet-framework/net48) for the native window.
- After every build, run `build.bat`'s built-in self-check (or `PeopleCounter.exe --diag`): it writes `exe_diag.txt` next to the exe stating whether CUDA is active and why not if it isn't.
- Only `yolo26n.pt` / `yolo26s.pt` are bundled. To use larger models, drop the `.pt` file next to `PeopleCounter.exe` — it appears in the sidebar automatically.

---

## 🌐 Web Dashboard (Recommended)

Launch the FastAPI web server:

```powershell
.venv\Scripts\python.exe -m src.server --source test1.mp4 --device cuda
```

Open your browser at:
👉 **[http://localhost:8000](http://localhost:8000)**

### Web Server Options

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `--source` | `test1.mp4` | Video file path or RTSP URL (`rtsp://...`) |
| `--device` | `cuda` | Inference device (`cuda` or `cpu`) |
| `--confidence` | `0.35` | YOLO detection confidence threshold |
| `--model` | `yolo26n.pt` | YOLO weights path or model name |
| `--port` | `8000` | Web server port |
| `--line` | `None` | Initial line coordinates `x1,y1,x2,y2` |
| `--line-file` | `line.txt` | Path to line configuration file |
| `--jpeg-quality`| `75` | MJPEG video streaming compression quality |

---

## 💻 CLI Usage

### Count People in a Video

Run with GPU:
```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --output counted_test1.mp4 --device cuda
```

Run with CPU / Headless:
```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --output counted_test1.mp4 --device cpu --no-preview
```

### Pick a Counting Line via OpenCV Tool

```powershell
.venv\Scripts\python.exe -m src.pick_line test1.mp4 --output line.txt
```
* **Left click**: select point 1 and point 2.
* **`r`**: reset points.
* **`q`**: save and exit.

---

## 🧭 Entering & Leaving Direction

The system identifies which side of the line a tracked person crossed:

- **Horizontal lines**: `north_to_south` (default IN) / `south_to_north`
- **Vertical lines**: `west_to_east` (default IN) / `east_to_west`

Override the IN direction if your camera angle requires it:

```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --entering-direction south_to_north
```

---

## 📹 RTSP & ONVIF Cameras

### Run with an RTSP Camera Stream
```powershell
.venv\Scripts\python.exe -m src.count_people --source "rtsp://192.168.1.23:554/profile1" --username admin --password "p@ss" --line-file line.txt --device cuda
```

### Discover ONVIF Cameras on the Network
```powershell
.venv\Scripts\python.exe -m src.discover_cameras --timeout 5
```

### Resolve RTSP Stream URI from ONVIF Camera
```powershell
.venv\Scripts\python.exe -m src.discover_cameras --rtsp --host 192.168.1.23 --port 80 --username admin --password "p@ss"
```

---

## 🧪 Running Tests

Execute the test suite:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```
