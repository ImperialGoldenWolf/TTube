# Changelog

## Latest Updates

### Bug Fixes
- **Fixed "P" key interference**: Keys like `P`, `S`, and `Space` now work correctly in search mode without triggering playback controls
- **Fixed key overlaps**: Implemented mode-aware keybinding system to prevent command keys from interfering with search input
- **Removed search character limit**: Search queries can now be as long as needed (display truncation remains for UI purposes)
- **Fixed mode switching**: Improved focus control to prevent accidental mode switches while typing

### UI Improvements
- **Enhanced color scheme**: Added more vibrant colors with:
  - Cyan headers
  - Yellow-on-blue results section
  - Green status indicators
  - Magenta search labels
  - Visual feedback with background colors
  
- **Added special characters**: Improved visual polish with Unicode symbols:
  - `▶` for play/navigation indicators
  - `🔍` for search icon
  - `📋` for results section
  - `♪` for audio/VU meter
  - `⚙` for status messages
  - `⏸` for pause indicator
  - `█░` for scrollbar visualization
  
- **Reorganized layout**:
  - Removed decorative line separator at top
  - Moved progress bar and VU meter below search results
  - Better space utilization for results display
  - Improved scrollable results list with visual scrollbar

- **Improved scroll indicator**: 
  - Visual scrollbar showing current position
  - Position counter `[N/Total]` format
  - Better visual feedback for navigation

### UI Elements
- Braille spinner animation for busy states
- Better visual hierarchy with color pairs
- Cleaner help text with arrow symbols
- More polished overall appearance

### Code Quality
- Better key handling with mode-aware processing
- Cleaner separation of concerns
- Improved readability with organized sections

---

## Installation & Running

### Quick Start
```bash
python install.py
```

### Manual Install
```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux/Mac: source .venv/bin/activate
pip install -e .
```

### Run TTube
```bash
python -m ttube
# or
python ttube.py
```

---

## Platform Support
- ✅ Windows (10+)
- ✅ macOS (10.12+)
- ✅ Linux (most distributions)
- ✅ Cross-platform compatible

## Dependencies
- Python 3.10+
- yt-dlp
- sounddevice
- imageio-ffmpeg
- windows-curses (Windows only)
