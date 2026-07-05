"""
TTube Enhanced – package entry point.

Launch:
    python -m ttube_enhanced        (from the TTube root directory)
"""
from __future__ import annotations

import curses
import os
import sys


def _setup_console() -> None:
    """Set window title, embed taskbar icon, and resize to work area (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32   = ctypes.windll.user32

        # Title
        kernel32.SetConsoleTitleW("TTube Enhanced")

        # Icon (from parent directory, same ico used by main ttube)
        _here   = os.path.dirname(os.path.abspath(__file__))
        _parent = os.path.dirname(_here)
        ico     = os.path.join(_parent, "ttube.ico")
        if not os.path.exists(ico):
            ico = os.path.join(_here, "ttube.ico")

        if os.path.exists(ico):
            LR_LOADFROMFILE = 0x00000010
            IMAGE_ICON      = 0x00000001
            WM_SETICON      = 0x0080
            hicon_s = user32.LoadImageW(None, ico, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            hicon_b = user32.LoadImageW(None, ico, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            hwnd    = kernel32.GetConsoleWindow()
            if hwnd:
                if hicon_s: user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_s)
                if hicon_b: user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_b)

        # Windowed-maximise via SetWindowPos → work area (keeps chrome)
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            class RECT(ctypes.Structure):
                _fields_ = [("left",   ctypes.c_long), ("top",    ctypes.c_long),
                             ("right",  ctypes.c_long), ("bottom", ctypes.c_long)]
            work = RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)
            user32.SetWindowPos(
                hwnd, 0,
                work.left, work.top,
                work.right - work.left,
                work.bottom - work.top,
                0x0004 | 0x0010,  # SWP_NOZORDER | SWP_NOACTIVATE
            )
    except Exception:
        pass


def main() -> None:
    _setup_console()
    # Local import so sys.path is set first
    from app import cli   # noqa: F401  (resolved via sys.path in app.py)
    cli()


if __name__ == "__main__":
    # Allow running as: python ttube_enhanced/__main__.py
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    main()
