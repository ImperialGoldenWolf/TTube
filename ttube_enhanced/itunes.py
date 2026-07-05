"""
iTunes Search API client, Metadata dataclass, and YouTube title cleaner.
Uses the free, key-less iTunes Search API (itunes.apple.com/search).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Metadata ─────────────────────────────────────────────────────────────────

@dataclass
class Metadata:
    title:       str = ""
    artist:      str = ""
    album:       str = ""
    artwork_url: str = ""   # high-res (600×600) iTunes artwork
    duration_ms: int = 0

    @classmethod
    def from_itunes(cls, track: Dict) -> "Metadata":
        url = track.get("artworkUrl100", "")
        # Upgrade to 600 px artwork
        if url:
            url = re.sub(r"\d+x\d+bb", "600x600bb", url)
        return cls(
            title       = track.get("trackName",      ""),
            artist      = track.get("artistName",     ""),
            album       = track.get("collectionName", ""),
            artwork_url = url,
            duration_ms = track.get("trackTimeMillis", 0),
        )

    @classmethod
    def from_raw_title(cls, raw_title: str) -> "Metadata":
        return cls(title=clean_youtube_title(raw_title))

    def display_duration(self) -> str:
        if not self.duration_ms:
            return ""
        total = self.duration_ms // 1000
        h, m, s = total // 3600, (total % 3600) // 60, total % 60
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Public API ────────────────────────────────────────────────────────────────

def search_suggestions(query: str, limit: int = 5) -> List[Dict]:
    """
    Return up to *limit* iTunes song suggestions for *query*.
    Each dict has: trackName, artistName, collectionName,
                   artworkUrl100, trackTimeMillis.
    Returns [] on any network/parse error (safe to call from threads).
    """
    q = query.strip()
    if len(q) < 2:
        return []
    try:
        term = urllib.parse.quote(q)
        url  = (
            "https://itunes.apple.com/search"
            f"?term={term}&media=music&entity=song&limit={limit}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "TTube/0.1"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.load(r)
        return data.get("results", [])
    except Exception:
        return []


def match_metadata(youtube_title: str) -> Optional[Metadata]:
    """
    Try to find an iTunes track matching a YouTube video title.
    Returns a Metadata if a confident match is found, else None.
    """
    cleaned   = clean_youtube_title(youtube_title)
    candidates = search_suggestions(cleaned, limit=10)
    if not candidates:
        return None

    yt = cleaned.lower()
    best_track: Optional[Dict] = None
    best_score: float = 0.0

    for track in candidates:
        name   = track.get("trackName",  "").lower()
        artist = track.get("artistName", "").lower()
        score  = 0.0

        if name and (name in yt or yt in name):
            score += 3.0
        elif name:
            score += sum(0.5 for w in name.split() if len(w) > 3 and w in yt)

        # bonus if artist appears in the raw youtube title
        if artist and artist in youtube_title.lower():
            score += 2.0

        if score > best_score:
            best_score, best_track = score, track

    if best_track and best_score >= 1.0:
        return Metadata.from_itunes(best_track)
    return None


def clean_youtube_title(title: str) -> str:
    """
    Strip common YouTube decorations so the result can be matched against
    a proper music catalogue.

    'Bohemian Rhapsody (Official Music Video) [HD]'
        → 'Bohemian Rhapsody'
    """
    STRIP = [
        r"\(Official\s*(?:Music\s*)?Video\)",
        r"\[Official\s*(?:Music\s*)?Video\]",
        r"\(Official\s*(?:Lyric\s*)?Video\)",
        r"\[Official\s*(?:Lyric\s*)?Video\]",
        r"\(Official\s*Audio\)",    r"\[Official\s*Audio\]",
        r"\(Official\)",            r"\[Official\]",
        r"\(Audio\)",               r"\[Audio\]",
        r"\(Lyric\s*Video\)",       r"\[Lyric\s*Video\]",
        r"\(Lyrics?\)",             r"\[Lyrics?\]",
        r"\((?:HD|HQ|4K|8K|UHD)\)", r"\[(?:HD|HQ|4K|8K|UHD)\]",
        r"\(Explicit\)",            r"\[Explicit\]",
        r"\(Remastered[^)]*\)",     r"\[Remastered[^\]]*\]",
        r"\(Visualizer\)",          r"\[Visualizer\]",
        r"\(Live[^)]*\)",           r"\[Live[^\]]*\]",
        r"\|\s*.+$",                            # everything after " | "
        r"feat(?:uring)?\.?\s+[\w\s,&]+(?=\s*[-(\[]|$)",
        r"ft\.?\s+[\w\s,&]+(?=\s*[-(\[]|$)",
    ]
    result = title
    for pat in STRIP:
        result = re.sub(pat, "", result, flags=re.IGNORECASE).strip()

    result = result.strip(" \t-–|").strip()
    return result or title
