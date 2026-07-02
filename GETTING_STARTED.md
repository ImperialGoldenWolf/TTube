# Getting Started with TTube

Welcome to TTube - Terminal YouTube Audio Streamer! This guide will help you get started quickly.

---

## Quick Start (5 minutes)

### Windows Users

1. **Download TTube** to a folder on your computer

2. **Open PowerShell** and navigate to the TTube folder:
   ```powershell
   cd "C:\Path\To\TTube"
   ```

3. **Run the installer:**
   ```powershell
   python install_app.py
   ```
   
   This will:
   - Verify Python 3.10+ is installed
   - Create a virtual environment
   - Install all dependencies
   - Download and configure FFmpeg
   - Create desktop shortcuts

4. **Run TTube:**
   - Option A: Double-click `ttube_launcher.bat`
   - Option B: Run `python run.py`
   - Option C: Run `python -m ttube`

---

### macOS Users

1. **Download TTube** to a folder on your computer

2. **Open Terminal** and navigate to the TTube folder:
   ```bash
   cd /path/to/TTube
   ```

3. **Run the installer:**
   ```bash
   python3 install_app.py
   ```

4. **Run TTube:**
   ```bash
   ./ttube.sh
   ```
   or
   ```bash
   python3 -m ttube
   ```

---

### Linux Users

1. **Download TTube** to a folder on your computer

2. **Open Terminal** and navigate to the TTube folder:
   ```bash
   cd /path/to/TTube
   ```

3. **Install system dependencies** (Ubuntu/Debian):
   ```bash
   sudo apt-get install python3.10 python3-venv ffmpeg
   ```

4. **Run the installer:**
   ```bash
   python3 install_app.py
   ```

5. **Run TTube:**
   ```bash
   ./ttube.sh
   ```

---

## First Run

When you start TTube for the first time, you'll see:

```
>> TTube v0.1
=====================================================
Enter: search/play  ↑↓: navigate  Esc: search  Tab: switch  P/Space: pause  S: stop  Q: quit
Seek: ←→ ±5s  [ ] ±10s  PgUp/Dn ±30s  Home/End

[?] Search: 
[*] Results (0)
[*] Status: Type a search query (spaces supported) and press Enter.
```

---

## Basic Usage

### Searching

1. **Type your search query** in the search bar
   - Example: `Beatles Yesterday`
   - Example: `lofi hip hop`

2. **Press Enter** to search YouTube

3. **Wait for results** - You'll see:
   ```
   [*] Results (10)
   >> Best Song - Artist 1      [1/10]
      Another Song - Artist 2
      Great Hit - Artist 3
   ```

### Playing

1. **Use arrow keys** (↑↓) to navigate results

2. **Press Enter** to play the selected song

3. You'll see playback information:
   ```
   >> Now: Best Song - Artist 1
   [========~~~~~-----] 01:23 / 03:45  buf:0.8s
   [VU] L[########] R[########]
   ```

### Playback Controls

| Key | Action |
|-----|--------|
| `P` or `Space` | Pause/Resume |
| `S` | Stop playback |
| `←` | Seek back 5 seconds |
| `→` | Seek forward 5 seconds |
| `[` | Seek back 10 seconds |
| `]` | Seek forward 10 seconds |
| `PgUp` | Seek back 30 seconds |
| `PgDn` | Seek forward 30 seconds |
| `Home` | Jump to start |
| `End` | Jump to end |

### Navigation

| Key | Action |
|-----|--------|
| `Tab` | Switch between search and results |
| `Esc` | Return to search |
| `Q` | Quit TTube |

---

## Understanding the Interface

### Header Line
```
>> TTube v0.1                           [RESULTS] | Searching
```
- `>> TTube v0.1` - Application name and version
- `[RESULTS]` - Current mode (SEARCH or RESULTS)
- `Searching` - Current task (Searching, Resolving, etc.)

### Search Bar
```
[?] Search*: your query here
```
- `[?]` - Search icon
- `*` - Shows when search is active
- Text you type appears here

