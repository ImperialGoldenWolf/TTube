# 🎧 TTube

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform: Windows | macOS | Linux](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

> A minimalist, lightning-fast Terminal UI (TUI) for searching and streaming YouTube audio directly from your command line. No downloads, no clutter—just music.

##  Features

* **Seamless Search:** Find and select tracks without ever leaving the terminal.
* **Zero-Download Streaming:** Audio is streamed directly to your output device.
* **Advanced Playback:** Pause, resume, stop, and granular seeking capabilities.
* **Visual Feedback:** Features a real-time progress bar with buffer indicators and a built-in **stereo VU meter**.

---

##  Prerequisites

Before installing TTube, ensure your system has the following:
* **Python 3.10** or higher.
* A working audio output device.
* **FFmpeg** installed and added to your system `PATH` (Highly Recommended).
    * *Note: If FFmpeg is missing, TTube will attempt a Python fallback via `imageio-ffmpeg`.*

---

##  Getting Started

### 1. Quick Install (Recommended)
The easiest way to get TTube running is using the provided install script. This automatically creates a virtual environment (`.venv`) and installs all dependencies.

```bash
# Clone the repository, navigate to the folder, then run:
python install.py

```

### 2. Manual Install

If you prefer to set things up manually, creating a virtual environment is still highly recommended.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .

```

**macOS / Linux (Bash/Zsh)**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

```

### 3. Run TTube

If you used the installer or performed an editable install, launch the app via:

```bash
python -m ttube

```

Alternatively, you can run the script directly from the repository root:

```bash
python ttube.py

```

---

##  Controls

TTube is designed for rapid, keyboard-driven navigation. The app uses **mode-aware keybindings** to ensure optimal usability.

### Core Navigation

| Action | Keybinding | Context |
| --- | --- | --- |
| **Search** | `Enter` | When focused on the Search Bar |
| **Play Track** | `Enter` | When focused on Results |
| **Navigate Results** | `↑` / `↓` | Move selection up/down in results |
| **Page Results** | `PgUp` / `PgDn` | Scroll results by page |
| **First/Last Result** | `Home` / `End` | Jump to first or last result |
| **Focus Search** | `Esc` | Returns focus to the search input |
| **Switch Focus** | `Tab` | Toggles between Search and Results |
| **Quit** | `Q` | Exits TTube |

### Playback Controls

| Action | Keybinding | Context |
| --- | --- | --- |
| **Pause / Resume** | `P` or `Space` | During playback in Results mode |
| **Stop** | `S` | Stops current playback (Results mode only) |

**Note:** `P` can be typed normally in Search mode for queries like "Paul Simon".

### Seeking Controls

*(Available when track duration is known)*

| Jump Size | Keys |
| --- | --- |
| **± 5 seconds** | `←` / `→` |
| **± 10 seconds** | `[` / `]` |
| **± 30 seconds** | `PgUp` / `PgDn` |
| **Start / End** | `Home` / `End` |

---

##  Under the Hood

TTube is broken down into three core, lightweight modules:

* `ttube.py`: The `curses`-based frontend UI and application state manager.
* `ttube_youtube.py`: The search and extraction engine, powered by `yt-dlp`.
* `ttube_stream.py`: The audio pipeline routing FFmpeg to PCM, handled via `sounddevice` with buffering and VU level calculations.

---

##  Troubleshooting

* **"ffmpeg not found" error:** Install FFmpeg and ensure it is on your system `PATH`.
* **Windows:** `winget install Gyan.FFmpeg` (or use Chocolatey/Scoop)
* **macOS:** `brew install ffmpeg`
* **Linux (Debian/Ubuntu):** `sudo apt-get install ffmpeg`


* **UI is cut off:** Your terminal window is too small. Try enlarging it and restarting the app.
* **No audio playing:** Verify that your OS audio output device is working correctly and that PortAudio is available (a backend requirement for `sounddevice`).

---

## ⚖️ License & Disclaimer

This project is licensed under the **MIT License**. See the `LICENSE` file for details.

*Disclaimer: TTube utilizes `yt-dlp` to resolve streaming URLs. Please ensure your usage complies with applicable YouTube Terms of Service and local copyright laws.*

