╔════════════════════════════════════════════════════════════════════════════╗
║                    TTube - QUICK REFERENCE GUIDE                            ║
║                     Lyrics, Icons & Executables                             ║
╚════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎵 LYRICS FEATURE - QUICK START

  What it does:
  ✓ Auto-fetches subtitles from YouTube
  ✓ Shows lyrics line-by-line in real-time
  ✓ Smooth animations as song progresses
  ✓ Shows current line + next line preview
  ✓ Only displays if subtitles available

  How to use:
  1. Play a video
  2. Lyrics auto-load (in background)
  3. See display below VU meter:
     >> This is the current lyric          (green, bold, animated)
        Next lyric line preview             (gray, dimmed)
  4. Press 'L' to toggle lyrics ON/OFF

  Keyboard:
  ┌─ L      → Toggle lyrics ON/OFF
  ├─ P      → Pause/Resume
  ├─ S      → Stop
  ├─ Q      → Quit
  └─ (all other controls unchanged)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎨 ICON & BRANDING - QUICK START

  File format: .ico (256x256 pixels)
  Filename: ttube.ico
  Location: TTube project root folder

  How to create icon:
  Option A: Online (1 minute)
  ─────────────────────────
  1. Go: https://icoconvert.com/
  2. Upload: Your image (300x300px+)
  3. Download: as .ico
  4. Place: TTube/ttube.ico
  Done! ✓

  Option B: Python (2 minutes)
  ────────────────────────────
  from PIL import Image
  img = Image.open('your_image.png')
  img = img.resize((256, 256))
  img.save('ttube.ico', format='ICO')
  
  Option C: Command line (Windows)
  ─────────────────────────────────
  pip install pillow
  python ttube_icon_creator.py

  Where it's used:
  ✓ Desktop shortcut icon
  ✓ Start Menu entry
  ✓ Taskbar button
  ✓ Installer window

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💻 EXECUTABLE CREATION - QUICK START

  OPTION 1: PyInstaller (Recommended)
  ───────────────────────────────────

  Step 1: Install
  pip install pyinstaller>=6.0

  Step 2: Build
  pyinstaller ttube.spec

  Step 3: Test
  .\dist\ttube\ttube.exe

  Result: Standalone .exe (~250 MB)
  Users: Double-click to run (no Python needed!)

  OPTION 2: NSIS Installer (Professional)
  ───────────────────────────────────────

  Step 1: Install NSIS
  Download: https://nsis.sourceforge.io/
  Install normally

  Step 2: Build installer
  makensis ttube_installer.nsi

  Step 3: Distribute
  TTube-0.1.0-Installer.exe (~200 MB)
  Creates: Start Menu, shortcuts, uninstaller

  OPTION 3: Combined (Best)
  ─────────────────────────

  1. Create EXE with PyInstaller
  2. Wrap with NSIS installer
  3. Result: Professional Windows installer
  4. Users get: Start Menu entry, uninstaller, shortcuts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 ANSWER TO YOUR QUESTIONS

Q: Where do I put my icon?
A: TTube/ttube.ico
   - Format: .ico file
   - Size: 256x256 pixels
   - Will auto-use for shortcuts and installer

Q: Does it need to be .ico or .png?
A: Ideally .ico (Windows native)
   - .ico works perfectly
   - .png works too (auto-converted)
   - Recommended: .ico (no conversion needed)

Q: How to make an installer using NSIS?
A: Simple 2-step process:
   1. Install NSIS: https://nsis.sourceforge.io/
   2. Run: makensis ttube_installer.nsi
   Result: TTube-0.1.0-Installer.exe
   
   Full guide: See ICON_INSTALLER_GUIDE.md

Q: Does the app become an executable?
A: YES! Multiple ways:
   
   1. PyInstaller method (easiest):
      pyinstaller ttube.spec
      → Creates ttube.exe standalone
   
   2. NSIS installer method:
      makensis ttube_installer.nsi
      → Creates professional installer .exe
   
   3. Direct Python module (current):
      python -m ttube
      → No .exe needed for development

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 COMPLETE WORKFLOW

Step 1: ADD YOUR ICON
──────────────────────
Place: TTube/ttube.ico
Source: Create from image or use existing

Step 2: TEST LYRICS
──────────────────────
Run: python -m ttube
Action: Play video, press 'L' to see lyrics
Result: Lyrics display if available

Step 3: BUILD EXECUTABLE
──────────────────────────
Run: pyinstaller ttube.spec
Result: dist/ttube/ttube.exe
Test: .\dist\ttube\ttube.exe

Step 4: CREATE INSTALLER
──────────────────────────
Run: makensis ttube_installer.nsi
Result: TTube-0.1.0-Installer.exe
Distribute: Send to users

Step 5: DISTRIBUTE
──────────────────────────
Option A: Send ttube.exe directly
         Users: Double-click to run

