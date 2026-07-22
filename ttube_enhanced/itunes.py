"""
iTunes Search API – suggestions, metadata matching, title cleaning.
Free API – no key required.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Metadata:
    title:       str = ""
    artist:      str = ""
    album:       str = ""
    artwork_url: str = ""   # high-res 600×600
    duration_ms: int = 0

    @classmethod
    def from_itunes(cls, t: Dict) -> "Metadata":
        url = t.get("artworkUrl100", "")
        if url:
            # Upgrade to larger artwork (600px)
            url = re.sub(r"\d+x\d+bb\.jpg", "600x600bb.jpg", url)
            url = re.sub(r"\d+x\d+bb\.png", "600x600bb.png", url)
        return cls(
            title=t.get("trackName", ""),
            artist=t.get("artistName", ""),
            album=t.get("collectionName", ""),
            artwork_url=url,
            duration_ms=t.get("trackTimeMillis", 0),
        )

    def fmt_duration(self) -> str:
        if not self.duration_ms:
            return ""
        s = self.duration_ms // 1000
        h, m, sec = s // 3600, (s % 3600) // 60, s % 60
        return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


# ── API calls ─────────────────────────────────────────────────────────────────

def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "TTube/0.2"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def search_suggestions(query: str, limit: int = 6) -> List[Dict]:
    """Return raw iTunes track dicts for autocomplete suggestions."""
    q = query.strip()
    if len(q) < 2:
        return []
    try:
        term = urllib.parse.quote(q)
        data = _get(
            f"https://itunes.apple.com/search"
            f"?term={term}&media=music&entity=song&limit={limit}"
        )
        return data.get("results", [])
    except Exception:
        return []


def match_metadata(youtube_title: str) -> Optional[Metadata]:
    """Find best iTunes match for a YouTube video title."""
    cleaned    = clean_youtube_title(youtube_title)
    candidates = search_suggestions(cleaned, limit=10)
    if not candidates:
        return None

    yt = cleaned.lower()
    best: Optional[Dict] = None
    best_score: float    = 0.0

    for t in candidates:
        name   = t.get("trackName",  "").lower()
        artist = t.get("artistName", "").lower()
        score  = 0.0

        if name and (name in yt or yt in name):
            score += 3.0
        elif name:
            score += sum(0.5 for w in name.split() if len(w) > 3 and w in yt)

        if artist and artist in youtube_title.lower():
            score += 2.0

        if score > best_score:
            best_score, best = score, t

    if best and best_score >= 1.0:
        return Metadata.from_itunes(best)
    return None


def clean_youtube_title(title: str) -> str:
    """Strip YouTube decorations so the title can match a music catalogue."""
    pats = [
        r"\(Official\s*(?:Music\s*)?Video\)",  r"\[Official\s*(?:Music\s*)?Video\]",
        r"\(Official\s*(?:Lyric\s*)?Video\)",  r"\[Official\s*(?:Lyric\s*)?Video\]",
        r"\(Official\s*Audio\)",               r"\[Official\s*Audio\]",
        r"\(Official\)",                        r"\[Official\]",
        r"\(Audio\)",                           r"\[Audio\]",
        r"\(Lyric\s*Video\)",                  r"\[Lyric\s*Video\]",
        r"\(Lyrics?\)",                         r"\[Lyrics?\]",
        r"\((?:HD|HQ|4K|8K|UHD)\)",           r"\[(?:HD|HQ|4K|8K|UHD)\]",
        r"\(Explicit\)",                        r"\[Explicit\]",
        r"\(Remastered[^)]*\)",                r"\[Remastered[^\]]*\]",
        r"\(Visualizer\)",                      r"\[Visualizer\]",
        r"\(Live[^)]*\)",                      r"\[Live[^\]]*\]",
        r"\|\s*.+$",
        r"feat(?:uring)?\.?\s+[\w\s,&]+(?=\s*[-(\[]|$)",
        r"ft\.?\s+[\w\s,&]+(?=\s*[-(\[]|$)",
    ]
    result = title
    for pat in pats:
        result = re.sub(pat, "", result, flags=re.IGNORECASE).strip()
    return result.strip(" \t-–|") or title
