# TTube
TTube is a tiny terminal UI (TUI) for searching YouTube and streaming the audio of a selected result.

## Features
- Search YouTube from the terminal
- Stream audio playback (no file download)
- Pause/resume, stop
- Seeking controls (multiple step sizes)
- Progress bar with buffered-ahead indicator
- Simple stereo VU meter (visualizer)

## Requirements
- Python 3.10+
- A working audio output device
- ffmpeg on your PATH (recommended)
  - If ffmpeg isn't on PATH, TTube will try a Python fallback via `imageio-ffmpeg`.

## Install

### Quick install (recommended)
```bash
python install.py
```
This creates a `.venv` in the project folder and installs TTube (plus dependencies) into it.

### Manual install
Create a virtual environment (recommended) and install dependencies.

#### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

#### macOS / Linux (bash/zsh)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Run
If you used the installer / editable install:
- `python -m ttube`

Or run directly from the repo:
```bash
python ttube.py
```

## Controls
You can always see the shortcuts in-app, but the defaults are:
- Enter: search (when focused on the search bar) / play selected (when focused on results)
- ↑/↓: move selection
- Esc: focus search
- Tab: switch focus (search/results)
- P: pause/resume
- Space: pause/resume (when focused on results)
- S: stop
- Q: quit

Seeking (when duration is known):
- ←/→: ±5s
- [ / ]: ±10s
- PgUp/PgDn: ±30s
- Home/End: jump to start/end

## Troubleshooting
- If you see “ffmpeg not found”, install ffmpeg and ensure it’s on PATH.
  - Windows: `winget install Gyan.FFmpeg` (or use Chocolatey/Scoop)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
- If the UI looks cut off, try enlarging the terminal window.
- If audio doesn’t play, verify your OS audio output device works and that PortAudio is available (required by `sounddevice`).

## Project layout
- `ttube.py`: curses UI + app state
- `ttube_youtube.py`: search + resolve best audio stream using `yt-dlp`
- `ttube_stream.py`: ffmpeg -> PCM -> `sounddevice` playback, buffering, seeking, and the VU meter levels

## Notes
This project uses `yt-dlp` to resolve streaming URLs. Make sure your usage complies with applicable terms and laws.

## License
MIT (see `LICENSE`).