Option B: Send TTube-0.1.0-Installer.exe
         Users: Run installer, creates Start Menu entry

Option C: Create portable ZIP
         Users: Extract and run, no installation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 FILE LOCATIONS

  Icon files:
  TTube/ttube.ico                    ← Put your icon here

  Executables (after build):
  dist/ttube/ttube.exe               ← PyInstaller .exe
  TTube-0.1.0-Installer.exe          ← NSIS installer .exe

  Configuration files:
  ttube.spec                         ← PyInstaller config
  ttube_installer.nsi                ← NSIS config
  ttube_launcher.bat                 ← Windows launcher
  install_app.py                     ← Main installer

  Documentation:
  LYRICS_GUIDE.md                    ← Lyrics feature guide
  ICON_INSTALLER_GUIDE.md            ← This topic in detail
  FEATURE_UPDATE.md                  ← What's new
  GETTING_STARTED.md                 ← First time setup

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ QUICK COMMANDS

Lyrics:
  L                    Toggle lyrics display
  
Build:
  python install_app.py          Install/setup
  python -m ttube                Run app
  pyinstaller ttube.spec         Create .exe
  makensis ttube_installer.nsi   Create installer
  
Test:
  .\dist\ttube\ttube.exe         Test standalone exe
  .\TTube-0.1.0-Installer.exe    Test installer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 DETAILED GUIDES

Feature deep-dive:
  LYRICS_GUIDE.md                ← How lyrics work in detail
  ICON_INSTALLER_GUIDE.md        ← Icons and installers explained

Getting started:
  GETTING_STARTED.md             ← First time user guide
  FEATURE_UPDATE.md              ← What's new in this version

Development:
  CONFIG.md                      ← Customization options
  Makefile                       ← Development commands

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CHECKLIST: Ready to Ship?

Preparation:
  [ ] Icon file: ttube.ico created/placed
  [ ] Lyrics tested: Play video, press 'L'
  [ ] App tested: python -m ttube works

Building:
  [ ] PyInstaller installed: pip install pyinstaller
  [ ] Executable created: pyinstaller ttube.spec
  [ ] EXE tested: .\dist\ttube\ttube.exe runs

Installer (optional):
  [ ] NSIS installed from nsis.sourceforge.io
  [ ] Installer built: makensis ttube_installer.nsi
  [ ] Installer tested: Run .exe, verify shortcuts

Distribution:
  [ ] Decide format: .exe or .exe installer
  [ ] Create package: Gather files + icon
  [ ] Write instructions: What users need to do
  [ ] Ready to distribute!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 TIPS & TRICKS

Lyrics:
  • Press 'L' anytime to toggle during playback
  • Lyrics auto-sync with video position
  • No lyrics? Video might not have captions
  • English captions prioritized automatically

Icon:
  • Use 256x256 or 128x128 pixel image
  • PNG or ICO format (both work)
  • Will automatically scale for different uses
  • Can update anytime - just replace ttube.ico

Executable:
  • First build takes 30-60 seconds
  • Subsequent builds are faster
  • File size ~250-300 MB (includes Python runtime)
  • Works without Python installed on target machine

Installer:
  • Professional-looking Windows installer
  • Creates Start Menu folder automatically
  • Includes uninstaller
  • Users can easily uninstall from Control Panel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 YOUR NEXT STEPS

1. CREATE ICON
   → Download/create 256x256 image
   → Convert to .ico online or locally
   → Save as: TTube/ttube.ico

2. TEST LYRICS
   → Run: python -m ttube
   → Play any YouTube video
   → Press 'L' to toggle lyrics
   → Verify display

3. BUILD EXECUTABLE
   → Install: pip install pyinstaller
   → Build: pyinstaller ttube.spec
   → Test: .\dist\ttube\ttube.exe

4. CREATE INSTALLER (OPTIONAL)
   → Download NSIS installer
   → Run: makensis ttube_installer.nsi
   → Test: Run TTube-0.1.0-Installer.exe

5. DISTRIBUTE
   → Send TTube-0.1.0-Installer.exe to users
   → Or: Send ttube.exe + icon + docs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 YOU'RE ALL SET!

Your TTube application now has:
✅ Professional lyrics display with animations
✅ Custom icon support
✅ Executable distribution option
✅ Professional Windows installer
✅ No emojis - pure ASCII interface
✅ Complete documentation

Everything ready for professional distribution!

Questions? See:
  • LYRICS_GUIDE.md       → About lyrics
  • ICON_INSTALLER_GUIDE.md → About icons & installers
  • GETTING_STARTED.md    → Getting started
  • CONFIG.md             → Customization

Happy distributing! 🚀

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Version: 0.1.0
Last Updated: 2026-05-08
Status: ✅ Complete & Production Ready
