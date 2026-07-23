from __future__ import annotations

import curses
import os
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import List, Optional, Tuple

from ttube_stream import StreamPlayer
from ttube_youtube import (
    AudioStream, SearchResult,
    resolve_best_audio_stream, search_youtube,
    fetch_lyrics, Lyrics,
)


def _setup_windows_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32   = ctypes.windll.user32
        kernel32.SetConsoleTitleW("TTube")
        base     = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base, "ttube.ico")
        if os.path.exists(ico_path):
            hsmall = user32.LoadImageW(None, ico_path, 1, 16, 16, 0x10)
            hbig   = user32.LoadImageW(None, ico_path, 1, 32, 32, 0x10)
            hwnd   = kernel32.GetConsoleWindow()
            if hwnd:
                if hsmall: user32.SendMessageW(hwnd, 0x0080, 0, hsmall)
                if hbig:   user32.SendMessageW(hwnd, 0x0080, 1, hbig)
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 3) # SW_MAXIMIZE
    except Exception:
        pass


# ── UI constants ──────────────────────────────────────────────────────────────
HELP_LINES = [
    "  Navigation    ↑ ↓  Move result     Tab  Toggle focus     Esc  Back to search",
    "  Playback      Enter  Play           P  Pause/Resume      S  Stop",
    "  Seek          ← →  ±5s    [ ]  ±10s    PgUp/Dn  ±30s    Home/End",
    "  In search     ← →  Cursor    Ctrl+A  Select all    Ctrl+U  Clear",
    "  Display       L  Lyrics     C  Captions    ?  Hide help    Q  Quit",
]
SPINNER  = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
MIN_COLS = 60
MIN_ROWS = 12

_PROG_FULL  = "█"
_PROG_BUF   = "▓"
_PROG_EMPTY = "░"
_DIV_H      = "─"

# Spectrum visualizer: 8-bar stereo display using vertical block chars
_VU_CHARS   = " ▁▂▃▄▅▆▇█"

CP_LOGO      = 1
CP_SELECT    = 2
CP_PLAYING   = 3
CP_ERROR     = 4
CP_RESULTS_H = 5
CP_SEARCH    = 6
CP_STATUS_OK = 7
CP_PROGRESS  = 8
CP_VU_LOW    = 9    # green
CP_DIM       = 10
CP_LYRIC_CUR = 11
CP_LYRIC_NXT = 12
CP_ACCENT    = 13
CP_HELP_BG   = 14
CP_VU_MID    = 15   # yellow
CP_VU_HI     = 16   # red


def _safe_addstr(stdscr, y: int, x: int, s: str, attr: int = 0) -> None:
    try:
        stdscr.addstr(y, x, s, attr)
    except curses.error:
        pass


def _init_colors() -> None:
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
    except Exception:
        pass
    bg = -1
    curses.init_pair(CP_LOGO,      curses.COLOR_CYAN,    bg)
    curses.init_pair(CP_SELECT,    curses.COLOR_BLACK,   curses.COLOR_CYAN)
    curses.init_pair(CP_PLAYING,   curses.COLOR_GREEN,   bg)
    curses.init_pair(CP_ERROR,     curses.COLOR_RED,     bg)
    curses.init_pair(CP_RESULTS_H, curses.COLOR_CYAN,    bg)
    curses.init_pair(CP_SEARCH,    curses.COLOR_MAGENTA, bg)
    curses.init_pair(CP_STATUS_OK, curses.COLOR_GREEN,   bg)
    curses.init_pair(CP_PROGRESS,  curses.COLOR_CYAN,    bg)
    curses.init_pair(CP_VU_LOW,    curses.COLOR_GREEN,   bg)
    curses.init_pair(CP_DIM,       curses.COLOR_WHITE,   bg)
    curses.init_pair(CP_LYRIC_CUR, curses.COLOR_WHITE,   bg)
    curses.init_pair(CP_LYRIC_NXT, curses.COLOR_CYAN,    bg)
    curses.init_pair(CP_ACCENT,    curses.COLOR_MAGENTA, bg)
    curses.init_pair(CP_HELP_BG,   curses.COLOR_BLACK,   curses.COLOR_CYAN)
    if curses.COLORS >= 256:
        curses.init_pair(CP_VU_MID, curses.COLOR_YELLOW, bg)
        curses.init_pair(CP_VU_HI,  curses.COLOR_RED,    bg)
    else:
        curses.init_pair(CP_VU_MID, curses.COLOR_YELLOW, bg)
        curses.init_pair(CP_VU_HI,  curses.COLOR_RED,    bg)


