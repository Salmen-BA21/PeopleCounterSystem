# People Count System

Detect and count people crossing a line in a video file or RTSP camera stream.

The app uses:

- Ultralytics YOLO for person detection
- Supervision ByteTrack for tracking people between frames
- OpenCV for video input, preview, drawing, and output video writing
- PyTorch CUDA when `--device cuda` is used

## Project Layout

```text
src/count_people.py       Count people crossing a line
src/pick_line.py          Click two points on a frame and save line.txt
src/discover_cameras.py   Discover ONVIF cameras or get an RTSP URI
tests/                    Small unit tests
line.txt                  Saved counting line: x1,y1,x2,y2
test1.mp4                 Local test video
```

## Setup

From the project folder:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If you want CUDA acceleration, make sure PyTorch in `.venv` sees your GPU:

```powershell
.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Expected result on this machine:

```text
True
NVIDIA GeForce RTX 4060 Laptop GPU
```

## Pick A Counting Line

Click two points on a video frame:

```powershell
.venv\Scripts\python.exe -m src.pick_line test1.mp4 --output line.txt
```

Controls:

- Left click: choose line points
- `r`: reset clicks
- `q`: save after two clicks

The saved file looks like:

```text
178,222,399,224
```

## Count People In A Video

Run with CUDA:

```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --output counted_test1.mp4 --device cuda
```

Run with CPU:

```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --output counted_test1.mp4 --device cpu
```

Run without the preview window:

```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --output counted_test1.mp4 --device cuda --no-preview
```

Press `q` in the preview window to stop early.

## Entering And Leaving Direction

The app determines which side of the line a person was on before and after crossing.

For a mostly horizontal line:

- `north_to_south`
- `south_to_north`

For a mostly vertical line:

- `west_to_east`
- `east_to_west`

Default `IN` direction:

- horizontal line: `north_to_south`
- vertical line: `west_to_east`

Override it if your camera is reversed:

```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --output counted_test1.mp4 --device cuda --entering-direction south_to_north
```

At startup, the app prints:

```text
line: 178,222,399,224
line orientation: horizontal
entering direction: north_to_south
```

The video overlay shows `IN`, `OUT`, and the most recent crossing direction.

## RTSP Camera Usage

If you already know the RTSP URL:

```powershell
.venv\Scripts\python.exe -m src.count_people --source "rtsp://192.168.1.23:554/profile1" --username admin --password "p@ss" --line-file line.txt --device cuda
```

Discover ONVIF cameras:

```powershell
.venv\Scripts\python.exe -m src.discover_cameras --timeout 5
```

Get an RTSP URI from an ONVIF camera:

```powershell
.venv\Scripts\python.exe -m src.discover_cameras --rtsp --host 192.168.1.23 --port 80 --username admin --password "p@ss"
```

## Tests

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

## Common Problems

If plain `python` cannot import `torch`, use the virtual environment explicitly:

```powershell
.venv\Scripts\python.exe -m src.count_people --source test1.mp4 --line-file line.txt --device cuda
```

If CUDA fails, check:

```powershell
nvidia-smi
.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

If `IN` and `OUT` are reversed, change `--entering-direction`.
