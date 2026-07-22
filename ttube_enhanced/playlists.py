"""Playlist persistence – save/load JSON playlists to ~/Music/TTube/playlists/"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional

PLAYLISTS_DIR = os.path.join(os.path.expanduser("~"), "Music", "TTube", "playlists")


@dataclass
class PlTrack:
    title:       str
    video_id:    str
    webpage_url: str
    artist:      str = ""
    artwork_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlTrack":
        return cls(**{k: d.get(k, "") for k in cls.__dataclass_fields__})


@dataclass
class Playlist:
    name:   str
    tracks: List[PlTrack] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "tracks": [t.to_dict() for t in self.tracks]}

    @classmethod
    def from_dict(cls, d: dict) -> "Playlist":
        return cls(
            name=d.get("name", "Untitled"),
            tracks=[PlTrack.from_dict(t) for t in d.get("tracks", [])],
        )


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()[:80] or "playlist"


def _path(name: str) -> str:
    os.makedirs(PLAYLISTS_DIR, exist_ok=True)
    return os.path.join(PLAYLISTS_DIR, _safe(name) + ".json")


# ── public API ────────────────────────────────────────────────────────────────

def list_playlists() -> List[Playlist]:
    os.makedirs(PLAYLISTS_DIR, exist_ok=True)
    result = []
    has_liked = False
    for fname in sorted(os.listdir(PLAYLISTS_DIR)):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(PLAYLISTS_DIR, fname), encoding="utf-8") as f:
                    pl = Playlist.from_dict(json.load(f))
                    result.append(pl)
                    if pl.name == "Liked Songs":
                        has_liked = True
            except Exception:
                pass
    if not has_liked:
        liked_pl = Playlist(name="Liked Songs")
        save_playlist(liked_pl)
        result.insert(0, liked_pl)
    return result


def save_playlist(pl: Playlist) -> str:
    p = _path(pl.name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(pl.to_dict(), f, indent=2, ensure_ascii=False)
    return p


def load_playlist(name: str) -> Optional[Playlist]:
    p = _path(name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return Playlist.from_dict(json.load(f))


def delete_playlist(name: str) -> bool:
    p = _path(name)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def add_to_playlist(pl_name: str, track: PlTrack) -> Playlist:
    pl = load_playlist(pl_name) or Playlist(name=pl_name)
    # Deduplicate by video_id
    if not any(t.video_id == track.video_id for t in pl.tracks):
        pl.tracks.append(track)
    save_playlist(pl)
    return pl


def remove_from_playlist(pl_name: str, video_id: str) -> Optional[Playlist]:
    pl = load_playlist(pl_name)
    if not pl:
        return None
    pl.tracks = [t for t in pl.tracks if t.video_id != video_id]
    save_playlist(pl)
    return pl