def _attr(pair: int, bold: bool = False, dim: bool = False) -> int:
    if not curses.has_colors():
        return curses.A_BOLD if bold else (curses.A_DIM if dim else 0)
    a = curses.color_pair(pair)
    if bold: a |= curses.A_BOLD
    if dim:  a |= curses.A_DIM
    return a


def _draw_hline(stdscr, y: int, x: int, width: int, attr: int = 0) -> None:
    _safe_addstr(stdscr, y, x, _DIV_H * width, attr)


def _wrap(text: str, width: int) -> List[str]:
    if width <= 0:
        return [text] if text else [""]
    words, out, cur = text.split(), [], ""
    for word in words:
        if len(cur) + len(word) + (1 if cur else 0) <= width:
            cur += (" " if cur else "") + word
        else:
            if cur: out.append(cur)
            cur = word
    if cur: out.append(cur)
    return out or [""]


# ── Spectrum visualizer ───────────────────────────────────────────────────────
# Simulate a multi-band spectrum by splitting the two level values into N fake
# frequency bins with a smooth falloff — purely cosmetic but looks great.
_SPEC_BINS  = 12   # bars per channel
_spec_state : List[float] = [0.0] * (_SPEC_BINS * 2)   # persists across frames


def _update_spectrum(lvl_l: float, lvl_r: float) -> None:
    """Map stereo peak levels to a fake N-band spectrum with decay."""
    bins = _SPEC_BINS
    decay = 0.82
    # Create a rough "spectrum shape": more energy in mid-lows, taper at highs
    shape = [1.0, 0.95, 0.92, 0.88, 0.80, 0.70, 0.58, 0.46, 0.34, 0.22, 0.12, 0.05]

    for i in range(bins):
        target_l = lvl_l * shape[i] * (0.85 + 0.30 * (i % 3 == 1))
        target_r = lvl_r * shape[i] * (0.85 + 0.30 * (i % 3 == 2))
        _spec_state[i]        = max(target_l, _spec_state[i]        * decay)
        _spec_state[bins + i] = max(target_r, _spec_state[bins + i] * decay)


def _draw_spectrum(stdscr, y: int, x: int, width: int) -> None:
    """Draw a clean stereo spectrum visualizer on a single row."""
    bins  = _SPEC_BINS
    # Each bar is 1 char wide; channels separated by a gap
    # Layout: [L bars] [gap] [R bars]
    if width < bins * 2 + 3:
        return

    gap   = 3
    bar_w = (width - gap) // 2
    bar_w = min(bar_w, bins)

    for side in range(2):
        offset = side * (bar_w + gap)
        for i in range(bar_w):
            bin_i  = (bar_w - 1 - i) if side == 0 else i   # L mirror, R normal
            level  = _spec_state[(side * bins) + (bin_i % bins)]
            ci     = int(level * (len(_VU_CHARS) - 1))
            ci     = max(0, min(ci, len(_VU_CHARS) - 1))
            ch     = _VU_CHARS[ci]

            # Color: green < 60%, yellow < 85%, red above
            if level < 0.60:
                attr = _attr(CP_VU_LOW)
            elif level < 0.85:
                attr = _attr(CP_VU_MID, bold=True)
            else:
                attr = _attr(CP_VU_HI, bold=True)

            _safe_addstr(stdscr, y, x + offset + i, ch, attr)

    # Center separator
    sep_x = x + bar_w + 1
    _safe_addstr(stdscr, y, sep_x, "│", _attr(CP_DIM, dim=True))


