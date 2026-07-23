from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import json
import re
import urllib.request

import yt_dlp
from ytmusicapi import YTMusic
import syncedlyrics


@dataclass(frozen=True)
class SearchResult:
    title: str
    video_id: str
    webpage_url: str


@dataclass(frozen=True)
class AudioStream:
    title: str
    webpage_url: str
    stream_url: str
    http_headers: Dict[str, str]
    duration_seconds: int | None


@dataclass
class LyricLine:
    """Single lyric line with timing information."""
    text: str
    start_time: float  # seconds
    end_time: float    # seconds


@dataclass(frozen=True)
class Lyrics:
    """Lyrics/subtitles for a video."""
    lines: List[LyricLine]
    is_auto_generated: bool = False


def search_youtube(query: str, limit: int = 10) -> List[SearchResult]:
    """Fast metadata-only search using YTMusicAPI for high quality official results."""
    query = (query or "").strip()
    if not query:
        return []

    try:
        ytmusic = YTMusic()
        results_raw = ytmusic.search(query, filter="songs", limit=limit)

        results: List[SearchResult] = []
        for r in results_raw:
            video_id = r.get("videoId")
            if not video_id:
                continue

            title   = r.get("title", "(untitled)")
            artists = ", ".join([a.get("name", "") for a in r.get("artists", []) if a.get("name")])
            if artists:
                title = f"{title} - {artists}"

            webpage_url = f"https://www.youtube.com/watch?v={video_id}"
            results.append(SearchResult(title=title, video_id=video_id, webpage_url=webpage_url))

        return results
    except Exception as e:
        with open("error_log.txt", "a") as f:
            import traceback
            f.write(f"YTMusic search failed: {e}\n{traceback.format_exc()}\n")
        return []


def _pick_best_audio_format(formats: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    audio_formats = [
        f for f in formats
        if f
        and f.get("vcodec") == "none"
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]
    if not audio_formats:
        return None

    def score(f: Dict[str, Any]) -> Tuple[float, float, int]:
        abr = float(f.get("abr") or 0.0)
        tbr = float(f.get("tbr") or 0.0)
        asr = int(f.get("asr") or 0)
        # Target sweet spot: 96–160 kbps (loads fast, sounds great).
        # Penalise streams above 160 kbps so we don't wait for 320 kbps.
        effective_abr = abr if abr else tbr
        penalty = max(0.0, effective_abr - 160.0) * 5.0   # lose 5 pts per kbps over 160
        return (effective_abr - penalty, float(tbr), asr)

    return max(audio_formats, key=score)


def _strip_ansi(s: str) -> str:
    """Remove ANSI escape codes from a string."""
    import re as _re
    return _re.sub(r"\x1b\[[0-9;]*m", "", s)


# Cache the last resolved info so subtitle fetch can reuse it without a second yt-dlp call.
_info_cache: Dict[str, Any] = {}


def resolve_best_audio_stream(webpage_url: str) -> AudioStream:
    """Resolve a direct best-audio URL plus headers for ffmpeg."""
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android", "mweb"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(webpage_url, download=False)
    except Exception as e:
        raise RuntimeError(_strip_ansi(str(e))) from None

    if not info:
        raise RuntimeError("yt-dlp returned no info")

    # Cache for subtitle reuse (fetched later by fetch_lyrics / fetch_available_caption_tracks)
    _info_cache[webpage_url] = info

    title    = info.get("title") or "(untitled)"
    duration = info.get("duration")
    try:
        duration_seconds = int(duration) if duration is not None else None
    except Exception:
        duration_seconds = None

    formats = info.get("formats") or []
    best    = _pick_best_audio_format(formats)

    if not best:
        if info.get("url"):
            return AudioStream(
                title=title, webpage_url=webpage_url,
                stream_url=info["url"],
                http_headers=dict(info.get("http_headers") or {}),
                duration_seconds=duration_seconds,
            )
        raise RuntimeError("Could not find a usable audio-only format")

    headers = best.get("http_headers") or info.get("http_headers") or {}
    return AudioStream(
        title=title, webpage_url=webpage_url,
        stream_url=best["url"],
        http_headers=dict(headers),
        duration_seconds=duration_seconds,
    )


def headers_to_ffmpeg_arg(headers: Dict[str, str]) -> str:
    lines = [f"{k}: {v}" for k, v in headers.items() if k and v is not None]
    return "\r\n".join(lines) + ("\r\n" if lines else "")


import syncedlyrics

def fetch_lyrics(title: str) -> Optional[Lyrics]:
    """Fetch perfectly timed LRC lyrics using syncedlyrics (Spotify/Musixmatch)."""
    try:
        # Pass the video title (which usually contains the song name and artist)
        lrc = syncedlyrics.search(title)
        if not lrc:
            return None
            
        lines: List[LyricLine] = []
        for line in lrc.splitlines():
            line = line.strip()
            if not line:
                continue
                
            # Parse LRC format: [mm:ss.xx] lyric text
            m = re.match(r"^\[(\d+):(\d+\.\d+)\](.*)$", line)
            if not m:
                continue
                
            mins = int(m.group(1))
            secs = float(m.group(2))
            text = m.group(3).strip()
            
            # Skip empty lines (instrumental sections)
            if not text:
                continue
                
            start = mins * 60 + secs
            lines.append(LyricLine(start_time=start, end_time=start + 5.0, text=text))
            
        # Fix end times to bridge the gap to the next lyric
        for i in range(len(lines) - 1):
            lines[i].end_time = lines[i+1].start_time
            
        if not lines:
            return None
            
        return Lyrics(lines=lines)
    except Exception:
        return None
