from __future__ import annotations

import curses
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import List, Optional, Tuple

from ttube_stream import StreamPlayer
from ttube_youtube import AudioStream, SearchResult, resolve_best_audio_stream, search_youtube, fetch_lyrics, Lyrics


HELP = "Enter: search/play  ↑↓: navigate  Esc: search  Tab: switch  P: pause  S: stop  L: lyrics  Q: quit"
HELP2 = "Seek: ←→ ±5s  [ ] ±10s  PgUp/Dn ±30s  Home/End"
SPINNER = "/-\\|"

MIN_COLS = 60
MIN_ROWS = 14


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

    # pair 1: header
    curses.init_pair(1, curses.COLOR_CYAN, -1)
    # pair 2: selected row
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
    # pair 3: success/playing
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    # pair 4: error
    curses.init_pair(4, curses.COLOR_RED, -1)
    # pair 5: results header
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLUE)
    # pair 6: search label
    curses.init_pair(6, curses.COLOR_MAGENTA, -1)
    # pair 7: status OK
    curses.init_pair(7, curses.COLOR_GREEN, curses.COLOR_BLACK)
    # pair 8: progress bar
    curses.init_pair(8, curses.COLOR_GREEN, -1)
    # pair 9: visualizers (both same color)
    curses.init_pair(9, curses.COLOR_CYAN, -1)


class App:
    def __init__(self):
        self.query: str = ""
        self.results: List[SearchResult] = []
        self.selected: int = 0
        self._last_max_rows: int = 10

        self.status: str = "Type a search query (spaces supported) and press Enter."
        self.now_playing: str = ""

        # Focus (where keystrokes go):
        # - query: typing edits the search bar (Space inserts a space)
        # - results: arrows select, Enter plays (Space toggles pause)
        self.mode: str = "query"  # query | results

        self._executor = ThreadPoolExecutor(max_workers=3)
        self._pending_search: Optional[Future[List[SearchResult]]] = None
        self._pending_play: Optional[Future[Tuple[AudioStream, None]]] = None
        self._pending_seek: Optional[Future[None]] = None
        self._pending_lyrics: Optional[Future[Lyrics | None]] = None

        # Used to prevent stale background play tasks from taking over playback.
        self._play_generation: int = 0

        # Lyrics support
        self.lyrics: Optional[Lyrics] = None
        self.current_lyric_index: int = 0
        self.show_lyrics: bool = True

        self.player = StreamPlayer()

    def busy_label(self) -> str:
        if self._pending_play is not None:
            return "Resolving"
        if self._pending_search is not None:
            return "Searching"
        if self._pending_seek is not None:
            return "Seeking"
        return ""

    def close(self) -> None:
        try:
            self.player.stop()
        finally:
            self._executor.shutdown(wait=False, cancel_futures=True)

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

        idx = max(0, min(self.selected, len(self.results) - 1))
        item = self.results[idx]
        self.status = "Resolving stream…"
        self.now_playing = item.title
        self.lyrics = None
        self.current_lyric_index = 0
        self.show_lyrics = True  # Re-enable lyrics when starting playback

        # Invalidate any previous play tasks so they can't call player.play() later.
        self._play_generation += 1
        play_gen = self._play_generation
        webpage_url = item.webpage_url

        # Start fetching lyrics
        self._pending_lyrics = self._executor.submit(fetch_lyrics, webpage_url)

        def _do_play() -> Tuple[AudioStream, None]:
            stream = resolve_best_audio_stream(webpage_url)

            # If a newer play request happened (or Stop was pressed), do nothing.
            if play_gen != self._play_generation:
                return (stream, None)

            self.player.play(
                stream.stream_url,
                http_headers=stream.http_headers,
                duration_seconds=stream.duration_seconds,
            )
            return (stream, None)

        self._pending_play = self._executor.submit(_do_play)

    def poll_background_tasks(self) -> None:
        if self._pending_search is not None and self._pending_search.done():
            try:
                self.results = self._pending_search.result()
                self.selected = 0
                self.mode = "results" if self.results else "query"
                self.status = f"Found {len(self.results)} result(s)."
            except Exception as e:
                self.status = f"Search failed: {e}"
            finally:
                self._pending_search = None

        if self._pending_play is not None and self._pending_play.done():
            try:
                stream, _ = self._pending_play.result()
                self.now_playing = stream.title
                self.status = "Playing."
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

        # Check for fetched lyrics
        if self._pending_lyrics is not None and self._pending_lyrics.done():
            try:
                self.lyrics = self._pending_lyrics.result()
                self.current_lyric_index = 0
            except Exception:
                self.lyrics = None
            finally:
                self._pending_lyrics = None

    def get_current_lyric(self) -> str | None:
        """Get the current lyric based on playback position."""
        if not self.lyrics or not self.lyrics.lines:
            return None

        pos = self.player.position_seconds()
        if pos is None:
            return None

        # Find the lyric at current position
        for i, line in enumerate(self.lyrics.lines):
            if line.start_time <= pos < line.end_time:
                self.current_lyric_index = i
                return line.text
            if pos < line.start_time:
                break

        return None

    def get_next_lyric(self) -> str | None:
        """Get the next lyric line."""
        if not self.lyrics or not self.lyrics.lines:
            return None
        
        if self.current_lyric_index + 1 < len(self.lyrics.lines):
            return self.lyrics.lines[self.current_lyric_index + 1].text
        
        return None


