# TTube - Terminal vs GUI Version

Both terminal and graphical versions of TTube are now available!

## 🎯 Quick Choice Guide

### Use **Terminal TUI** (`ttube.py`) if:
- ✅ You prefer keyboard-driven interfaces
- ✅ You're working over SSH/remote connection
- ✅ You want minimal resource usage
- ✅ You like retro/nostalgic interfaces
- ✅ You're on a low-spec machine

**Run:** `python run.py` or `python ttube.py`

---

### Use **GUI** (`ttube_gui.py`) if:
- ✅ You prefer graphical interfaces with mouse support
- ✅ You want a modern, professional look
- ✅ You're on Windows/macOS/Linux desktop
- ✅ You prefer visual feedback and buttons
- ✅ You want an easier learning curve
- ✅ You like seeing lyrics while playing

**Run:** `python run_gui.py` or double-click `run_gui.bat`

---

## 📊 Feature Comparison

| Feature | Terminal TUI | GUI |
|---------|------------|-----|
| **Search** | Keyboard input | Text box + button |
| **Results** | Text list | Scrollable list |
| **Playback** | Keyboard controls | Buttons + sliders |
| **Progress** | Text progress bar | Visual progress bar |
| **Seeking** | Arrow keys | Slider drag |
| **Lyrics** | Full screen mode | Side panel |
| **Theme** | Colored text | Dark theme |
| **Mouse Support** | Limited | Full |
| **Installation** | Simple (no GUI libs) | Requires PyQt5 |
| **Performance** | Very light | Light |
| **Learning Curve** | Steep | Gentle |

---

## 🚀 Installation

### Both Versions
```bash
pip install -r requirements.txt
```

### Terminal Only
```bash
pip install yt-dlp sounddevice imageio-ffmpeg
```

### GUI Only
```bash
pip install PyQt5 yt-dlp sounddevice imageio-ffmpeg
```

---

## 🎵 How to Use Each Version

### Terminal TUI
```bash
python run.py
```
Then:
1. Type your search query (e.g., "Taylor Swift")
2. Press Enter to search
3. Use arrow keys to select a result
4. Press Enter to play
5. Use P to pause, S to stop, L for lyrics, Q to quit

### GUI
```bash
python run_gui.py
```
Then:
1. Type your search query in the text box
2. Click "Search" or press Enter
3. Click a result to select it
4. Click "▶ Play" to start
5. Use buttons to pause/stop or drag sliders to seek

---

## 📚 Documentation

### Terminal Version
- [README.md](README.md) - Main documentation
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick commands
- [GETTING_STARTED.md](GETTING_STARTED.md) - Getting started guide

### GUI Version  
- [README_GUI.md](README_GUI.md) - Full GUI documentation
- [QUICKSTART_GUI.md](QUICKSTART_GUI.md) - Quick start guide
- [GUI_IMPLEMENTATION.md](GUI_IMPLEMENTATION.md) - Technical details

### General
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [CONFIG.md](CONFIG.md) - Configuration guide
- [LYRICS_GUIDE.md](LYRICS_GUIDE.md) - Lyrics documentation

---

## 🎮 Controls Reference

### Terminal Controls
| Key | Action |
|-----|--------|
| Enter | Search / Play |
| ↑↓ | Navigate |
| Space | Pause |
| P | Pause |
| S | Stop |
| L | Lyrics |
| ←→ | Seek ±5s |
| [ ] | Seek ±10s |
| PgUp/Dn | Seek ±30s |
| Q | Quit |

### GUI Controls
| Action | How |
|--------|-----|
| Search | Type + Enter/Click |
| Select | Click item |
| Play | Button or Enter |
| Pause | Button or Space |
| Stop | Button |
| Seek | Drag progress bar |
| Volume | Drag volume slider |
| Quit | Close window |

---

## 🔧 Troubleshooting

### Terminal TUI Issues
- **Curses not found**: `pip install windows-curses` (Windows)
- **Colors not showing**: Try different terminal emulator
- **See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for more**

### GUI Issues
- **PyQt5 not found**: `pip install PyQt5`
- **GUI looks small**: Set `QT_AUTO_SCREEN_SCALE_FACTOR=1`
- **No audio**: Install FFmpeg: `choco install ffmpeg` (Windows)
- **See [README_GUI.md](README_GUI.md) for more**

### Both Versions
- **No results**: Check internet connection
- **Playback stutters**: Ensure stable internet + FFmpeg installed
- **Song won't play**: Try a different result

---

## 📁 Project Structure

```
TTube/
├── 🖥️ TERMINAL VERSION
│   ├── ttube.py                    # Main TUI app
│   ├── ttube_youtube.py            # YouTube backend
│   ├── ttube_stream.py             # Stream engine
│   └── run.py                      # TUI launcher
│
├── 🎨 GUI VERSION
│   ├── ttube_gui.py                # Main GUI app
│   ├── run_gui.py                  # GUI launcher
│   ├── run_gui.bat                 # Windows launcher
│   └── run_gui.sh                  # Unix launcher
│
├── 📖 DOCUMENTATION
│   ├── README.md                   # Main readme
│   ├── README_GUI.md               # GUI docs
│   ├── QUICKSTART_GUI.md           # GUI quick start
│   ├── QUICK_REFERENCE.md          # TUI reference
│   ├── GETTING_STARTED.md          # Getting started
│   ├── GUI_IMPLEMENTATION.md       # Technical details
│   └── ... (other docs)
│
└── ⚙️ CONFIG
    ├── requirements.txt            # Dependencies
    ├── setup.cfg                   # Setup config
    ├── pyproject.toml              # Project config
    └── ... (other config)
```

---

## 💡 Pro Tips

### For Terminal Users
- Use specific search terms for better results
- Press `L` to switch between results and lyrics
- Tab switches between search and results panels
- Type in the search bar, then Tab to switch focus

### For GUI Users
- Double-click results to play (faster than button)
- Keyboard shortcuts still work (Enter, Space, etc.)
- Drag the seek slider for precise control
- Scroll through results with mouse wheel

---

## 🎁 What's New in GUI

**Coming from Terminal?** Here's what the GUI adds:
- ✨ Visual progress bar
- ✨ Volume slider
- ✨ Lyrics side panel (not full screen)
- ✨ Mouse support for everything
- ✨ Modern dark theme
- ✨ No terminal knowledge needed
- ✨ Easier for new users

---

## 🔄 Switching Between Versions

**You can run both!** They're completely independent:

```bash
# Terminal in one window
python run.py

# GUI in another window
python run_gui.py

# Even use them simultaneously with different accounts
```

Each version uses the same backend, so they share YouTube search and streaming capabilities.

---

## 📞 Getting Help

### Quick Links
- **Not sure where to start?** → [QUICKSTART_GUI.md](QUICKSTART_GUI.md) (GUI) or [GETTING_STARTED.md](GETTING_STARTED.md) (Terminal)
- **Need keyboard reference?** → [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Having issues?** → Check [README.md](README.md) or [README_GUI.md](README_GUI.md)
- **Want to know how it works?** → [GUI_IMPLEMENTATION.md](GUI_IMPLEMENTATION.md)

---

## ✅ Compatibility

- ✅ **Windows** - Both versions
- ✅ **macOS** - Both versions  
- ✅ **Linux** - Both versions
- ✅ **Python 3.10+** - Required
- ✅ **FFmpeg** - Optional but recommended

---

**Choose your favorite version and start streaming! 🎵**