# ── App state ─────────────────────────────────────────────────────────────────
class App:
    def __init__(self):
        self.query:    str  = ""
        self.q_cursor: int  = 0      # cursor position within query string
        self.results: List[SearchResult] = []
        self.selected: int = 0
        self._last_max_rows: int = 10

        self.status:      str = "Type a search query and press Enter."
        self.now_playing: str = ""
        self.mode:        str = "query"  # query | results | captions

        self._executor = ThreadPoolExecutor(max_workers=3)
        self._pending_search: Optional[Future] = None
        self._pending_play:   Optional[Future] = None
        self._pending_seek:   Optional[Future] = None
        self._pending_lyrics: Optional[Future] = None

        self._play_generation: int = 0

        self.lyrics:              Optional[Lyrics] = None
        self.current_lyric_index: int  = 0
        self.show_lyrics:         bool = True
        self._current_url:        str  = ""



        self.show_help: bool = False

        self.player = StreamPlayer()

    def busy_label(self) -> str:
        if self._pending_play   is not None: return "Resolving"
        if self._pending_search is not None: return "Searching"
        if self._pending_seek   is not None: return "Seeking"
        return ""

    def close(self) -> None:
        try:    self.player.stop()
        finally: self._executor.shutdown(wait=False, cancel_futures=True)

    # ── actions ─────────────────────────────────────────────────────────────
    def start_search(self) -> None:
        q = self.query.strip()
        if not q:
            self.status = "Enter a search query first."
            return
        self.status = "Searching…"
        self._pending_search = self._executor.submit(search_youtube, q, 10)

    def start_play_selected(self) -> None:
        if not self.results:
            self.status = "No results to play."
            return
        idx  = max(0, min(self.selected, len(self.results) - 1))
        item = self.results[idx]
        self.status       = "Resolving stream…"
        self.now_playing  = item.title
        self.lyrics       = None
        self.current_lyric_index = 0
        self.show_lyrics  = True
        self._current_url = item.webpage_url


        self._play_generation += 1
        play_gen    = self._play_generation
        webpage_url = item.webpage_url

        def _do_play():
            stream = resolve_best_audio_stream(webpage_url)
            if play_gen != self._play_generation:
                return (stream, None)
            self.player.play(stream.stream_url,
                             http_headers=stream.http_headers,
                             duration_seconds=stream.duration_seconds)
            return (stream, None)

        self._pending_play = self._executor.submit(_do_play)

        # Lyrics fetch
        def _do_lyrics():
            return fetch_lyrics(item.title)

        self._pending_lyrics    = self._executor.submit(_do_lyrics)



    # ── polling ──────────────────────────────────────────────────────────────
    def poll_background_tasks(self) -> None:
        if self._pending_search is not None and self._pending_search.done():
            try:
                self.results  = self._pending_search.result()
                self.selected = 0
                self.mode     = "results" if self.results else "query"
                self.status   = f"Found {len(self.results)} result(s)."
            except Exception as e:
                self.status = f"Search failed: {e}"
            finally:
                self._pending_search = None

        if self._pending_play is not None and self._pending_play.done():
            try:
                stream, _ = self._pending_play.result()
                self.now_playing = stream.title
                self.status      = "Playing."
            except Exception as e:
                self.status = f"Playback failed: {e}"
            finally:
                self._pending_play = None

        if self._pending_seek is not None and self._pending_seek.done():
            try:
                self._pending_seek.result()
                self.status = "Seeked."
            except Exception as e:
                self.status = f"Seek failed: {e}"
            finally:
                self._pending_seek = None

        if self._pending_lyrics is not None and self._pending_lyrics.done():
            try:
                self.lyrics = self._pending_lyrics.result()
                self.current_lyric_index = 0
                self.status = "Lyrics loaded." if self.lyrics else "No lyrics found."
            except Exception as e:
                self.lyrics = None
                self.status = f"Lyrics error: {e}"
            finally:
                self._pending_lyrics = None



    # ── lyrics helpers ───────────────────────────────────────────────────────
    def get_current_lyric(self) -> str | None:
        if not self.lyrics or not self.lyrics.lines:
            return None
        pos = self.player.position_seconds()
        if pos is None:
            return None
        for i, line in enumerate(self.lyrics.lines):
            if line.start_time <= pos < line.end_time:
                self.current_lyric_index = i
                return line.text
            if pos < line.start_time:
                break
        return None

    def get_next_lyric(self) -> str | None:
        if not self.lyrics or not self.lyrics.lines:
            return None
        idx = self.current_lyric_index + 1
        return self.lyrics.lines[idx].text if idx < len(self.lyrics.lines) else None


# ── Formatting ────────────────────────────────────────────────────────────────
def _format_time(seconds: float | None) -> str:
    if seconds is None: return "--:--"
    if seconds < 0:     seconds = 0
    t = int(seconds); h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _progress_bar(width: int, played: float, buffered: float | None = None) -> str:
    width = max(0, int(width))
    if not width: return ""
    pr = min(1.0, max(0.0, played))
    br = max(pr, pr if buffered is None else min(1.0, max(0.0, buffered)))
    p  = min(width, int(round(pr * width)))
    b  = min(width, max(p, int(round(br * width))))
    return _PROG_FULL * p + _PROG_BUF * (b - p) + _PROG_EMPTY * (width - b)