def _format_time(seconds: float | None) -> str:
    if seconds is None:
        return "--:--"
    if seconds < 0:
        seconds = 0
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _progress_bar(width: int, played_ratio: float, buffered_ratio: float | None = None) -> str:
    width = max(0, int(width))
    if width <= 0:
        return ""

    pr = min(1.0, max(0.0, float(played_ratio)))
    br = pr if buffered_ratio is None else min(1.0, max(0.0, float(buffered_ratio)))
    if br < pr:
        br = pr

    played = min(width, int(round(pr * width)))
    buffered = min(width, int(round(br * width)))
    if buffered < played:
        buffered = played

    # '=' played, '~' buffered ahead, '-' not yet buffered
    return "=" * played + "~" * max(0, buffered - played) + "-" * max(0, width - buffered)


def _meter_bar(width: int, level: float) -> str:
    width = max(0, int(width))
    if width <= 0:
        return ""
    r = min(1.0, max(0.0, float(level)))
    filled = min(width, int(round(r * width)))
    return "#" * filled + "." * max(0, width - filled)


def _capitalize_english(text: str) -> str:
    """Capitalize text if it appears to be in English."""
    # Simple heuristic: if most characters are ASCII letters, it's likely English
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    total_letters = sum(1 for c in text if c.isalpha())
    if total_letters > 0 and ascii_letters / total_letters > 0.8:
        return text.title()
    return text


