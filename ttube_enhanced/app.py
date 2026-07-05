"""
TTube Enhanced – main TUI application.

New features over the base ttube.py:
  • iTunes-powered live search suggestions  (Tab to autocomplete)
  • Right info panel: album art (256-colour half-blocks) + metadata
  • Audio channel badge: MONO / STEREO / 2.1 / 5.1 / 7.1
  • '/' key shows a full keybind help overlay (inactive while searching)
  • 'D' key downloads selected track offline (MP3 320 kbps + lyrics)
  • Offline playback: plays local file when already downloaded

Run from the TTube root:
    python -m ttube_enhanced
"""
from __future__ import annotations

import curses
import os
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

# ── path bootstrap so we can import the parent package backends ───────────────
_HERE   = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (_HERE, _PARENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ttube_stream  import StreamPlayer
from ttube_youtube import (AudioStream, SearchResult,
                           resolve_best_audio_stream,
                           search_youtube, fetch_lyrics, Lyrics)

from itunes     import Metadata, search_suggestions, match_metadata
from art        import ArtRenderer, HAS_PIL
from downloader import DownloadManager, DownloadJob, DOWNLOAD_DIR

# ── Layout constants ──────────────────────────────────────────────────────────

PANEL_W   = 28     # Right panel content width (inside borders)
PANEL_TOT = PANEL_W + 2   # +1 separator col + 1 border col
ART_W     = PANEL_W - 2   # Art columns
ART_H     = 9             # Art rows (each = 2 pixel rows via ▀)
SUGG_MAX  = 5             # Max suggestion rows shown
BOTTOM    = 7             # Rows reserved for playback UI at bottom
MIN_W     = 72
MIN_H     = 20

SPINNER = "/-\\|"

HELP_TEXT = """\
╔══════════════ TTube+ Key Bindings ═══════════════╗
║                                                   ║
║  SEARCH MODE (typing in search bar)               ║
║   Enter      Search YouTube with query            ║
║   Tab        Cycle iTunes suggestions             ║
║   Backspace  Delete character                     ║
║   Ctrl+U     Clear search bar                     ║
║   Esc        Return to results                    ║
║                                                   ║
║  RESULTS MODE                                     ║
║   ↑ / ↓      Navigate result list                 ║
║   Enter      Play selected track                  ║
║   D          Download track  (MP3 320 + lyrics)   ║
║   P / Space  Pause / Resume playback              ║
║   S          Stop playback                        ║
║   L          Toggle synced lyrics                 ║
║                                                   ║
║  SEEKING  (when duration is known)                ║
║   ← / →      Seek ± 5 seconds                    ║
║   [ / ]      Seek ± 10 seconds                   ║
║   PgUp/Dn    Seek ± 30 seconds                   ║
║   Home / End  Jump to start / end                ║
║                                                   ║
║  ALWAYS                                           ║
║   /          Show this help (results mode)        ║
║   Q          Quit                                 ║
║                                                   ║
║         Press any key to close                    ║
╚═══════════════════════════════════════════════════╝"""


# ── Colour-pair registry ──────────────────────────────────────────────────────
# Pairs 1-19  : UI elements (fixed)
# Pairs 20+   : Art colour pairs (allocated on demand, cached)

_art_pair_cache: Dict[Tuple[int, int], int] = {}
_next_art_pair  = 20

def _get_art_pair(fg: int, bg: int) -> int:
    """Allocate (or return cached) a curses colour pair for half-block art."""
    global _next_art_pair
    key = (fg, bg)
    if key in _art_pair_cache:
        return _art_pair_cache[key]
    cap = min(curses.COLOR_PAIRS - 1, 511)
    if _next_art_pair > cap:
        _next_art_pair = 20
        _art_pair_cache.clear()
    try:
        curses.init_pair(_next_art_pair, fg, bg)
        _art_pair_cache[key] = _next_art_pair
        _next_art_pair += 1
    except curses.error:
        return 0
    return _art_pair_cache[key]


def _init_colors() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
    except Exception:
        pass
    C = curses
    curses.init_pair(1,  C.COLOR_CYAN,    -1)                # header
    curses.init_pair(2,  C.COLOR_BLACK,   C.COLOR_CYAN)      # selected row
    curses.init_pair(3,  C.COLOR_GREEN,   -1)                # playing / ok
    curses.init_pair(4,  C.COLOR_RED,     -1)                # error
    curses.init_pair(5,  C.COLOR_YELLOW,  C.COLOR_BLUE)      # results header
    curses.init_pair(6,  C.COLOR_MAGENTA, -1)                # search label
    curses.init_pair(7,  C.COLOR_GREEN,   C.COLOR_BLACK)     # status ok
    curses.init_pair(8,  C.COLOR_GREEN,   -1)                # progress bar
    curses.init_pair(9,  C.COLOR_CYAN,    -1)                # VU meter
    curses.init_pair(10, C.COLOR_WHITE,   C.COLOR_BLUE)      # suggestion selected
    curses.init_pair(11, C.COLOR_CYAN,    -1)                # suggestion normal
    curses.init_pair(12, C.COLOR_YELLOW,  -1)                # artist / album
    curses.init_pair(13, C.COLOR_WHITE,   -1)                # panel text
    curses.init_pair(14, C.COLOR_BLUE,    -1)                # panel border
    curses.init_pair(15, C.COLOR_WHITE,   C.COLOR_BLUE)      # panel title
    curses.init_pair(16, C.COLOR_BLACK,   C.COLOR_GREEN)     # download done
    curses.init_pair(17, C.COLOR_BLACK,   C.COLOR_YELLOW)    # download progress
    curses.init_pair(18, C.COLOR_WHITE,   C.COLOR_BLACK)     # help overlay bg
    curses.init_pair(19, C.COLOR_CYAN,    C.COLOR_BLACK)     # help overlay border


# ── Helper functions ──────────────────────────────────────────────────────────

def _safe(stdscr, y: int, x: int, s: str, attr: int = 0) -> None:
    try:
        stdscr.addstr(y, x, s, attr)
    except curses.error:
        pass


def _fmt(seconds: Optional[float]) -> str:
    if seconds is None:
        return "--:--"
    t = max(0, int(seconds))
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _pbar(width: int, played: float, buffered: Optional[float] = None) -> str:
    w = max(0, width)
    if w == 0:
        return ""
    pr = min(1.0, max(0.0, played))
    br = pr if buffered is None else min(1.0, max(pr, buffered))
    p  = min(w, int(round(pr * w)))
    b  = min(w, int(round(br * w)))
    return "=" * p + "~" * max(0, b - p) + "-" * max(0, w - b)


def _mbar(width: int, level: float) -> str:
    w = max(0, width)
    if w == 0:
        return ""
    f = min(w, int(round(min(1.0, max(0.0, level)) * w)))
    return "#" * f + "." * (w - f)


def _ch_label(n: int) -> str:
    """Return human-readable channel badge for audio_channels count."""
    return {1: "MONO", 2: "STEREO", 3: "2.1", 6: "5.1", 8: "7.1"}.get(n, f"{n}ch")


# ── Extended stream resolve (also returns channel count) ──────────────────────

def _resolve_enhanced(webpage_url: str) -> Tuple[AudioStream, int]:
    """Resolve audio stream AND detect channel count (mono/stereo/5.1 etc.)."""
    import yt_dlp as _ydl
    opts = {
        "quiet": True, "no_warnings": True,
        "skip_download": True, "format": "bestaudio/best",
        "noplaylist": True,
    }
    with _ydl.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(webpage_url, download=False)
    if not info:
        raise RuntimeError("yt-dlp returned no info")

    title    = info.get("title") or "(untitled)"
    duration = info.get("duration")
    dur_sec  = int(duration) if duration is not None else None
    formats  = info.get("formats") or []

    audio_fmts = [
        f for f in formats
        if f and f.get("vcodec") == "none"
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]

    channels = 2  # default stereo
    if audio_fmts:
        def _score(f):
            return (float(f.get("abr") or 0) * 1000,
                    float(f.get("tbr") or 0),
                    int(f.get("asr")   or 0))
        best = max(audio_fmts, key=_score)
        stream_url = best["url"]
        headers    = dict(best.get("http_headers") or info.get("http_headers") or {})
        channels   = int(best.get("audio_channels") or 2)
    else:
        stream_url = info.get("url", "")
        headers    = dict(info.get("http_headers") or {})

    stream = AudioStream(
        title=title, webpage_url=webpage_url,
        stream_url=stream_url, http_headers=headers,
        duration_seconds=dur_sec,
    )
    return stream, channels


# ── Application state ─────────────────────────────────────────────────────────

class App:
    def __init__(self) -> None:
        # Search / results
        self.query:    str             = ""
        self.results:  List[SearchResult] = []
        self.selected: int             = 0
        self._last_max_rows: int       = 10
        self.mode:     str             = "query"   # "query" | "results"

        # Status / now-playing
        self.status:      str = "Type to search. iTunes suggestions appear as you type."
        self.now_playing: str = ""
        self.channels:    int = 2   # current track audio channels

        # Suggestions
        self.suggestions:      List[Dict] = []
        self.suggestion_idx:   int        = -1
        self._sugg_query:      str        = ""
        self._sugg_debounce:   float      = 0.0

        # Per-track metadata + art
        self.current_meta: Optional[Metadata] = None
        self.art = ArtRenderer()
        self._art_256: bool = False  # set in main() after curses init

        # Lyrics
        self.lyrics:             Optional[Lyrics] = None
        self.current_lyric_idx:  int              = 0
        self.show_lyrics:        bool             = True

        # Help overlay
        self.show_help: bool = False

        # Download manager
        self.dl = DownloadManager()

        # Background work pool
        self._ex = ThreadPoolExecutor(max_workers=5)
        self._f_search:  Optional[Future] = None
        self._f_play:    Optional[Future] = None
        self._f_seek:    Optional[Future] = None
        self._f_lyrics:  Optional[Future] = None
        self._f_sugg:    Optional[Future] = None
        self._f_meta:    Optional[Future] = None
        self._f_art:     Optional[Future] = None
        self._play_gen:  int              = 0

        self.player = StreamPlayer()

    def close(self) -> None:
        try:
            self.player.stop()
        finally:
            self._ex.shutdown(wait=False, cancel_futures=True)

    def busy_label(self) -> str:
        if self._f_play:   return "Resolving"
        if self._f_search: return "Searching"
        if self._f_seek:   return "Seeking"
        return ""

    # ── Search ────────────────────────────────────────────────────────────────

    def start_search(self) -> None:
        q = self.query.strip()
        # If a suggestion is highlighted use it verbatim
        if 0 <= self.suggestion_idx < len(self.suggestions):
            s  = self.suggestions[self.suggestion_idx]
            q  = f"{s.get('trackName','')} {s.get('artistName','')}".strip()
            self.query = q
        if not q:
            self.status = "Enter a query first."
            return
        self.suggestions    = []
        self.suggestion_idx = -1
        self.show_suggestions_flag = False
        self.status = "Searching YouTube…"
        self._f_search = self._ex.submit(search_youtube, q, 10)

    def _fire_suggestions(self) -> None:
        q = self.query.strip()
        if len(q) < 2:
            self.suggestions    = []
            self.suggestion_idx = -1
            return
        now = time.time()
        if q != self._sugg_query:
            self._sugg_debounce = now + 0.35
            self._sugg_query    = q
        if now >= self._sugg_debounce and self._f_sugg is None:
            self._f_sugg = self._ex.submit(search_suggestions, q, SUGG_MAX)

    def tab_suggestion(self) -> None:
        if not self.suggestions:
            return
        self.suggestion_idx = (self.suggestion_idx + 1) % len(self.suggestions)
        s = self.suggestions[self.suggestion_idx]
        track  = s.get("trackName",  "")
        artist = s.get("artistName", "")
        self.query = f"{track} {artist}".strip() if artist else track

    # ── Playback ──────────────────────────────────────────────────────────────

    def start_play(self) -> None:
        if not self.results:
            self.status = "No results."
            return
        idx  = max(0, min(self.selected, len(self.results) - 1))
        item = self.results[idx]

        # Prefer local file if available
        local = self.dl.find_local(item.video_id)

        self.now_playing = item.title
        self.lyrics      = None
        self.current_lyric_idx = 0
        self.show_lyrics = True
        self.art.clear()
        self.current_meta = None
        self.channels = 2

        self._play_gen += 1
        gen = self._play_gen
        url = item.webpage_url

        # Always fetch lyrics (works for local too via video_id)
        self._f_lyrics = self._ex.submit(fetch_lyrics, url)

        # Fetch iTunes metadata for right panel
        self._f_meta = self._ex.submit(match_metadata, item.title)

        if local:
            # Offline: play immediately from disk
            self.status = "Playing (offline)."
            try:
                self.player.play(local, {})
            except Exception as e:
                self.status = f"Playback error: {e}"
            return

        def _do() -> Tuple[AudioStream, int]:
            stream, ch = _resolve_enhanced(url)
            if gen != self._play_gen:
                return stream, ch
            self.player.play(
                stream.stream_url,
                http_headers=stream.http_headers,
                duration_seconds=stream.duration_seconds,
            )
            return stream, ch

        self._f_play = self._ex.submit(_do)

    def start_download(self) -> None:
        if not self.results:
            self.status = "Nothing to download."
            return
        idx  = max(0, min(self.selected, len(self.results) - 1))
        item = self.results[idx]

        if self.dl.find_local(item.video_id):
            self.status = f"Already downloaded: {item.title}"
            return

        meta  = self.current_meta
        title  = meta.title  if meta and meta.title  else item.title
        artist = meta.artist if meta and meta.artist else ""

        self.dl.start(item.video_id, item.webpage_url, title, artist)
        self.status = f"Downloading: {title}"

    # ── Lyrics ────────────────────────────────────────────────────────────────

    def _get_lyric(self) -> Optional[str]:
        if not self.lyrics or not self.lyrics.lines:
            return None
        pos = self.player.position_seconds()
        if pos is None:
            return None
        for i, line in enumerate(self.lyrics.lines):
            if line.start_time <= pos < line.end_time:
                self.current_lyric_idx = i
                return line.text
            if pos < line.start_time:
                break
        return None

    def _get_next_lyric(self) -> Optional[str]:
        if not self.lyrics or not self.lyrics.lines:
            return None
        n = self.current_lyric_idx + 1
        return self.lyrics.lines[n].text if n < len(self.lyrics.lines) else None

    # ── Background polling ────────────────────────────────────────────────────

    def poll(self) -> None:
        # Suggestions
        if self._f_sugg is not None and self._f_sugg.done():
            try:
                res = self._f_sugg.result()
                self.suggestions    = res or []
                self.suggestion_idx = -1
            except Exception:
                self.suggestions = []
            finally:
                self._f_sugg = None

        # Search results
        if self._f_search is not None and self._f_search.done():
            try:
                self.results  = self._f_search.result()
                self.selected = 0
                self.mode     = "results" if self.results else "query"
                self.status   = f"Found {len(self.results)} result(s)."
            except Exception as e:
                self.status = f"Search failed: {e}"
            finally:
                self._f_search = None

        # Playback resolved
        if self._f_play is not None and self._f_play.done():
            try:
                stream, ch = self._f_play.result()
                self.now_playing = stream.title
                self.channels    = ch
                self.status      = "Playing."
            except Exception as e:
                self.status = f"Playback failed: {e}"
            finally:
                self._f_play = None

        # Seek
        if self._f_seek is not None and self._f_seek.done():
            try:
                self._f_seek.result()
                self.status = "Seeked."
            except Exception as e:
                self.status = f"Seek failed: {e}"
            finally:
                self._f_seek = None

        # Lyrics
        if self._f_lyrics is not None and self._f_lyrics.done():
            try:
                self.lyrics = self._f_lyrics.result()
                self.current_lyric_idx = 0
            except Exception:
                self.lyrics = None
            finally:
                self._f_lyrics = None

        # iTunes metadata
        if self._f_meta is not None and self._f_meta.done():
            try:
                meta = self._f_meta.result()
                self.current_meta = meta
                if meta and meta.artwork_url and self._art_256:
                    self._f_art = self._ex.submit(
                        self.art.fetch_and_process,
                        meta.artwork_url, ART_W, ART_H,
                    )
            except Exception:
                self.current_meta = None
            finally:
                self._f_meta = None

        # Art
        if self._f_art is not None and self._f_art.done():
            try:
                self._f_art.result()
            except Exception:
                pass
            finally:
                self._f_art = None

        # Debounced suggestions
        if self.mode == "query" and len(self.query.strip()) >= 2:
            self._fire_suggestions()

        # Download status → update status bar
        job = self.dl.current
        if job and job.status == "downloading":
            self.status = f"⬇ {job.display[:30]}  {job.progress}%"
        elif job and job.status == "postprocessing":
            self.status = f"⬇ {job.display[:30]}  processing…"
        elif job and job.status == "done" and job.path:
            saved = os.path.basename(job.path)
            self.status = f"✓ Saved: {saved}"
            self.dl.current = None
        elif job and job.status == "error":
            self.status = f"✗ Download failed: {job.error[:40]}"
            self.dl.current = None


# ── Draw ──────────────────────────────────────────────────────────────────────

def _draw(stdscr, app: App) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    HC = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD

    # ── Too small ─────────────────────────────────────────────────────────────
    if h < MIN_H or w < MIN_W:
        _safe(stdscr, 0, 0,
              f"Terminal too small – need {MIN_W}×{MIN_H} (have {w}×{h}).", HC)
        stdscr.refresh(); return

    # ── Help overlay ──────────────────────────────────────────────────────────
    if app.show_help:
        _draw_help(stdscr, h, w)
        stdscr.refresh(); return

    has_col  = curses.has_colors()
    is_busy  = bool(app.busy_label())
    spin     = SPINNER[int(time.time() * 8) % 4] if is_busy else " "

    # Effective widths
    panel_x  = w - PANEL_TOT        # left edge of right panel
    left_w   = panel_x - 1          # usable left-column width
    art_256  = app._art_256

    # ── Row 0: header ─────────────────────────────────────────────────────────
    logo = "♪ TTube+"
    mode_str = f"[{'SEARCH' if app.mode == 'query' else 'RESULTS'}]  {spin} {app.busy_label()}".rstrip()
    hint     = "  / for help"
    _safe(stdscr, 0, 0, logo, HC)
    _safe(stdscr, 0, max(0, w - len(mode_str) - len(hint) - 1),
          hint, curses.color_pair(14) if has_col else 0)
    _safe(stdscr, 0, max(0, w - len(mode_str) - 1), mode_str, HC)

    # ── Row 1: search bar ─────────────────────────────────────────────────────
    label      = "[?] Search" + ("*" if app.mode == "query" else "")
    label_attr = curses.color_pair(6) | curses.A_BOLD if has_col else curses.A_BOLD
    _safe(stdscr, 1, 0, f"{label}: ", label_attr)
    bar_x = len(label) + 2
    bar_w = max(0, left_w - bar_x)
    q     = app.query
    q_attr = curses.A_REVERSE if app.mode == "query" else 0
    _safe(stdscr, 1, bar_x,
          (q + " " * max(0, bar_w - len(q)))[:bar_w], q_attr)

    # ── Rows 2-6: suggestions dropdown (query mode only) ──────────────────────
    sugg_rows = 0
    if app.mode == "query" and app.suggestions:
        sugg_rows = min(SUGG_MAX, len(app.suggestions))
        for i in range(sugg_rows):
            y    = 2 + i
            s    = app.suggestions[i]
            trk  = s.get("trackName",  "")
            art  = s.get("artistName", "")
            text = f" ♪ {trk}  ·  {art} "
            text = text[:max(0, left_w - bar_x - 1)]
            if i == app.suggestion_idx:
                attr = curses.color_pair(10) | curses.A_BOLD if has_col else curses.A_REVERSE
            else:
                attr = curses.color_pair(11) if has_col else 0
            _safe(stdscr, y, bar_x, text, attr)

    # ── Results header ────────────────────────────────────────────────────────
    results_y = 2 + sugg_rows
    rh_attr   = curses.color_pair(5) | curses.A_BOLD if has_col else curses.A_BOLD
    rh_text   = f"[*] Results ({len(app.results)})" + ("*" if app.mode == "results" else "")
    _safe(stdscr, results_y, 0, rh_text[:max(0, left_w)], rh_attr)

    # ── Results list ─────────────────────────────────────────────────────────
    list_top = results_y + 1
    max_rows = max(0, h - list_top - BOTTOM)
    app._last_max_rows = max_rows

    if app.results and max_rows > 0:
        start = 0
        if app.selected >= max_rows:
            start = app.selected - max_rows + 1
        view  = app.results[start: start + max_rows]

        for i, r in enumerate(view):
            y   = list_top + i
            idx = start + i
            sel = idx == app.selected

            # Clean display title
            meta = app.current_meta if (sel and app.mode == "results") else None
            disp = (meta.title if meta and meta.title else r.title)

            # offline indicator
            offline = "◉ " if app.dl.find_local(r.video_id) else "  "
            prefix  = f"{'>> ' if sel else '   '}{offline}"
            line    = (prefix + disp)[: max(0, left_w - 1)]

            if sel:
                attr = curses.color_pair(2) | curses.A_BOLD if has_col else curses.A_REVERSE
            else:
                attr = 0
            _safe(stdscr, y, 0, line, attr)

        # Scroll indicator
        if len(app.results) > max_rows:
            pos_str = f"[{app.selected+1}/{len(app.results)}]"
            _safe(stdscr, results_y, max(0, left_w - len(pos_str)), pos_str,
                  curses.A_DIM)

    # ── Right panel ───────────────────────────────────────────────────────────
    px = panel_x
    if px < 1:
        px = 1
    # Vertical separator
    sep_attr = curses.color_pair(14) if has_col else 0
    for y in range(1, h - 1):
        _safe(stdscr, y, px - 1, "│", sep_attr)

    # Panel rows available (between header and bottom UI)
    panel_top  = 1
    panel_bot  = h - BOTTOM - 1
    panel_rows = max(0, panel_bot - panel_top)

    p_row = panel_top

    # Album art
    if art_256 and app.art.is_ready() and panel_rows >= ART_H:
        for ri, row in enumerate(app.art.rows[:ART_H]):
            y = p_row + ri
            if y >= panel_bot:
                break
            for ci, (char, fg, bg) in enumerate(row[:ART_W]):
                x = px + ci
                if x >= w:
                    break
                pn = _get_art_pair(fg, bg)
                if pn:
                    _safe(stdscr, y, x, char, curses.color_pair(pn))
        p_row += ART_H
        # Separator line
        if p_row < panel_bot:
            _safe(stdscr, p_row, px, "─" * min(PANEL_W, w - px - 1),
                  curses.color_pair(14) if has_col else 0)
            p_row += 1
    elif not app.art.is_ready() and app.now_playing:
        # Placeholder while art loads
        place_lines = ["┌" + "─" * (PANEL_W - 2) + "┐"]
        rows_free   = min(ART_H, panel_bot - p_row - 1)
        for ri in range(rows_free - 2):
            mid = "│" + " " * (PANEL_W - 2) + "│"
            if ri == rows_free // 2 - 1:
                lbl = " Loading art… "
                mid = "│" + lbl.center(PANEL_W - 2) + "│"
            place_lines.append(mid)
        place_lines.append("└" + "─" * (PANEL_W - 2) + "┘")
        for li, pl in enumerate(place_lines):
            y = p_row + li
            if y >= panel_bot:
                break
            _safe(stdscr, y, px, pl[:max(0, w - px - 1)],
                  curses.color_pair(14) if has_col else 0)
        p_row += len(place_lines)

    # Metadata text
    meta = app.current_meta
    if meta and p_row < panel_bot:
        t_attr  = curses.color_pair(13) | curses.A_BOLD if has_col else curses.A_BOLD
        a_attr  = curses.color_pair(12) if has_col else 0
        al_attr = curses.color_pair(12) | curses.A_DIM if has_col else curses.A_DIM

        # Title (wrapped to panel width)
        title_disp = meta.title or app.now_playing
        for chunk_start in range(0, len(title_disp), PANEL_W):
            chunk = title_disp[chunk_start: chunk_start + PANEL_W]
            if p_row >= panel_bot:
                break
            _safe(stdscr, p_row, px, chunk, t_attr)
            p_row += 1

        if meta.artist and p_row < panel_bot:
            _safe(stdscr, p_row, px, meta.artist[:PANEL_W], a_attr)
            p_row += 1

        if meta.album and p_row < panel_bot:
            _safe(stdscr, p_row, px, meta.album[:PANEL_W], al_attr)
            p_row += 1

        # Duration + channel badge on same line
        dur_str = meta.display_duration()
        ch_badge = f"[{_ch_label(app.channels)}]"
        dur_line = f"◉ {dur_str}  {ch_badge}" if dur_str else ch_badge
        if p_row < panel_bot:
            _safe(stdscr, p_row, px, dur_line[:PANEL_W], a_attr)
            p_row += 1

    elif app.now_playing and p_row < panel_bot:
        # No iTunes meta yet – show raw channel badge
        ch_badge = f"[{_ch_label(app.channels)}]"
        _safe(stdscr, p_row, px, ch_badge,
              curses.color_pair(12) if has_col else 0)

    # Download hint
    if p_row < panel_bot - 1:
        dl_hint = "D: download track"
        _safe(stdscr, panel_bot - 1, px,
              dl_hint[:PANEL_W], curses.color_pair(14) | curses.A_DIM if has_col else curses.A_DIM)

    # ── Now playing bar (bottom section) ─────────────────────────────────────
    np_y   = h - BOTTOM
    pb_y   = h - BOTTOM + 1
    vu_y   = h - BOTTOM + 2
    lyr_y  = h - BOTTOM + 3
    lyrn_y = h - BOTTOM + 4
    stat_y = h - 1

    if app.now_playing:
        np_attr  = curses.color_pair(3) | curses.A_BOLD if has_col else curses.A_BOLD
        paused   = " [PAUSED]" if app.player.is_paused() else ""
        ch_badge = f"  [{_ch_label(app.channels)}]"
        np_line  = f">> Now: {app.now_playing}{paused}{ch_badge}"
        _safe(stdscr, np_y, 0, np_line[:max(0, w - 1)], np_attr)

        pos = app.player.position_seconds()
        dur = app.player.duration_seconds()
        buf = app.player.buffered_seconds()

        l_str = _fmt(pos)
        r_str = _fmt(dur)
        ratio  = (pos / dur) if dur else 0.0
        brat   = ((pos + buf) / dur) if dur else None
        label  = f"{l_str} / {r_str}  buf:{buf:.1f}s "
        bw     = max(0, w - len(label) - 3)
        bar    = _pbar(bw, ratio, brat)
        _safe(stdscr, pb_y, 0,
              f"[{bar}] {label}"[:max(0, w - 1)],
              curses.color_pair(8) if has_col else 0)

        lvl_l, lvl_r = app.player.levels()
        mw = 8
        vu_attr = curses.color_pair(9) if has_col else 0
        _safe(stdscr, vu_y, 0,        f"L[{_mbar(mw, lvl_l)}]", vu_attr)
        _safe(stdscr, vu_y, w - mw - 4, f"R[{_mbar(mw, lvl_r)}]", vu_attr)

        if app.show_lyrics:
            lyr  = app._get_lyric()
            nlyr = app._get_next_lyric()
            ly_attr  = curses.color_pair(3) if has_col else 0
            lyd_attr = curses.A_DIM
            if lyr:
                _safe(stdscr, lyr_y, 0, f"  ♫  {lyr}"[:max(0, w - 1)], ly_attr)
            if nlyr:
                _safe(stdscr, lyrn_y, 0, f"     {nlyr}"[:max(0, w - 1)], lyd_attr)

    # ── Status bar ────────────────────────────────────────────────────────────
    stat = app.status
    sl   = app.status.lower()
    if has_col:
        if any(sl.startswith(x) for x in ("search failed", "playback", "seek failed", "✗")):
            sa = curses.color_pair(4) | curses.A_BOLD
        elif any(sl.startswith(x) for x in ("playing", "✓")):
            sa = curses.color_pair(7)
        elif "download" in sl or "⬇" in sl:
            sa = curses.color_pair(17)
        else:
            sa = 0
    else:
        sa = 0
    hint_r = "  D:dl  P:pause  S:stop  L:lyrics  Q:quit"
    stat_l = f"[*] {stat}"[:max(0, w - len(hint_r) - 1)]
    _safe(stdscr, stat_y, 0, stat_l, sa)
    _safe(stdscr, stat_y, max(0, w - len(hint_r) - 1), hint_r)

    # ── Cursor ────────────────────────────────────────────────────────────────
    try:
        curses.curs_set(1 if app.mode == "query" else 0)
    except Exception:
        pass
    if app.mode == "query":
        try:
            stdscr.move(1, bar_x + min(len(q), bar_w))
        except Exception:
            pass

    stdscr.refresh()


def _draw_help(stdscr, h: int, w: int) -> None:
    """Draw the centred help overlay."""
    lines = HELP_TEXT.split("\n")
    bh, bw = len(lines), max(len(l) for l in lines)
    sy = max(0, (h - bh) // 2)
    sx = max(0, (w - bw) // 2)
    stdscr.erase()
    bg_attr  = curses.color_pair(18) if curses.has_colors() else 0
    bdr_attr = curses.color_pair(19) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
    for i, line in enumerate(lines):
        y = sy + i
        if y >= h:
            break
        # First and last lines as border colour, rest as body
        attr = bdr_attr if i in (0, len(lines) - 1) else bg_attr
        _safe(stdscr, y, sx, line[:max(0, w - sx)], attr)


# ── Input handler ─────────────────────────────────────────────────────────────

def _handle(ch: int, app: App) -> bool:
    """Return False to quit."""
    if ch in (-1, 0):
        return True

    # Dismiss help overlay with any key
    if app.show_help:
        app.show_help = False
        return True

    # Quit (always)
    if ch in (ord("q"), ord("Q")):
        return False

    # Esc → go to query mode
    if ch == 27:
        app.mode = "query"
        app.suggestion_idx = -1
        return True

    # '/' → help overlay, but ONLY when NOT in query mode (avoids blocking search input)
    if ch == ord("/") and app.mode == "results":
        app.show_help = True
        return True

    # Tab → cycle suggestions (query mode only)
    if ch == 9 and app.mode == "query":
        app.tab_suggestion()
        return True

    # ── QUERY MODE ────────────────────────────────────────────────────────────
    if app.mode == "query":
        if ch in (curses.KEY_ENTER, 10, 13):
            app.start_search()
            return True
        if ch in (curses.KEY_UP, curses.KEY_DOWN) and app.results:
            app.mode = "results"
            return True
        if ch in (curses.KEY_BACKSPACE, 8, 127, curses.KEY_DC):
            app.query = app.query[:-1]
            app.suggestion_idx = -1
            return True
        if ch == 21:   # Ctrl+U
            app.query = ""
            app.suggestions = []
            app.suggestion_idx = -1
            return True
        if 32 <= ch <= 126:
            app.query += chr(ch)
            app.suggestion_idx = -1
            return True
        return True

    # ── RESULTS MODE ──────────────────────────────────────────────────────────
    if ch == curses.KEY_UP:
        app.selected = max(0, app.selected - 1)
        return True
    if ch == curses.KEY_DOWN:
        app.selected = min(len(app.results) - 1, app.selected + 1)
        return True

    if ch in (ord("s"), ord("S")):
        app.player.stop()
        app.now_playing = ""
        app._play_gen  += 1
        app.status      = "Stopped."
        app.art.clear()
        app.current_meta = None
        return True

    if ch in (ord("p"), ord("P"), ord(" ")):
        app.player.toggle_pause()
        app.status = "Paused." if app.player.is_paused() else "Playing."
        return True

    if ch in (ord("l"), ord("L")):
        app.show_lyrics = not app.show_lyrics
        app.status = "Lyrics: ON" if app.show_lyrics else "Lyrics: OFF"
        return True

    if ch in (ord("d"), ord("D")):
        app.start_download()
        return True

    # Seeking
    if app.now_playing and app.player.duration_seconds() and app._f_seek is None:
        seeks = {
            curses.KEY_LEFT:  -5.0,  curses.KEY_RIGHT: +5.0,
            ord("["):         -10.0, ord("]"):          +10.0,
            curses.KEY_PPAGE: -30.0, curses.KEY_NPAGE:  +30.0,
        }
        if ch in seeks:
            app.status  = "Seeking…"
            app._f_seek = app._ex.submit(app.player.seek_relative, seeks[ch])
            return True
        if ch == curses.KEY_HOME:
            app._f_seek = app._ex.submit(app.player.seek_to, 0.0)
            return True
        if ch == curses.KEY_END:
            app._f_seek = app._ex.submit(
                app.player.seek_to, float(app.player.duration_seconds() or 0))
            return True

    # Paging (when not seeking)
    if app.results:
        page = max(1, app._last_max_rows)
        if ch == curses.KEY_PPAGE:
            app.selected = max(0, app.selected - page)
            return True
        if ch == curses.KEY_NPAGE:
            app.selected = min(len(app.results) - 1, app.selected + page)
            return True
        if ch == curses.KEY_HOME:
            app.selected = 0
            return True
        if ch == curses.KEY_END:
            app.selected = len(app.results) - 1
            return True

    if ch in (curses.KEY_ENTER, 10, 13):
        app.start_play()
        return True

    # Start typing → switch to query mode
    if 32 <= ch <= 126:
        app.mode   = "query"
        app.query += chr(ch)
        return True

    return True


# ── Main loop ─────────────────────────────────────────────────────────────────

def main(stdscr) -> None:
    _init_colors()
    try:
        curses.curs_set(1)
    except Exception:
        pass

    stdscr.nodelay(True)
    stdscr.keypad(True)

    app = App()
    # Detect 256-color support
    app._art_256 = HAS_PIL and curses.has_colors() and curses.COLORS >= 256

    try:
        while True:
            app.poll()
            _draw(stdscr, app)
            ch = stdscr.getch()
            if not _handle(ch, app):
                break
            time.sleep(0.03)
    finally:
        app.close()


def cli() -> None:
    curses.wrapper(main)


if __name__ == "__main__":
    cli()
