# TTube - Terminal YouTube Audio Streamer

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform: Windows | macOS | Linux](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

> A minimalist, lightning-fast Terminal UI (TUI) for searching and streaming YouTube audio directly from your command line. 
> No downloads, no clutter—just music.

---

## Features

- **[*] Seamless Search:** Find and select tracks without ever leaving the terminal
- **[*] Zero-Download Streaming:** Audio is streamed directly to your output device
- **[*] Advanced Playback:** Pause, resume, stop, and granular seeking capabilities
- **[*] Visual Feedback:** Real-time progress bar with buffer indicators and stereo VU meter
- **[*] Clean Theme:** Professional TUI with color-coded interface
- **[*] Lightweight:** Minimal resource usage, runs on any system

---

## Requirements

Before installing TTube, ensure your system has the following:

- **Python 3.10** or higher
- A working audio output device
- **FFmpeg** (recommended, will be installed by installer)
  - *Note: If FFmpeg is not available, TTube will attempt a Python fallback via imageio-ffmpeg*

---

## Installation

### Option 1: Automatic Installation (Recommended)

The easiest way to get TTube running is using the enhanced installer. This automatically creates a virtual environment and installs all dependencies including FFmpeg.

**Windows (PowerShell):**
```powershell
python install_app.py
```

**Linux/macOS (Terminal):**
```bash
python3 install_app.py
```

The installer will:
- Create a virtual environment (`.venv`)
- Install all Python dependencies
- Download and configure FFmpeg (Windows)
- Create desktop and Start Menu shortcuts (Windows)

### Option 2: Manual Installation

If you prefer manual setup:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

**Linux/macOS (Terminal):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Quick Start

### After Installation

**Windows:**
- Use the `ttube_launcher.bat` from the installation folder, or
- Run: `python -m ttube`

**Linux/macOS:**
- Run: `./ttube.sh`, or
- Run: `python -m ttube`

### Basic Usage

```
>> TTube v0.1
=====================================================
Enter: search/play  ↑↓: navigate  Esc: search  Tab: switch  P/Space: pause  S: stop  Q: quit
Seek: ←→ ±5s  [ ] ±10s  PgUp/Dn ±30s  Home/End

[?] Search*: [type query here]

[*] Results (0)

[*] Status: Type a search query (spaces supported) and press Enter.
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `Enter` | Search or play selected result |
| `↑` / `↓` | Navigate results |
| `Tab` | Switch between search and results |
| `Esc` | Return to search |
| `P` / `Space` | Pause/Resume playback |
| `S` | Stop playback |
| `←` / `→` | Seek ±5 seconds |
| `[` / `]` | Seek ±10 seconds |
| `PgUp` / `PgDn` | Seek ±30 seconds or page results |
| `Home` / `End` | Jump to start/end |
| `Q` | Quit application |

---

## Interface Elements

```
>> TTube v0.1                           [RESULTS] | Searching
Enter: search/play  ↑↓: navigate  Esc: search  Tab: switch  P/Space: pause  S: stop  Q: quit
Seek: ←→ ±5s  [ ] ±10s  PgUp/Dn ±30s  Home/End

[?] Search: awesome music

[*] Results (10)
>> Best Song Ever - Artist One        [2/10]
   Another Great Song - Artist Two
   Great Hits Collection - Various

>> Now: Best Song Ever - Artist One
[========~~~~~-----] 01:23 / 03:45  buf:0.8s
[VU] L[########] R[########]

[*] Status: Playing.
```

---

## Configuration

TTube stores its virtual environment in `.venv/` within the application directory. No additional configuration is needed.

### Audio Device Selection

If you have multiple audio devices and need to select a specific one:

1. Edit the `ttube_stream.py` file and modify the `device` parameter in the `StreamPlayer` class

### FFmpeg

TTube will use system FFmpeg if available. For best performance and format support, ensure FFmpeg is installed and in your PATH.

---

## Troubleshooting

### Application won't start

```
[>] Make sure you have Python 3.10 or higher installed
[>] Run: python install_app.py
[>] Check that all dependencies are installed: pip install -r requirements.txt
```

### No sound output

```
[>] Check your system audio is working: play any audio file
[>] Verify sound device is available and not muted
[>] Try a different search result
[>] Ensure FFmpeg or imageio-ffmpeg is installed
```

### Search not working

```
[>] Check your internet connection
[>] Try searching for a simpler query term
[>] Verify yt-dlp is installed: pip list | grep yt-dlp
```

### FFmpeg not found

```
[>] Install FFmpeg: https://ffmpeg.org/download.html
[>] Add FFmpeg/bin to your system PATH
[>] Or reinstall TTube: python install_app.py
```

---

## Performance Tips

- **First search:** May take a few seconds to fetch results from YouTube
- **Smooth playback:** Ensure stable internet connection (5+ Mbps recommended)
- **VU meter:** Visual indicator of audio levels; may use slightly more CPU

---

## Project Structure

```
TTube/
├── ttube.py                # Main TUI application
├── ttube_stream.py         # Audio playback engine
├── ttube_youtube.py        # YouTube search & streaming
├── install_app.py          # Installer with FFmpeg support
├── install.py              # Minimal install script
├── run.py                  # Launch script
├── ttube_launcher.bat      # Windows launcher (auto-generated)
├── ttube.sh                # Linux/macOS launcher
├── ttube.spec              # PyInstaller build spec
├── ttube.ico               # Application icon
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Package configuration
├── setup.cfg               # Package metadata
├── Makefile                # Dev commands
├── README.md               # This file
├── CHANGELOG.md            # Version history
├── GETTING_STARTED.md      # Quickstart guide
├── QUICK_REFERENCE.md      # Keyboard shortcuts reference
├── LYRICS_GUIDE.md         # Lyrics feature guide
├── CONFIG.md               # Configuration guide
├── LICENSE                 # MIT License
└── .venv/                  # Virtual environment (created by installer)
```

---

## Development

### Setup development environment

```bash
python install_app.py
source .venv/bin/activate  # Linux/macOS
# or
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -e ".[dev]"
```

### Building standalone executable

```bash
pyinstaller ttube.spec
```

---

## License

TTube is released under the MIT License. See [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

---

## Credits

Built with:
- **yt-dlp** - YouTube content download
- **sounddevice** - Audio playback
- **curses** - Terminal UI framework
- **imageio-ffmpeg** - FFmpeg Python bindings

---

## Disclaimer

TTube is for educational and personal use only. Respect YouTube's Terms of Service and copyright laws. The creators are not responsible for misuse of this tool.

---

**Version 0.1.0** | Last Updated: 2026-05-08