def _draw(stdscr, app: App) -> None:
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    header_attr = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD

    # If the terminal is too small, show a focused message instead of a partially cut-off UI.
    if h < MIN_ROWS or w < MIN_COLS:
        _safe_addstr(stdscr, 0, 0, "TTube", header_attr)
        msg = f"Resize terminal to at least {MIN_COLS}x{MIN_ROWS} (current {w}x{h})."
        _safe_addstr(stdscr, 2, 0, msg[: max(0, w - 1)], curses.A_BOLD)
        _safe_addstr(stdscr, 3, 0, "Press Q to quit."[: max(0, w - 1)], curses.A_DIM)
        try:
            curses.curs_set(0)
        except Exception:
            pass
        stdscr.refresh()
        return

    is_busy = bool(app.busy_label())
    spinner = SPINNER[int(time.time() * 8) % len(SPINNER)] if is_busy else " "

    # TTube ASCII art logo - custom simple design centered
    ttube_lines = [
        "████████╗████████╗██╗   ██╗██████╗ ███████╗",
        "╚══██╔══╝╚══██╔══╝██║   ██║██╔══██╗██╔════╝",
        "   ██║      ██║   ██║   ██║██████╔╝█████╗  ",
        "   ██║      ██║   ██║   ██║██╔══██╗██╔══╝  ",
        "   ██║      ██║   ╚██████╔╝██████╔╝███████╗",
        "   ╚═╝      ╚═╝    ╚═════╝ ╚═════╝ ╚══════╝",
        ""
    ]
    
    focus = "SEARCH" if app.mode == "query" else "RESULTS"
    status_right = f"[{focus}] {spinner} {app.busy_label()}".rstrip()
    _safe_addstr(stdscr, 0, max(0, w - len(status_right) - 1), status_right[: max(0, w - 1)], header_attr)
    
    # Draw TTube ASCII art centered
    for i, line in enumerate(ttube_lines):
        if i < min(7, h):
            # Center the line
            line_len = len(line)
            left_pad = max(0, (w - line_len) // 2)
            display_line = (" " * left_pad + line)[: max(0, w - 1)]
            logo_attr = curses.color_pair(1) if curses.has_colors() else 0
            _safe_addstr(stdscr, i, 0, display_line, logo_attr)

    # Search bar
    query_label = "[?] Search" + ("*" if app.mode == "query" else "")
    label_attr = curses.color_pair(6) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
    _safe_addstr(stdscr, 8, 0, f"{query_label}: ", label_attr)
    bar_x = len(query_label) + 2
    bar_w = max(0, w - bar_x - 1)
    q = app.query
    q_attr = curses.A_REVERSE if app.mode == "query" else 0
    _safe_addstr(stdscr, 8, bar_x, (q + " " * max(0, bar_w - len(q)))[:bar_w], q_attr)

    # Results section
    results_y = 10
    results_header = f"[*] Results ({len(app.results)})" + ("*" if app.mode == "results" else "")
    results_attr = curses.color_pair(5) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
    _safe_addstr(stdscr, results_y, 0, results_header[: max(0, w - 1)], results_attr)

    list_top = results_y + 1
    # Reserve space for progressbar and VU meter (7 lines)
    reserved = 8 if app.now_playing else 3
    max_rows = max(0, h - list_top - reserved)
    app._last_max_rows = max_rows
    
    # Calculate right column for lyrics display
    results_col_width = 60  # Width reserved for results list (increased from 45)
    lyrics_col_start = results_col_width + 2  # Lyrics start after results
    lyrics_col_width = max(0, w - lyrics_col_start - 1)
    
    # Populate lyric_display_rows with only valid rows (not overlapping progress bar)
    lyric_display_rows = []
    for row_idx in range(max_rows):
        lyric_display_rows.append(list_top + row_idx)

    if app.results and max_rows > 0:
        start = 0
        if app.selected >= max_rows:
            start = app.selected - max_rows + 1

        view = app.results[start : start + max_rows]
        for i, r in enumerate(view):
            y = list_top + i
            absolute_idx = start + i
            selected = absolute_idx == app.selected
            prefix = ">> " if selected else "   "
            line = (prefix + r.title)[: max(0, results_col_width - 1)]

            if selected:
                attr = curses.color_pair(2) | curses.A_BOLD if curses.has_colors() else curses.A_REVERSE
            else:
                attr = 0

            _safe_addstr(stdscr, y, 0, line, attr)

        # Scroll indicator with visual representation
        if len(app.results) > max_rows:
            scroll_pos = app.selected + 1
            scroll_total = len(app.results)
            pos = f"[{scroll_pos}/{scroll_total}]"
            
            # Draw scrollbar indicator
            scroll_width = max(3, w - len(pos) - 2)
            filled = int((scroll_pos / scroll_total) * scroll_width) if scroll_total > 0 else 0
            scrollbar = "█" * filled + "░" * (scroll_width - filled)
            _safe_addstr(stdscr, results_y, max(0, w - len(pos) - len(scrollbar) - 2), scrollbar, curses.A_DIM)
            _safe_addstr(stdscr, results_y, max(0, w - len(pos) - 1), pos, curses.A_DIM)

    # Display lyrics on the right side at eye level (aligned with results)
    if app.show_lyrics and lyric_display_rows and lyrics_col_width > 0:
        # Check if lyrics are available and loaded
        current_lyric = None
        prefix = ""
        if app.lyrics is None:
            # Lyrics still loading, show nothing
            pass
        elif app.lyrics and app.lyrics.lines:
            current_lyric = app.get_current_lyric()
            next_lyric = app.get_next_lyric()
            lyric_attr = curses.color_pair(3) if curses.has_colors() else curses.A_BOLD
            
            # If no current lyric (playback not started or between lyrics), show first lyric
            if not current_lyric and app.lyrics.lines:
                current_lyric = app.lyrics.lines[0].text
                app.current_lyric_index = 0
                prefix = ">> "
            elif current_lyric:
                # Get animation progress
                lyric_start = app.lyrics.lines[app.current_lyric_index].start_time
                lyric_end = app.lyrics.lines[app.current_lyric_index].end_time
                pos = app.player.position_seconds() or 0
                
                if lyric_end > lyric_start:
                    progress = (pos - lyric_start) / (lyric_end - lyric_start)
                    progress = max(0.0, min(1.0, progress))
                
                if progress < 0.3:
                    prefix = ">> "
                elif progress < 0.7:
                    prefix = "> "
                else:
                    prefix = "  "
            else:
                prefix = ">> "
        else:
            prefix = ""
        
        if current_lyric:
            # Format lyric text with capitalization
            lyric_text = _capitalize_english(current_lyric)
            full_text = prefix + lyric_text
            
            # Split long lyrics into multiple lines on the right column
            words = full_text.split()
            lines_to_display = []
            current_line = ""
            
            for word in words:
                if len(current_line) + len(word) + 1 <= lyrics_col_width:
                    current_line += (" " if current_line else "") + word
                else:
                    if current_line:
                        lines_to_display.append(current_line)
                    current_line = word
            
            if current_line:
                lines_to_display.append(current_line)
            
            # Display wrapped lyrics on the right side
            for line_idx, lyric_line in enumerate(lines_to_display[:len(lyric_display_rows)]):
                y = lyric_display_rows[line_idx]
                _safe_addstr(stdscr, y, lyrics_col_start, lyric_line[: max(0, lyrics_col_width - 1)], lyric_attr)
            
            # Display next lyric preview
            if next_lyric and len(lines_to_display) < len(lyric_display_rows):
                next_lyric_text = _capitalize_english(next_lyric)
                next_display = "   " + next_lyric_text
                next_words = next_display.split()
                next_lines = []
                next_current_line = ""
                
                for word in next_words:
                    if len(next_current_line) + len(word) + 1 <= lyrics_col_width:
                        next_current_line += (" " if next_current_line else "") + word
                    else:
                        if next_current_line:
                            next_lines.append(next_current_line)
                        next_current_line = word
                
                if next_current_line:
                    next_lines.append(next_current_line)
                
                # Display next lyric preview on next available row
                for next_idx, next_line in enumerate(next_lines):
                    display_row_idx = len(lines_to_display) + next_idx
                    if display_row_idx < len(lyric_display_rows):
                        y = lyric_display_rows[display_row_idx]
                        next_attr = curses.A_DIM if curses.has_colors() else 0
                        _safe_addstr(stdscr, y, lyrics_col_start, next_line[: max(0, lyrics_col_width - 1)], next_attr)

    # Now playing with progressbar (moved to bottom section)
    if app.now_playing:
        np_line_y = h - 7
        np_attr = curses.color_pair(3) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
        paused = " [PAUSED]" if app.player.is_paused() else ""
        _safe_addstr(stdscr, np_line_y, 0, f">> Now: {app.now_playing}{paused}"[: max(0, w - 1)], np_attr)

        pos = app.player.position_seconds()
        dur = app.player.duration_seconds()
        buf = app.player.buffered_seconds()

        left = _format_time(pos)
        right = _format_time(dur)
        ratio = (pos / dur) if (dur is not None and dur > 0) else 0.0
        buf_ratio = ((pos + buf) / dur) if (dur is not None and dur > 0) else None

        label = f"{left} / {right}  buf:{buf:0.1f}s "
        bar_w = max(0, w - len(label) - 3)
        bar = _progress_bar(bar_w, ratio, buf_ratio)
        line = f"[{bar}] {label}"[: max(0, w - 1)]
        bar_attr = curses.color_pair(8) if curses.has_colors() else 0
        _safe_addstr(stdscr, np_line_y + 1, 0, line, bar_attr)

        # Simple visualizer (peak meter) - on separate line below progress bar
        lvl_l, lvl_r = app.player.levels()
        meter_w = 8  # Width of each visualizer
        meter_l = _meter_bar(meter_w, lvl_l)
        meter_r = _meter_bar(meter_w, lvl_r)
        
        # Visualizer labels with same color
        viz_attr = curses.color_pair(9) if curses.has_colors() else 0  # Cyan for both
        
        # Display visualizers on separate line below progress bar to avoid overlap
        vu_line_y = np_line_y + 2
        
        # Left visualizer
        x_pos = 0
        _safe_addstr(stdscr, vu_line_y, x_pos, "L[", viz_attr)
        x_pos += 2
        _safe_addstr(stdscr, vu_line_y, x_pos, meter_l, viz_attr)
        x_pos += len(meter_l)
        _safe_addstr(stdscr, vu_line_y, x_pos, "]", viz_attr)
        
        # Right visualizer - on the RIGHT EDGE
        right_x = w - len(meter_r) - 3
        _safe_addstr(stdscr, vu_line_y, right_x, "R[", viz_attr)
        _safe_addstr(stdscr, vu_line_y, right_x + 2, meter_r, viz_attr)
        _safe_addstr(stdscr, vu_line_y, right_x + 2 + len(meter_r), "]", viz_attr)

    # Status bar at bottom left
    status_attr = 0
    if curses.has_colors():
        s = app.status.lower()
        if s.startswith("search failed") or s.startswith("playback failed") or s.startswith("seek failed"):
            status_attr = curses.color_pair(4) | curses.A_BOLD
        elif s.startswith("playing") or s.startswith("searching"):
            status_attr = curses.color_pair(7)

    status_line = f"[*] Status: {app.status}"[: max(0, w - len(HELP) - 5)]
    _safe_addstr(stdscr, h - 1, 0, status_line, status_attr)
    
    # Keyboard controls at bottom right
    controls_line = HELP[: max(0, w - 1)]
    _safe_addstr(stdscr, h - 1, max(0, w - len(controls_line) - 1), controls_line)

    # Cursor visibility + placement.
    try:
        curses.curs_set(1 if app.mode == "query" else 0)
    except Exception:
        pass

    if app.mode == "query":
        try:
            stdscr.move(8, bar_x + min(len(q), bar_w))
        except Exception:
            pass

    stdscr.refresh()


def _handle_input(ch: int, app: App) -> bool:
    """Return False to exit."""
    if ch in (-1, 0):
        return True

    # Always-available
    if ch in (ord("q"), ord("Q")):
        return False

    # Focus controls (should work in both modes)
    if ch == 27:  # Esc
        app.mode = "query"
        return True

    # '/' focuses search when browsing results (less/vim style). In query mode it should
    # be treated as a normal character so users can search things like "AC/DC".
    if ch == ord("/") and app.mode == "results":
        app.mode = "query"
        return True

    if ch in (9,):  # Tab
        if app.mode == "query" and app.results:
            app.mode = "results"
        else:
            app.mode = "query"
        return True

    # ===== QUERY MODE =====
    if app.mode == "query":
        if ch in (curses.KEY_ENTER, 10, 13):
            app.start_search()
            return True

        if ch in (curses.KEY_UP, curses.KEY_DOWN) and app.results:
            app.mode = "results"
            return True

        if ch in (curses.KEY_BACKSPACE, 8, 127, curses.KEY_DC):
            app.query = app.query[:-1]
            return True

        # Ctrl+U clears the line
        if ch == 21:
            app.query = ""
            return True

        # Accept printable chars INCLUDING space - this allows P, S, Space to be typed
        if 32 <= ch <= 126:
            app.query += chr(ch)
            return True

        return True

    # ===== RESULTS MODE =====
    if ch == curses.KEY_UP:
        app.selected = max(0, app.selected - 1)
        return True

    if ch == curses.KEY_DOWN:
        app.selected = min(len(app.results) - 1, app.selected + 1)
        return True

    # Stop (only in results mode)
    if ch in (ord("s"), ord("S")):
        app.player.stop()
        app.now_playing = ""
        app.show_lyrics = False  # Hide lyrics when music is stopped

        # Cancel/ignore any in-flight play or seek requests.
        app._play_generation += 1
        if app._pending_play is not None:
            try:
                app._pending_play.cancel()
            except Exception:
                pass
            app._pending_play = None
        if app._pending_seek is not None:
            try:
                app._pending_seek.cancel()
            except Exception:
                pass
            app._pending_seek = None

        app.status = "Stopped."
        return True

    # Pause: only in results mode (P always works; Space only when focus is results)
    if ch in (ord("p"), ord("P"), ord(" ")):
        app.player.toggle_pause()
        app.status = "Paused." if app.player.is_paused() else "Playing."
        return True

    # Lyrics toggle (L key)
    if ch in (ord("l"), ord("L")):
        app.show_lyrics = not app.show_lyrics
        status_text = "Lyrics: ON" if app.show_lyrics else "Lyrics: OFF"
        app.status = status_text
        return True

    # Seeking (only when we have a duration)
    if app.now_playing and app.player.duration_seconds() is not None:
        # Avoid stacking multiple seeks.
        if app._pending_seek is None:
            # small ±5s
            if ch == curses.KEY_LEFT:
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_relative, -5.0)
                return True
            if ch == curses.KEY_RIGHT:
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_relative, +5.0)
                return True

            # medium ±10s
            if ch == ord("["):
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_relative, -10.0)
                return True
            if ch == ord("]"):
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_relative, +10.0)
                return True

            # big ±30s (PageUp/PageDown)
            if ch == curses.KEY_PPAGE:
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_relative, -30.0)
                return True
            if ch == curses.KEY_NPAGE:
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_relative, +30.0)
                return True

            if ch == curses.KEY_HOME:
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_to, 0.0)
                return True
            if ch == curses.KEY_END:
                app.status = "Seeking…"
                app._pending_seek = app._executor.submit(app.player.seek_to, float(app.player.duration_seconds() or 0.0))
                return True

    # Results paging/jumps (only when not used for seeking)
    if app.results:
        page = max(1, int(app._last_max_rows) or 1)
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
        app.start_play_selected()
        return True

    # If the user starts typing while in results, switch back to search and keep the keystroke.
    if 32 <= ch <= 126:
        app.mode = "query"
        app.query += chr(ch)
        return True

    return True


def main(stdscr) -> None:
    _init_colors()

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
    """Console entrypoint installed by pip (see pyproject.toml)."""
    curses.wrapper(main)


if __name__ == "__main__":
    cli()