### Results List
```
[*] Results (10)
>> Best Result - Artist              [1/10]
   Second Result - Artist
   Third Result - Artist
```
- `[*]` - Results icon
- `(10)` - Number of results found
- `>>` - Currently selected (highlighted in color)
- `[1/10]` - Current position / total results

### Now Playing
```
>> Now: Best Result - Artist
[========~~~~~-----] 01:23 / 03:45  buf:0.8s
[VU] L[########] R[########]
```
- `>> Now:` - Currently playing track
- `[========~~~~~-----]` - Progress bar
  - `=` = Played
  - `~` = Buffered
  - `-` = Not yet buffered
- `01:23 / 03:45` - Current time / Total time
- `buf:0.8s` - Buffer size
- `[VU]` - Volume Unit meter
- `L[...]` - Left channel level
- `R[...]` - Right channel level

### Status Bar
```
[*] Status: Playing.
```
- Shows current status
- Red if error: `[!] Error: ...`
- Green if playing: `[+] Playing.`

---

## Common Issues & Solutions

### "Python version too old"
```
Python 3.10+ is required!
```
**Solution:**
- Download Python 3.10+ from https://www.python.org/
- Reinstall TTube after upgrading Python

### "Virtual environment not found"
```
[!] Virtual environment not found!
[>] Please run: python install_app.py
```
**Solution:**
- Run the installer: `python install_app.py`

### "No audio output"
```
Playback failed: ...
```
**Checklist:**
- [ ] Speakers/headphones connected?
- [ ] Volume not muted?
- [ ] Audio device working? (Test with other apps)
- [ ] FFmpeg installed? (Check with `ffmpeg -version`)

### "Search fails"
```
Search failed: ...
```
**Checklist:**
- [ ] Internet connection working?
- [ ] Try a different search term?
- [ ] yt-dlp installed? (Check with `pip list | grep yt-dlp`)

### "Can't find FFmpeg"
```
Note: If FFmpeg is missing, TTube will attempt a Python fallback via imageio-ffmpeg
```
**Solution (Optional):**
- Install FFmpeg from https://ffmpeg.org/download.html
- Or reinstall TTube: `python install_app.py`

---

## Tips & Tricks

### Finding Good Audio Streams

1. **Search by artist:** `The Beatles`
2. **Search with "official":** `Song Title official audio`
3. **Search for playlists:** `lo-fi hip hop beats`
4. **Search for radio:** `24/7 jazz radio`

### Better Playback

- **Stable internet:** 5+ Mbps recommended for smooth streaming
- **Good speakers:** Enhance audio quality significantly
- **Close other apps:** Reduce CPU usage, smoother playback

### Keyboard Shortcuts

- **Ctrl+C** - Emergency stop (if app freezes)
- **Type while browsing** - Automatically switches to search
- **Arrow keys** - Work in results to navigate

---

## Uninstalling TTube

### Windows
```powershell
# Just delete the TTube folder
Remove-Item -Recurse -Force "C:\Path\To\TTube"
# Remove shortcuts
Remove-Item "$env:USERPROFILE\Desktop\TTube.lnk"
Remove-Item "$env:USERPROFILE\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\TTube" -Recurse
```

### macOS/Linux
```bash
# Just delete the TTube folder
rm -rf /path/to/TTube
```

---

## Next Steps

- **[CONFIG.md](CONFIG.md)** - Customize colors, audio device, UI elements
- **[README.md](README.md)** - Full documentation
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and features

---

## Getting Help

### Check Logs
If TTube crashes, check for error messages or run:
```bash
python -m ttube 2>&1 | tee ttube_debug.log
```

### Known Issues
See [CHANGELOG.md](CHANGELOG.md) for known issues and workarounds

### Report Issues
Visit: https://github.com/your-org/ttube/issues

---

## Enjoy!

You're all set! Start searching for your favorite music and enjoy streaming from your terminal.

```
>> TTube v0.1
=====================================================
Happy listening! Press Q to quit anytime.
```

---

**Getting Started Guide v0.1** | 2026-05-08
