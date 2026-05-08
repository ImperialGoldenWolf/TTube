from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import yt_dlp


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


def search_youtube(query: str, limit: int = 10) -> List[SearchResult]:
    """Fast metadata-only search (no download)."""
    query = (query or "").strip()
    if not query:
        return []

    ydl_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    entries = (info or {}).get("entries") or []
    results: List[SearchResult] = []

    for e in entries:
        if not e:
            continue

        video_id = e.get("id")
        title = e.get("title") or "(untitled)"
        webpage_url = e.get("webpage_url")

        if not webpage_url and video_id:
            webpage_url = f"https://www.youtube.com/watch?v={video_id}"

        if not video_id or not webpage_url:
            continue

        results.append(SearchResult(title=title, video_id=video_id, webpage_url=webpage_url))

    return results


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
        abr = f.get("abr") or 0.0
        tbr = f.get("tbr") or 0.0
        asr = f.get("asr") or 0
        return (float(abr), float(tbr), int(asr))

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
