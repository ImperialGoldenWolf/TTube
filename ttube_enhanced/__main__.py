"""
TTube Enhanced – launcher.
Starts the Flask server on localhost:7777 and opens a native pywebview window.
"""
from __future__ import annotations

import os
import sys
import threading
import time

_HERE   = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (_HERE, _PARENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PORT = 7777

import server
import webview  # type: ignore

def _check_deps() -> None:
    missing = []
    for pkg, import_name in [("Flask", "flask"), ("Pillow", "PIL"), ("webview", "webview")]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    if missing:
        msg = f"Missing dependencies: {', '.join(missing)}\n"
        try:
            with open("crash.log", "w") as f:
                f.write(msg)
        except Exception:
            pass
        sys.exit(1)


def main() -> None:
    _check_deps()

    server._WEBVIEW_MODE = True

    def start_flask() -> None:
        server.app.run(
            host="127.0.0.1",
            port=PORT,
            threaded=True,
            debug=False,
            use_reloader=False,
        )

    t = threading.Thread(target=start_flask, daemon=True)
    t.start()

    time.sleep(1)  # wait for Flask

    class Api:
        def __init__(self):
            self.is_max = False
            self.orig_size = (1100, 750)
            self.orig_pos = (0, 0)
        def minimize(self):
            webview.windows[0].minimize()
        def maximize(self):
            w = webview.windows[0]
            if self.is_max:
                w.resize(self.orig_size[0], self.orig_size[1])
                w.move(self.orig_pos[0], self.orig_pos[1])
                self.is_max = False
            else:
                self.orig_size = (w.width, w.height)
                self.orig_pos = (w.x, w.y)
                try:
                    import ctypes
                    from ctypes.wintypes import RECT
                    rect = RECT()
                    user32 = ctypes.windll.user32
                    user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
                    
                    try:
                        dpi = user32.GetDpiForSystem()
                        scale = dpi / 96.0
                    except AttributeError:
                        scale = 1.0

                    w.move(int(rect.left / scale), int(rect.top / scale))
                    w.resize(int((rect.right - rect.left) / scale), int((rect.bottom - rect.top) / scale))
                except Exception:
                    w.maximize()
                self.is_max = True
        def close(self):
            try:
                webview.windows[0].destroy()
            except Exception:
                pass
            import threading, os
            threading.Timer(0.1, lambda: os._exit(0)).start()

    # Create native window
    webview.create_window(
        title="TTube +",
        url=f"http://127.0.0.1:{PORT}",
        width=1100,
        height=750,
        min_size=(800, 600),
        background_color="#121212",
        frameless=True,
        easy_drag=False,
        js_api=Api()
    )
    
    # Blocks until window is closed
    webview.start(private_mode=False)


if __name__ == "__main__":
    main()
