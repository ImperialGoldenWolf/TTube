from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import json
import urllib.request

import yt_dlp
from ytmusicapi import YTMusic


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


@dataclass(frozen=True)
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
        # Search for songs specifically to get official tracks
        results_raw = ytmusic.search(query, filter="songs", limit=limit)
        
        results: List[SearchResult] = []
        for r in results_raw:
            video_id = r.get("videoId")
            if not video_id:
                continue
                
            title = r.get("title", "(untitled)")
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
        f
        for f in formats
        if f
        and f.get("vcodec") == "none"
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]
    if not audio_formats:
        return None

    def score(f: Dict[str, Any]) -> Tuple[float, float, int]:
        # Prioritize full quality: higher audio bitrate (abr) is weighted most heavily
        abr = f.get("abr") or 0.0
        tbr = f.get("tbr") or 0.0
        asr = f.get("asr") or 0
        # Weight ABR higher (multiply by 1000) to ensure highest quality audio is selected first
        return (float(abr) * 1000.0, float(tbr), int(asr))

    return max(audio_formats, key=score)


def resolve_best_audio_stream(webpage_url: str) -> AudioStream:
    """Resolve a direct best-audio URL plus headers for ffmpeg.

    This does NOT download the file; it returns a signed media URL that ffmpeg can read.
    """
    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(webpage_url, download=False)

    if not info:
        raise RuntimeError("yt-dlp returned no info")

    title = info.get("title") or "(untitled)"
    duration = info.get("duration")
    try:
        duration_seconds = int(duration) if duration is not None else None
    except Exception:
        duration_seconds = None

    formats = info.get("formats") or []

    best = _pick_best_audio_format(formats)
    if not best:
        # Some extractors may put the selected format URL at top-level.
        if info.get("url"):
            stream_url = info["url"]
            headers = (info.get("http_headers") or {})
            return AudioStream(
                title=title,
                webpage_url=webpage_url,
                stream_url=stream_url,
                http_headers=dict(headers),
                duration_seconds=duration_seconds,
            )
        raise RuntimeError("Could not find a usable audio-only format")

    stream_url = best["url"]
    headers = best.get("http_headers") or info.get("http_headers") or {}

    return AudioStream(
        title=title,
        webpage_url=webpage_url,
        stream_url=stream_url,
        http_headers=dict(headers),
        duration_seconds=duration_seconds,
    )


def headers_to_ffmpeg_arg(headers: Dict[str, str]) -> str:
    """Convert a header dict to ffmpeg's -headers argument value."""
    # ffmpeg expects CRLF between lines.
    lines = []
    for k, v in headers.items():
        if not k or v is None:
            continue
        lines.append(f"{k}: {v}")
    return "\r\n".join(lines) + ("\r\n" if lines else "")


def _parse_vtt_subtitles(vtt_content: str) -> List[LyricLine]:
    """Parse VTT (WebVTT) subtitle format to lyric lines."""
    lines = []
    current_text = []
    start_time = 0.0
    end_time = 0.0
    
    for line in vtt_content.split('\n'):
        line = line.strip()
        
        # Skip empty lines and metadata
        if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
            continue
        
        # Detect timestamp line (format: 00:00:00.000 --> 00:00:05.000)
        if '-->' in line:
            parts = line.split('-->')
            if len(parts) == 2:
                try:
                    start_str = parts[0].strip()
                    end_str = parts[1].strip().split()[0]  # Remove cue settings
                    start_time = _vtt_time_to_seconds(start_str)
                    end_time = _vtt_time_to_seconds(end_str)
                except Exception:
                    continue
        # Text line (not a timestamp)
        elif line and not line.startswith('STYLE'):
            current_text.append(line)
        
        # When we hit a new timestamp or end, save the previous lyric
        if '-->' in line and current_text:
            text = ' '.join(current_text).strip()
            if text:
                lines.append(LyricLine(text=text, start_time=start_time, end_time=end_time))
            current_text = []
    
    # Don't forget the last one
    if current_text:
        text = ' '.join(current_text).strip()
        if text:
            lines.append(LyricLine(text=text, start_time=start_time, end_time=end_time))
    
    return lines


def _vtt_time_to_seconds(time_str: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm) to seconds."""
    try:
        parts = time_str.replace(',', '.').split(':')
        hours = float(parts[0]) if len(parts) > 2 else 0
        minutes = float(parts[-2]) if len(parts) > 1 else 0
        seconds = float(parts[-1]) if parts else 0
        return hours * 3600 + minutes * 60 + seconds
    except Exception:
        return 0.0


def _parse_json_subtitles(json_content: str) -> List[LyricLine]:
    """Parse JSON-based subtitles (YouTube format)."""
    try:
        data = json.loads(json_content)
        lines = []
        
        # Handle various JSON subtitle formats
        events = data.get('events') or []
        for event in events:
            if 'segs' not in event:
                continue
            
            start_ms = event.get('tStartMs', 0)
            dur_ms = event.get('dDurationMs', 0)
            
            text_parts = []
            for seg in event['segs']:
                if 'utf8' in seg:
                    text_parts.append(seg['utf8'])
            
            if text_parts:
                text = ''.join(text_parts).strip()
                if text and text not in ['[', ']']:
                    lines.append(LyricLine(
                        text=text,
                        start_time=int(start_ms) / 1000.0,
                        end_time=(int(start_ms) + int(dur_ms)) / 1000.0
                    ))
        
        return lines
    except Exception:
        return []


def fetch_lyrics(webpage_url: str) -> Lyrics | None:
    """Fetch subtitles/lyrics from YouTube video.
    
    Returns a Lyrics object if subtitles are available, None otherwise.
    Tries to fetch auto-generated subtitles first, then manual subtitles.
    """
    try:
        # yt-dlp option to get subtitle data without writing to files
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "getsubtitles": True,
            "noplaylist": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(webpage_url, download=False)
        
        if not info:
            return None
        
        # Try to get subtitles
        subtitles = info.get('subtitles') or {}
        auto_subs = info.get('automatic_captions') or {}
        
        all_subs = {**subtitles, **auto_subs}
        is_auto = bool(auto_subs and not subtitles)
        
        if not all_subs:
            return None
        
        # Prefer English, fallback to first available
        sub_lang = 'en' if 'en' in all_subs else next(iter(all_subs.keys())) if all_subs else None
        
        if not sub_lang or sub_lang not in all_subs:
            return None
        
        sub_data = all_subs[sub_lang]
        if not sub_data:
            return None
        
        # sub_data is a list of format dicts with 'url' and 'ext' keys
        sub_entry = sub_data[0] if isinstance(sub_data, list) else sub_data
        
        if not isinstance(sub_entry, dict) or 'url' not in sub_entry:
            return None
        
        # Download the subtitle content from the URL
        try:
            with urllib.request.urlopen(sub_entry['url'], timeout=10) as response:
                sub_content = response.read().decode('utf-8', errors='replace')
        except Exception:
            return None
        
        if not sub_content:
            return None
        
        # Parse based on format
        if 'WEBVTT' in sub_content or '-->' in sub_content:
            lines = _parse_vtt_subtitles(sub_content)
        else:
            try:
                lines = _parse_json_subtitles(sub_content)
            except Exception:
                lines = []
        
        if not lines:
            return None
        
        return Lyrics(lines=lines, is_auto_generated=is_auto)
    
    except Exception as e:
        # Silently fail - lyrics are optional
        return None