def _capitalize_english(text: str) -> str:
    asc = sum(1 for c in text if c.isascii() and c.isalpha())
    tot = sum(1 for c in text if c.isalpha())
    return text.title() if tot and asc / tot > 0.8 else text


# ── Drawing ───────────────────────────────────────────────────────────────────
def _draw(stdscr, app: App) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    if h < MIN_ROWS or w < MIN_COLS:
        _safe_addstr(stdscr, 0, 0, "TTube", _attr(CP_LOGO, bold=True))
        _safe_addstr(stdscr, 2, 0,
                     f"Resize to {MIN_COLS}x{MIN_ROWS} (now {w}x{h})"[:w - 1],
                     _attr(CP_ERROR, bold=True))
        stdscr.refresh()
        return

    is_busy   = bool(app.busy_label())
    spin_char = SPINNER[int(time.time() * 10) % len(SPINNER)] if is_busy else " "

    # ── Row 0: minimal wordmark + badge ──────────────────────────────────────
    wordmark      = "T T u b e"
    wordmark_attr = _attr(CP_LOGO, bold=True)

    if is_busy:
        badge = f"  {spin_char} {app.busy_label()}  "
        badge_attr = _attr(CP_ACCENT, bold=True)
    elif app.mode == "query":
        badge = "  SEARCH  "
        badge_attr = _attr(CP_SEARCH, bold=True)
    else:
        badge = "  RESULTS  "
        badge_attr = _attr(CP_RESULTS_H, bold=True)

    _safe_addstr(stdscr, 0, 2, wordmark, wordmark_attr)
    _safe_addstr(stdscr, 0, max(len(wordmark) + 4, w - len(badge) - 1),
                 badge[:w - 1], badge_attr)

    # Row 1: thin divider
    _draw_hline(stdscr, 1, 0, w - 1, _attr(CP_DIM, dim=True))

    # ── Row 2: Search bar ────────────────────────────────────────────────────
    search_y = 2
    dot      = "●" if app.mode == "query" else "○"
    lbl      = f" {dot} Search: "
    _safe_addstr(stdscr, search_y, 0, lbl, _attr(CP_SEARCH, bold=True))
    bar_x    = len(lbl)
    bar_w    = max(0, w - bar_x - 1)
    q        = app.query
    q_attr   = _attr(CP_SELECT) if app.mode == "query" else 0
    _safe_addstr(stdscr, search_y, bar_x,
                 (q + " " * max(0, bar_w - len(q)))[:bar_w], q_attr)

    # Row 3: divider + results header
    _draw_hline(stdscr, 3, 0, w - 1, _attr(CP_DIM, dim=True))

    results_y = 4
    dot_r     = "●" if app.mode == "results" else "○"
    count     = str(len(app.results)) if app.results else "—"
    rh_str    = f" {dot_r} Results [{count}]"
    _safe_addstr(stdscr, results_y, 0, rh_str[:w - 1], _attr(CP_RESULTS_H, bold=True))
    if app.results:
        si = f"[{app.selected + 1}/{len(app.results)}]"
        _safe_addstr(stdscr, results_y, max(0, w - len(si) - 1), si, _attr(CP_DIM, dim=True))

    # ── Result list area ─────────────────────────────────────────────────────
    list_top = 5
    reserved = 6 if app.now_playing else 2   # player bar rows
    max_rows = max(0, h - list_top - reserved)
    app._last_max_rows = max_rows

    lyrics_visible = (
        app.show_lyrics and app.now_playing
        and app.lyrics is not None and bool(app.lyrics.lines)
    )
    
    panel_visible = bool(app.now_playing)

    RESULTS_COL_W = 52

    if panel_visible:
        results_left = 0
        lyr_x        = RESULTS_COL_W + 2
        lyr_w        = max(0, w - lyr_x - 1)
    else:
        results_left = max(0, (w - RESULTS_COL_W) // 2)
        lyr_x = lyr_w = 0

    # Draw rows
    if app.results and max_rows > 0:
        start = 0
        if app.selected >= max_rows:
            start = app.selected - max_rows + 1
        for i, r in enumerate(app.results[start : start + max_rows]):
            y       = list_top + i
            abs_idx = start + i
            if abs_idx == app.selected:
                line = (" ▶  " + r.title)[:RESULTS_COL_W - 1].ljust(RESULTS_COL_W - 1)
                attr = _attr(CP_SELECT)
            else:
                line = ("    " + r.title)[:RESULTS_COL_W - 1]
                attr = 0
            _safe_addstr(stdscr, y, results_left, line, attr)

        if len(app.results) > max_rows:
            sb_x      = results_left + RESULTS_COL_W
            thumb_pos = int((app.selected / max(1, len(app.results) - 1)) * (max_rows - 1))
            for ri in range(max_rows):
                _safe_addstr(stdscr, list_top + ri, sb_x,
                             "█" if ri == thumb_pos else "░",
                             _attr(CP_DIM, dim=True))

    # ── Audio Spectrum or Lyrics panel ───────────────────────────────────────
    if panel_visible and lyr_w > 10:
        if lyrics_visible:
            lyr_hdr   = "♪ Lyrics"
            lyr_hdr_x = lyr_x + max(0, (lyr_w - len(lyr_hdr)) // 2)
            _safe_addstr(stdscr, results_y, lyr_hdr_x, lyr_hdr, _attr(CP_ACCENT, bold=True))

            cur_lyric  = app.get_current_lyric()
            next_lyric = app.get_next_lyric()

            progress = 0.0
            if cur_lyric and app.lyrics:
                lo   = app.lyrics.lines[app.current_lyric_index]
                span = lo.end_time - lo.start_time
                if span > 0:
                    pos_now  = app.player.position_seconds() or 0
                    progress = max(0.0, min(1.0, (pos_now - lo.start_time) / span))

            anim_chars = ["▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
            anim_char  = anim_chars[min(len(anim_chars) - 1, int(progress * len(anim_chars)))]

            lyric_rows = list(range(list_top, list_top + max_rows))
            row_ptr = max(0, (len(lyric_rows) - 6) // 2)

            if cur_lyric:
                lines_cur = _wrap(_capitalize_english(cur_lyric), lyr_w - 3)
                cur_attr  = _attr(CP_LYRIC_CUR, bold=True)
                for li, lline in enumerate(lines_cur):
                    if row_ptr >= len(lyric_rows): break
                    pfx  = anim_char if li == 0 else " "
                    body = f"{pfx} {lline}"
                    cx   = lyr_x + max(0, (lyr_w - len(body)) // 2)
                    _safe_addstr(stdscr, lyric_rows[row_ptr], cx, body[:lyr_w], cur_attr)
                    row_ptr += 1

            row_ptr += 1   # gap line
            if next_lyric and row_ptr < len(lyric_rows):
                lines_nxt = _wrap(_capitalize_english(next_lyric), lyr_w - 4)
                nxt_attr  = _attr(CP_LYRIC_NXT, dim=True)
                for lline in lines_nxt:
                    if row_ptr >= len(lyric_rows): break
                    cx = lyr_x + max(0, (lyr_w - len(lline)) // 2)
                    _safe_addstr(stdscr, lyric_rows[row_ptr], cx, lline[:lyr_w], nxt_attr)
                    row_ptr += 1
        else:
            # Draw empty state instead of Lyrics
            no_lyr_msg = "(No lyrics available)"
            no_lyr_x = lyr_x + max(0, (lyr_w - len(no_lyr_msg)) // 2)
            _safe_addstr(stdscr, results_y + max_rows // 2, no_lyr_x, no_lyr_msg, _attr(CP_DIM, dim=True))

    # ── Help overlay ─────────────────────────────────────────────────────────
    if app.show_help:
        _draw_help(stdscr, h, w)

    # ── Player bar ───────────────────────────────────────────────────────────
    if app.now_playing:
        np_y = h - reserved
        if np_y > 0:
            _draw_hline(stdscr, np_y - 1, 0, w - 1, _attr(CP_DIM, dim=True))

        paused_tag = "  ⏸ PAUSED" if app.player.is_paused() else ""
        _safe_addstr(stdscr, np_y, 0,
                     f" ♪  {app.now_playing}{paused_tag}"[:w - 1],
                     _attr(CP_PLAYING, bold=True))

        pos       = app.player.position_seconds()
        dur       = app.player.duration_seconds()
        buf       = app.player.buffered_seconds()
        t_pos     = _format_time(pos)
        t_dur     = _format_time(dur)
        ratio     = (pos / dur) if (dur and dur > 0 and pos is not None) else 0.0
        buf_ratio = ((pos + buf) / dur) if (dur and dur > 0 and pos is not None) else None
        t_l, t_r  = f" {t_pos} ", f" {t_dur} "
        bar_w2    = max(0, w - len(t_l) - len(t_r) - 2)
        prog_line = f"{t_l}[{_progress_bar(bar_w2, ratio, buf_ratio)}]{t_r}"
        _safe_addstr(stdscr, np_y + 1, 0, prog_line[:w - 1], _attr(CP_PROGRESS, bold=True))

        # Spectrum visualizer
        lvl_l, lvl_r = app.player.levels()
        _update_spectrum(lvl_l, lvl_r)
        _draw_spectrum(stdscr, np_y + 2, 2, w - 4)

    # ── Status bar ───────────────────────────────────────────────────────────
    status_y = h - 1
    if status_y >= 0:
        s = app.status.lower()
        if any(s.startswith(x) for x in ("search failed", "playback failed", "seek failed")):
            st_attr = _attr(CP_ERROR, bold=True)
        elif s.startswith("playing"):
            st_attr = _attr(CP_STATUS_OK, bold=True)
        elif any(s.startswith(x) for x in ("searching", "resolving", "loading")):
            st_attr = _attr(CP_ACCENT, bold=True)
        else:
            st_attr = _attr(CP_DIM, dim=True)

        hint   = "  (?) Help"
        hint_x = max(0, w - len(hint) - 1)
        _safe_addstr(stdscr, status_y, 0, " " * (w - 1), _attr(CP_DIM, dim=True))
        _safe_addstr(stdscr, status_y, 0,
                     f" ● {app.status}"[:max(0, hint_x - 1)], st_attr)
        _safe_addstr(stdscr, status_y, hint_x, hint, _attr(CP_ACCENT))

    # ── Cursor ───────────────────────────────────────────────────────────────
    try:
        curses.curs_set(1 if app.mode == "query" else 0)
    except Exception:
        pass

    if app.mode == "query":
        bx = len(f" {'●'} Search: ")
        # Show cursor at query cursor position
        cur_screen_x = bx + min(app.q_cursor, max(0, bar_w - 1))
        try:
            stdscr.move(search_y, cur_screen_x)
        except Exception:
            pass

    stdscr.refresh()


def _draw_help(stdscr, h: int, w: int) -> None:
    box_w = min(w - 4, 74)
    box_h = len(HELP_LINES) + 4
    box_x = max(0, (w - box_w) // 2)
    box_y = max(0, (h - box_h) // 2)
    bg    = _attr(CP_HELP_BG)
    bold  = _attr(CP_HELP_BG) | curses.A_BOLD

    _safe_addstr(stdscr, box_y, box_x, ("┌" + "─" * (box_w - 2) + "┐")[:w - box_x], bg)
    title = " Keyboard Shortcuts "
    _safe_addstr(stdscr, box_y, box_x + max(0, (box_w - len(title)) // 2), title, bold)
    for i, line in enumerate(HELP_LINES):
        y = box_y + 1 + i
        if y >= h: break
        _safe_addstr(stdscr, y, box_x, ("│" + line.ljust(box_w - 2)[:box_w - 2] + "│")[:w - box_x], bg)
    sep_y = box_y + 1 + len(HELP_LINES)
    if sep_y < h:
        _safe_addstr(stdscr, sep_y, box_x, ("├" + "─" * (box_w - 2) + "┤")[:w - box_x], bg)
    close_y = sep_y + 1
    if close_y < h:
        _safe_addstr(stdscr, close_y, box_x,
                     ("│" + "  Press ? to close  ".center(box_w - 2) + "│")[:w - box_x], bold)
    bot_y = close_y + 1
    if bot_y < h:
        _safe_addstr(stdscr, bot_y, box_x, ("└" + "─" * (box_w - 2) + "┘")[:w - box_x], bg)


def _draw_caption_picker(stdscr, app: App, h: int, w: int) -> None:
    tracks = app.caption_tracks
    if not tracks: return
    box_w = min(w - 4, 50)
    box_h = len(tracks) + 4
    box_x = max(0, (w - box_w) // 2)
    box_y = max(0, (h - box_h) // 2)
    bg    = _attr(CP_HELP_BG)
    sel   = _attr(CP_SELECT)
    dim   = _attr(CP_DIM, dim=True)

    _safe_addstr(stdscr, box_y, box_x, ("┌" + "─" * (box_w - 2) + "┐")[:w - box_x], bg)
    title = " Choose Caption Track "
    _safe_addstr(stdscr, box_y, box_x + max(0, (box_w - len(title)) // 2), title, bg | curses.A_BOLD)
    for i, track in enumerate(tracks):
        y     = box_y + 1 + i
        if y >= h: break
        label = track.get("label") or track.get("lang", "?")
        row   = ("│" + f"  {label}  ".ljust(box_w - 2)[:box_w - 2] + "│")[:w - box_x]
        _safe_addstr(stdscr, y, box_x, row, sel if i == app.caption_sel else bg)
    sep_y = box_y + 1 + len(tracks)
    if sep_y < h:
        _safe_addstr(stdscr, sep_y, box_x, ("├" + "─" * (box_w - 2) + "┤")[:w - box_x], bg)
    hint_y = sep_y + 1
    if hint_y < h:
        _safe_addstr(stdscr, hint_y, box_x,
                     ("│" + "  ↑↓ Navigate   Enter Select   Esc Cancel  ".center(box_w - 2)[:box_w - 2] + "│")[:w - box_x], dim)
    bot_y = hint_y + 1
    if bot_y < h:
        _safe_addstr(stdscr, bot_y, box_x, ("└" + "─" * (box_w - 2) + "┘")[:w - box_x], bg)


# ── Input ─────────────────────────────────────────────────────────────────────
def _handle_input(ch: int, app: App) -> bool:
    if ch in (-1, 0): return True

    # Help toggle always intercepts ?
    if ch == ord("?"):
        app.show_help = not app.show_help
        return True

    # Any key dismisses help overlay
    if app.show_help:
        app.show_help = False
        return True

    # Global quit
    if ch in (ord("q"), ord("Q")) and app.mode not in ("captions",):
        return False

    # ── Caption picker ───────────────────────────────────────────────────────
    if app.mode == "captions":
        if ch in (27, ord("c"), ord("C")):
            app.mode = "results"
        elif ch == curses.KEY_UP:
            app.caption_sel = max(0, app.caption_sel - 1)
        elif ch == curses.KEY_DOWN:
            app.caption_sel = min(len(app.caption_tracks) - 1, app.caption_sel + 1)
        elif ch in (curses.KEY_ENTER, 10, 13):
            app.fetch_lyrics_for_track(app.caption_sel)
            app.mode = "results"
        return True

    # ── Global ───────────────────────────────────────────────────────────────
    if ch == 27:   # Esc
        app.mode = "query"
        return True
    if ch == ord("/") and app.mode == "results":
        app.mode = "query"
        return True
    if ch == 9:    # Tab
        app.mode = "results" if (app.mode == "query" and app.results) else "query"
        return True

    # ── QUERY mode ───────────────────────────────────────────────────────────
    if app.mode == "query":
        if ch in (curses.KEY_ENTER, 10, 13):
            app.start_search()
            return True

        # Allow ↑↓ to switch to results without losing query
        if ch == curses.KEY_UP and app.results:
            app.mode = "results"
            return True
        if ch == curses.KEY_DOWN and app.results:
            app.mode = "results"
            return True

        # Cursor movement in search bar
        if ch == curses.KEY_LEFT:
            app.q_cursor = max(0, app.q_cursor - 1)
            return True
        if ch == curses.KEY_RIGHT:
            app.q_cursor = min(len(app.query), app.q_cursor + 1)
            return True
        if ch == curses.KEY_HOME:
            app.q_cursor = 0
            return True
        if ch == curses.KEY_END:
            app.q_cursor = len(app.query)
            return True

        # Ctrl+A — move cursor to start (select all semantics in TUI)
        if ch == 1:
            app.q_cursor = 0
            return True

        # Backspace / Delete
        if ch in (curses.KEY_BACKSPACE, 8, 127):
            if app.q_cursor > 0:
                app.query    = app.query[:app.q_cursor - 1] + app.query[app.q_cursor:]
                app.q_cursor -= 1
            return True
        if ch == curses.KEY_DC:
            if app.q_cursor < len(app.query):
                app.query = app.query[:app.q_cursor] + app.query[app.q_cursor + 1:]
            return True

        # Ctrl+U — clear line
        if ch == 21:
            app.query    = ""
            app.q_cursor = 0
            return True

        # Printable chars: insert at cursor
        if 32 <= ch <= 126:
            app.query    = app.query[:app.q_cursor] + chr(ch) + app.query[app.q_cursor:]
            app.q_cursor += 1
            return True

        return True

    # ── RESULTS mode ─────────────────────────────────────────────────────────
    if ch == curses.KEY_UP:
        app.selected = max(0, app.selected - 1)
        return True
    if ch == curses.KEY_DOWN:
        app.selected = min(len(app.results) - 1, app.selected + 1)
        return True

    if ch in (ord("s"), ord("S")):
        app.player.stop()
        app.now_playing = ""
        app.show_lyrics = False
        app._play_generation += 1
        for fut in (app._pending_play, app._pending_seek):
            if fut:
                try: fut.cancel()
                except Exception: pass
        app._pending_play = app._pending_seek = None
        app.status = "Stopped."
        return True

    if ch in (ord("p"), ord("P"), ord(" ")):
        app.player.toggle_pause()
        app.status = "Paused." if app.player.is_paused() else "Playing."
        return True

    if ch in (ord("l"), ord("L")):
        app.show_lyrics = not app.show_lyrics
        if app.show_lyrics:
            if app.now_playing and not app.lyrics:
                app.status = "Lyrics: ON. Fetching..."
                def _do_lyrics():
                    return fetch_lyrics(app.now_playing)
                app._pending_lyrics = app._executor.submit(_do_lyrics)
            else:
                app.status = "Lyrics: ON"
        else:
            app.status = "Lyrics: OFF"
        return True

    # Seeking
    if app.now_playing and app.player.duration_seconds() is not None and app._pending_seek is None:
        seek_map = {
            curses.KEY_LEFT:  -5.0,  curses.KEY_RIGHT: +5.0,
            ord("["):         -10.0, ord("]"):          +10.0,
            curses.KEY_PPAGE: -30.0, curses.KEY_NPAGE:  +30.0,
        }
        if ch in seek_map:
            app.status = "Seeking…"
            app._pending_seek = app._executor.submit(app.player.seek_relative, seek_map[ch])
            return True
        if ch == curses.KEY_HOME:
            app.status = "Seeking…"
            app._pending_seek = app._executor.submit(app.player.seek_to, 0.0)
            return True
        if ch == curses.KEY_END:
            dur = float(app.player.duration_seconds() or 0.0)
            app.status = "Seeking…"
            app._pending_seek = app._executor.submit(app.player.seek_to, dur)
            return True

    # Result paging
    if app.results:
        page = max(1, app._last_max_rows)
        if ch == curses.KEY_PPAGE:
            app.selected = max(0, app.selected - page); return True
        if ch == curses.KEY_NPAGE:
            app.selected = min(len(app.results) - 1, app.selected + page); return True
        if ch == curses.KEY_HOME:
            app.selected = 0; return True
        if ch == curses.KEY_END:
            app.selected = len(app.results) - 1; return True

    if ch in (curses.KEY_ENTER, 10, 13):
        app.start_play_selected()
        return True

    # Start typing → drop back to search
    if 32 <= ch <= 126:
        app.mode     = "query"
        app.query    = app.query[:app.q_cursor] + chr(ch) + app.query[app.q_cursor:]
        app.q_cursor += 1
        return True

    return True


# ── Entry point ───────────────────────────────────────────────────────────────
def main(stdscr) -> None:
    _init_colors()

    # Release mouse so the window decorations keep working (force Windows Terminal)
    try:
        import sys
        sys.stdout.write("\x1b[?1000l\x1b[?1002l\x1b[?1015l\x1b[?1006l")
        sys.stdout.flush()
        curses.mousemask(0)
    except Exception:
        pass

    try:
        curses.curs_set(1)
    except Exception:
        pass

    stdscr.nodelay(True)
    stdscr.keypad(True)

    app = App()
    try:
        while True:
            app.poll_background_tasks()
            _draw(stdscr, app)
            ch = stdscr.getch()
            if not _handle_input(ch, app):
                break
            time.sleep(0.03)
    finally:
        app.close()


def cli() -> None:
    """Console entrypoint installed by pip."""
    curses.wrapper(main)


if __name__ == "__main__":
    cli()
