"""
Half-block album artwork renderer for 256-colour terminals.

Technique
─────────
Each terminal cell represents TWO vertical pixels using the character
'▀' (U+2580 UPPER HALF BLOCK).  The cell's foreground colour is the
top pixel; the background colour is the bottom pixel.  This gives an
effective vertical resolution of 2 × terminal_rows.

Requires Pillow; degrades gracefully (HAS_PIL = False) when absent.
"""
from __future__ import annotations

import io
import urllib.request
from typing import List, Tuple

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Each element: (unicode char, xterm-256 fg index, xterm-256 bg index)
ArtCell = Tuple[str, int, int]
ArtRows = List[List[ArtCell]]


def rgb_to_xterm256(r: int, g: int, b: int) -> int:
    """Map an sRGB triplet to the nearest index in the xterm-256 colour cube."""
    # The 6×6×6 colour cube occupies indices 16–231.
    r6 = round(r / 51)
    g6 = round(g / 51)
    b6 = round(b / 51)
    return 16 + 36 * r6 + 6 * g6 + b6


class ArtRenderer:
    """
    Download an image URL and render it as Unicode half-block art.

    Usage (from a background thread)::

        renderer = ArtRenderer()
        success  = renderer.fetch_and_process(url, art_width=24, art_height=10)

    Then in the draw loop::

        if renderer.is_ready():
            for row_idx, row in enumerate(renderer.rows):
                for col_idx, (char, fg, bg) in enumerate(row):
                    ...
    """

    def __init__(self) -> None:
        self._rows: ArtRows = []
        self._dominant: int = 20  # fallback: dark blue-ish xterm index

    # ── Public interface ──────────────────────────────────────────────────────

    def fetch_and_process(
        self,
        url:        str,
        art_width:  int = 22,
        art_height: int = 10,
    ) -> bool:
        """
        Fetch the image at *url*, resize it, and convert to half-block rows.

        *art_width*  – columns the art should occupy in the terminal.
        *art_height* – rows  the art should occupy (each row = 2 pixel rows).

        Returns True on success, False on any error.
        Thread-safe (does not touch curses).
        """
        if not HAS_PIL:
            return False
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "TTube/0.1"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw = resp.read()

            img = Image.open(io.BytesIO(raw)).convert("RGB")
            # Each terminal row encodes 2 pixel rows → resize to (w, h*2)
            img = img.resize((art_width, art_height * 2), Image.LANCZOS)
            pixels = list(img.getdata())

            rows: ArtRows = []
            for row_idx in range(art_height):
                row: List[ArtCell] = []
                for col_idx in range(art_width):
                    top = pixels[row_idx * 2 * art_width + col_idx]
                    bot = pixels[(row_idx * 2 + 1) * art_width + col_idx]
                    row.append(("▀", rgb_to_xterm256(*top), rgb_to_xterm256(*bot)))
                rows.append(row)

            self._rows = rows

            # Dominant colour from centre of image
            cx = art_width  // 2
            cy = art_height        # middle pixel row (in the 2× expanded image)
            self._dominant = rgb_to_xterm256(*pixels[cy * art_width + cx])
            return True

        except Exception:
            return False

    def is_ready(self) -> bool:
        return bool(self._rows)

    def clear(self) -> None:
        self._rows = []

    @property
    def rows(self) -> ArtRows:
        return self._rows

    @property
    def dominant_color(self) -> int:
        """xterm-256 index of the image's approximate dominant colour."""
        return self._dominant
