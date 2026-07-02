# TTube Configuration Guide

## File Structure

```
TTube/
├── install_app.py           # Main installer (run first!)
├── ttube.py                 # Main application
├── ttube_stream.py          # Audio streaming backend
├── ttube_youtube.py         # YouTube search integration
├── ttube_launcher.bat       # Windows launcher (auto-generated)
├── ttube.sh                 # Linux/macOS launcher
├── requirements.txt         # Python dependencies
├── pyproject.toml          # Package metadata
├── ttube.spec              # PyInstaller configuration
├── .venv/                  # Virtual environment (created)
├── ffmpeg/                 # FFmpeg installation (Windows, optional)
├── README.md               # User documentation
├── CHANGELOG.md            # Version history
├── CONFIG.md               # This file
└── LICENSE                 # MIT License
```

## Installation & Setup

### Step 1: Initial Installation (Recommended)

**Windows:**
```powershell
# Run from TTube folder
python install_app.py
```

**macOS/Linux:**
```bash
# Run from TTube folder
python3 install_app.py
```

This will:
1. Verify Python 3.10+
2. Create virtual environment (`.venv`)
3. Install all dependencies
4. Download FFmpeg (Windows only)
5. Create desktop shortcuts

### Step 2: Running the Application

**Windows:**
- Double-click `ttube_launcher.bat`
- Or: `python -m ttube`

**macOS/Linux:**
- Run: `./ttube.sh`
- Or: `python -m ttube`

## Customization

### Audio Device Configuration

To use a specific audio device instead of the default:

1. Open `ttube_stream.py`
2. Find the `StreamPlayer` class `__init__` method
3. Modify the `device` parameter:

```python
def __init__(self, device: int = None):  # None = default device
    # Change to: device=2  (for example)
    self.stream = sd.Stream(
        channels=2,
        samplerate=44100,
        blocksize=4096,
        device=device,  # Specify device ID here
        # ... other settings
    )
```

List available devices:
```python
import sounddevice as sd
print(sd.query_devices())
```

### Terminal Theme

Edit the color pairs in `ttube.py` `_init_colors()` function:

```python
curses.init_pair(1, curses.COLOR_CYAN, -1)     # Header
curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Selection
curses.init_pair(3, curses.COLOR_GREEN, -1)    # Playing
curses.init_pair(4, curses.COLOR_RED, -1)      # Error
curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLUE) # Results
curses.init_pair(6, curses.COLOR_MAGENTA, -1)  # Labels
curses.init_pair(7, curses.COLOR_GREEN, curses.COLOR_BLACK) # Status OK
curses.init_pair(8, curses.COLOR_GREEN, -1)    # Progress bar
```

Available colors:
- `curses.COLOR_BLACK`
- `curses.COLOR_RED`
- `curses.COLOR_GREEN`
- `curses.COLOR_YELLOW`
- `curses.COLOR_BLUE`
- `curses.COLOR_MAGENTA`
- `curses.COLOR_CYAN`
- `curses.COLOR_WHITE`

### UI Elements Customization

Modify these in `ttube.py`:

```python
# Header
_safe_addstr(stdscr, 0, 0, ">> TTube v0.1", header_attr)

# Search label
query_label = "[?] Search"

# Results header
results_header = f"[*] Results ({len(app.results)})"

# Now playing
f">> Now: {app.now_playing}"

# VU meter
vu_line = f"[VU] L[{meter_l}] R[{meter_r}]"

# Status
status_line = f"[*] Status: {app.status}"
```

## Environment Variables

### Optional Tweaks

```bash
# Windows
set TERM=xterm-256color
set PYTHONUNBUFFERED=1

# macOS/Linux
export TERM=xterm-256color
export PYTHONUNBUFFERED=1
```

## Virtual Environment Management

### Activate Virtual Environment

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### Deactivate

```bash
deactivate
```

### Reinstall Dependencies

```bash
pip install --upgrade -r requirements.txt
```

## FFmpeg Configuration

### Check FFmpeg Status

```bash
ffmpeg -version
```

### Using System FFmpeg

TTube automatically uses FFmpeg from system PATH if available.

### Using Local FFmpeg (Windows)

If installed via `install_app.py`:
- Location: `TTube/ffmpeg/bin/`
- Automatically added to PATH by launcher

### Manual FFmpeg Installation

1. Download from: https://ffmpeg.org/download.html
2. Extract to: `TTube/ffmpeg/`
3. Ensure structure: `TTube/ffmpeg/bin/ffmpeg.exe`

## Troubleshooting

### "Python version too old"
```bash
# Check version
python --version
# Upgrade Python from python.org or your package manager
```

### "Virtual environment not found"
```bash
# Recreate it
python install_app.py
```

### "FFmpeg not found" (Windows)
```bash
# Reinstall with FFmpeg
python install_app.py
# Or install manually
```

### "No audio device found"
```python
# List devices
import sounddevice as sd
print(sd.query_devices())
# Edit ttube_stream.py to use device ID
```

### Terminal rendering issues
```bash
# Set terminal type
set TERM=xterm-256color  # Windows
export TERM=xterm-256color  # macOS/Linux
```

## Development & Building

### Install Development Tools

```bash
pip install -e ".[dev]"
```

### Code Quality

```bash
# Format code
black ttube.py ttube_stream.py ttube_youtube.py

# Lint
flake8 ttube.py ttube_stream.py ttube_youtube.py

# Test
pytest
```

### Build Standalone EXE (Windows)

```bash
pyinstaller ttube.spec
```

Output: `dist/ttube/`

## Advanced Options

### Debug Mode

Enable debug output:
```python
# In ttube.py, add at start of main():
import logging
logging.basicConfig(level=logging.DEBUG, filename='ttube_debug.log')
```

### Custom Search Limit

Modify in `ttube.py` `start_search()`:
```python
self._pending_search = self._executor.submit(search_youtube, q, 20)  # 20 results
```

### Buffer Size Adjustment

In `ttube_stream.py` `StreamPlayer.__init__()`:
```python
self.stream = sd.Stream(
    blocksize=8192,  # Increase for slower connections
    # ...
)
```

## Performance Optimization

### For Slow Machines

1. Reduce buffer size in `ttube_stream.py`
2. Lower spinner speed in `ttube.py` (modify `time.time() * 8`)
3. Increase draw interval (modify `time.sleep(0.03)`)

### For Fast Machines

Increase search results limit in `ttube.py`

## Uninstallation

**Windows:**
```powershell
# Remove folder and environment
Remove-Item -Recurse -Force TTube
```

**macOS/Linux:**
```bash
rm -rf TTube
```

---

**Configuration Guide v0.1** | 2026-05-08
