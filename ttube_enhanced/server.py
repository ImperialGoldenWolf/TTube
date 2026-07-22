"""
TTube Enhanced – Flask backend (v3).
Fixes: play on first click, artwork loading, shutdown on browser close.
New: playlists, library view, seek ±10s, heartbeat, artist following, caching.
"""
from __future__ import annotations

import json
import hashlib
import os
import signal
import sys
import threading
import time
import urllib.request
import urllib.parse
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

_HERE   = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (_HERE, _PARENT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, jsonify, request, send_from_directory, Response

from ttube_stream  import StreamPlayer
from ttube_youtube import search_youtube, fetch_lyrics, _parse_vtt_subtitles
from itunes        import search_suggestions as _itunes_sugg, match_metadata
from downloader    import DownloadManager, DOWNLOAD_DIR
from playlists     import (Playlist, PlTrack, list_playlists, save_playlist,
                           load_playlist, delete_playlist,
                           add_to_playlist, remove_from_playlist)
import mutagen.mp3

_STATIC = os.path.join(_HERE, "static")

CACHE_DIR = os.path.join(os.path.expanduser("~"), "Music", "TTube", "cache")
ART_DIR   = os.path.join(CACHE_DIR, "artworks")

app = Flask(__name__, static_folder=_STATIC, static_url_path="/static")
app.config["JSON_SORT_KEYS"] = False


# ── Caching & Artists ─────────────────────────────────────────────────────────

def _cache_key(title: str) -> str:
    return hashlib.md5(title.lower().encode()).hexdigest()

def get_meta_cache(title: str) -> Optional[dict]:
    p = os.path.join(CACHE_DIR, _cache_key(title) + ".json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return None

def set_meta_cache(title: str, data: dict) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, _cache_key(title) + ".json")
    with open(p, "w", encoding="utf-8") as f: json.dump(data, f)

def get_followed_artists() -> list[str]:
    p = os.path.join(CACHE_DIR, "artists.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return []

def save_followed_artists(artists: list[str]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    p = os.path.join(CACHE_DIR, "artists.json")
    with open(p, "w", encoding="utf-8") as f: json.dump(artists, f)

def get_artist_history() -> dict[str, int]:
    p = os.path.join(CACHE_DIR, "history.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {}

def record_artist(artist: str) -> None:
    if not artist: return
    hist = get_artist_history()
    hist[artist] = hist.get(artist, 0) + 1
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, "history.json"), "w", encoding="utf-8") as f:
        json.dump(hist, f)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ch(n: int) -> str:
    return {1: "MONO", 2: "STEREO", 3: "2.1", 6: "5.1", 8: "7.1"}.get(n, f"{n}ch")

def _fmt(s) -> str:
    if s is None: return "--:--"
    t = max(0, int(s))
    h, m, sec = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"

def _resolve(url: str, quality: str = "standard"):
    """Return (stream_url, headers, duration, title, channels)."""
    import yt_dlp
    # High quality = best audio available. Standard = low bandwidth
    fmt = "bestaudio" if quality == "high" else "bestaudio[abr<=128]/bestaudio"
    opts = {"quiet": True, "no_warnings": True,
            "skip_download": True, "format": fmt, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("yt-dlp returned no info")
    title    = info.get("title") or "(untitled)"
    duration = info.get("duration")
    fmts     = [f for f in (info.get("formats") or [])
                if f and f.get("vcodec") == "none"
                and f.get("acodec") not in (None, "none") and f.get("url")]
    channels = 2
    if fmts:
        best     = max(fmts, key=lambda f: (float(f.get("abr") or 0) * 1000,
                                            float(f.get("tbr") or 0)))
        surl     = best["url"]
        hdrs     = dict(best.get("http_headers") or info.get("http_headers") or {})
        channels = int(best.get("audio_channels") or 2)
    else:
        surl = info.get("url", "")
        hdrs = dict(info.get("http_headers") or {})
    return surl, hdrs, (float(duration) if duration else None), title, channels


# ── Global player state ───────────────────────────────────────────────────────

class State:
    def __init__(self) -> None:
        self.player    = StreamPlayer()
        self.playing   = False
        self.paused    = False
        self.loading   = False          # yt-dlp resolving
        self.meta_loading = False       # itunes resolving
        self.title     = ""
        self.artist    = ""
        self.album     = ""
        self.artwork   = ""
        self.channels  = 2
        self.error     = ""
        self.vid       = ""
        self.webpage_url = ""
        self.lyrics_lines: list = []
        self._gen      = 0
        self._ex       = ThreadPoolExecutor(max_workers=4)
        self.dl        = DownloadManager()
        self.last_hb   = time.time()


_st = State()

_WEBVIEW_MODE = False

def _watchdog() -> None:
    time.sleep(10)
    while True:
        time.sleep(5)
        if _WEBVIEW_MODE: return
        if time.time() - _st.last_hb > 45:
            os.kill(os.getpid(), signal.SIGTERM)

_wd = threading.Thread(target=_watchdog, daemon=True, name="ttube-watchdog")
_wd.start()


# ── Routes – static ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    resp = send_from_directory(_STATIC, "index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.route("/static/<path:filename>")
def static_files(filename):
    resp = send_from_directory(_STATIC, filename)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


# ── Routes – API ─────────────────────────────────────────────────────────────

@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    _st.last_hb = time.time()
    return jsonify({"ok": True})


@app.route("/api/status")
def status():
    _st.last_hb = time.time()
    s   = _st
    pos = s.player.position_seconds() if s.playing or s.paused else None
    dur = s.player.duration_seconds()
    buf = s.player.buffered_seconds() if s.playing else 0.0
    lvl = list(s.player.levels())

    if s.playing and not s.paused and pos is not None and dur and pos >= dur - 0.3:
        s.playing = False

    job    = s.dl.current
    dl_out = None
    if job:
        dl_out = {"status": job.status, "progress": job.progress,
                  "display": job.display, "path": job.path, "error": job.error}
        if job.status in ("done", "error"):
            s.dl.current = None

    cur_lyric = ""
    if s.lyrics_lines and pos is not None:
        for line in s.lyrics_lines:
            if line.start_time <= pos < line.end_time:
                cur_lyric = line.text
                break

    return jsonify({
        "playing":       s.playing,
        "paused":        s.paused,
        "loading":       s.loading,
        "meta_loading":  s.meta_loading,
        "title":         s.title,
        "artist":        s.artist,
        "album":         s.album,
        "artwork":       s.artwork,
        "channels":      s.channels,
        "channel_label": _ch(s.channels),
        "position":      pos,
        "duration":      dur,
        "buffered":      buf,
        "pos_fmt":       _fmt(pos),
        "dur_fmt":       _fmt(dur),
        "levels":        lvl,
        "error":         s.error,
        "current_vid":   s.vid,
        "lyric":         cur_lyric,
        "download":      dl_out,
        "offline":       bool(s.dl.find_local(s.vid)) if s.vid else False,
    })


@app.route("/api/search", methods=["POST"])
def search():
    q = (request.json or {}).get("query", "").strip()
    if not q: return jsonify({"results": [], "error": ""})
    try:
        results = search_youtube(q, 10)
        return jsonify({"results": [
            {"title": r.title, "video_id": r.video_id,
             "webpage_url": r.webpage_url,
             "offline": bool(_st.dl.find_local(r.video_id))}
            for r in results
        ], "error": ""})
    except Exception as e:
        return jsonify({"results": [], "error": str(e)[:160]})


@app.route("/api/suggestions")
def suggestions():
    q   = request.args.get("q", "").strip()
    raw = _itunes_sugg(q, 6) if len(q) >= 2 else []
    return jsonify({"results": [
        {"track":   t.get("trackName",  ""),
         "artist":  t.get("artistName", ""),
         "artwork": t.get("artworkUrl100", "")}
        for t in raw
    ]})


@app.route("/api/play", methods=["POST"])
def play():
    data  = request.json or {}
    vid   = data.get("video_id",   "")
    url   = data.get("webpage_url","")
    title = data.get("title",      "")
    artist_name = data.get("artist", "")
    filename = data.get("filename", "")
    quality = data.get("quality", "standard")

    if artist_name:
        record_artist(artist_name)

    local = None
    if filename:
        p = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(p):
            local = p
            vid = vid or f"local_{filename}"
            url = url or "local"
    else:
        local = _st.dl.find_local(vid)

    if not url:
        return jsonify({"ok": False, "error": "No URL"})

    _st.loading  = not bool(local)
    _st.meta_loading = True
    _st.playing  = False
    _st.paused   = False
    _st.title    = title
    _st.artist   = ""
    _st.album    = ""
    _st.artwork  = ""
    _st.channels = 2
    _st.error    = ""
    _st.vid      = vid
    _st.webpage_url = url
    _st.lyrics_lines = []
    _st._gen += 1
    gen = _st._gen

    def _do() -> None:
        try:
            nonlocal local
            if not local:
                local = _st.dl.find_local(vid) if vid else None
            if local:
                _st.player.stop()
                _st.artwork = ""
                _st.lyrics_lines = []
                try:
                    audio = mutagen.mp3.MP3(local)
                    dur = audio.info.length if audio.info else None
                    _st.title = str(audio.get("TIT2", title))
                    _st.artist = str(audio.get("TPE1", artist))
                    for tag in audio.tags.values() if audio.tags else []:
                        if tag.FrameID == 'APIC':
                            _st.artwork = f"/api/local_artwork?f={urllib.parse.quote(os.path.basename(local))}"
                            break
                except Exception: dur = None
                _st.player.play(local, None, duration_seconds=dur)
                _st.playing = True
                _st.loading = False
                _st.meta_loading = False
                vtt_path = os.path.splitext(local)[0] + ".en.vtt"
                if not os.path.exists(vtt_path): vtt_path = os.path.splitext(local)[0] + ".vtt"
                if os.path.exists(vtt_path):
                    try:
                        with open(vtt_path, "r", encoding="utf-8") as f:
                            _st.lyrics_lines = _parse_vtt_subtitles(f.read())
                    except Exception: pass
            else:
                surl, hdrs, dur, resolved_title, ch = _resolve(url, quality=quality)
                if gen != _st._gen: return
                _st.player.stop()
                _st.player.play(surl, hdrs, duration_seconds=dur)
                _st.title    = resolved_title
                _st.channels = ch
                _st.playing  = True
                _st.loading  = False

            # Check metadata cache first
            c_meta = get_meta_cache(_st.title)
            if c_meta and gen == _st._gen:
                _st.title = c_meta.get("title", _st.title)
                _st.artist = c_meta.get("artist", "")
                _st.album = c_meta.get("album", "")
                _st.artwork = c_meta.get("artwork", "")
                _st.meta_loading = False
            else:
                meta = match_metadata(_st.title)
                if gen == _st._gen:
                    if meta:
                        if meta.title:       _st.title   = meta.title
                        if meta.artist:      _st.artist  = meta.artist
                        if meta.album:       _st.album   = meta.album
                        if meta.artwork_url: _st.artwork = meta.artwork_url
                        set_meta_cache(_st.title, {
                            "title": _st.title, "artist": _st.artist,
                            "album": _st.album, "artwork": _st.artwork
                        })
                    _st.meta_loading = False

            try:
                lyr = fetch_lyrics(url)
                if lyr and gen == _st._gen:
                    _st.lyrics_lines = lyr.lines
            except Exception: pass

        except Exception as exc:
            _st.error   = str(exc)[:160]
            _st.loading = False
            _st.meta_loading = False
            _st.playing = False

    _st._ex.submit(_do)
    return jsonify({"ok": True})


@app.route("/api/pause", methods=["POST"])
def pause():
    _st.player.toggle_pause()
    _st.paused = _st.player.is_paused()
    return jsonify({"ok": True, "paused": _st.paused})


@app.route("/api/stop", methods=["POST"])
def stop():
    _st.player.stop()
    _st._gen   += 1
    _st.playing = False
    _st.paused  = False
    _st.loading = False
    _st.meta_loading = False
    _st.title = _st.artist = _st.album = _st.artwork = _st.error = ""
    _st.vid = _st.webpage_url = ""
    _st.channels = 2
    _st.lyrics_lines = []
    return jsonify({"ok": True})


@app.route("/api/seek", methods=["POST"])
def seek():
    pos = (request.json or {}).get("position")
    if pos is not None and (_st.playing or _st.paused):
        _st._ex.submit(_st.player.seek_to, float(pos))
    return jsonify({"ok": True})


@app.route("/api/seek_rel", methods=["POST"])
def seek_rel():
    delta = (request.json or {}).get("delta", 0)
    if _st.playing or _st.paused:
        _st._ex.submit(_st.player.seek_relative, float(delta))
    return jsonify({"ok": True})


# ── Download & Library ────────────────────────────────────────────────────────

@app.route("/api/download", methods=["POST"])
def download():
    data   = request.json or {}
    vid    = data.get("video_id",    "")
    url    = data.get("webpage_url", "")
    title  = data.get("title",   "")
    artist = data.get("artist",  "") or _st.artist
    if not url: return jsonify({"ok": False, "error": "No URL"})
    if _st.dl.find_local(vid):
        return jsonify({"ok": True, "already": True, "path": _st.dl.find_local(vid)})
    _st.dl.start(vid, url, title, artist)
    
    # Auto add to Liked Songs
    track = PlTrack(title=title, video_id=vid, webpage_url=url, artist=artist, artwork_url=_st.artwork)
    add_to_playlist("Liked Songs", track)
    
    return jsonify({"ok": True})


@app.route("/api/library")
def library():
    tracks = []
    if os.path.isdir(DOWNLOAD_DIR):
        for fname in sorted(os.listdir(DOWNLOAD_DIR)):
            if fname.endswith(".mp3"):
                path  = os.path.join(DOWNLOAD_DIR, fname)
                parts = fname[:-4].split(" - ", 1)
                
                art = ""
                t = parts[1].strip() if len(parts) == 2 else fname[:-4]
                a = parts[0].strip() if len(parts) == 2 else ""
                
                try:
                    audio = mutagen.mp3.MP3(path)
                    t = str(audio.get("TIT2", t))
                    a = str(audio.get("TPE1", a))
                    for tag in audio.tags.values() if audio.tags else []:
                        if tag.FrameID == 'APIC':
                            art = f"/api/local_artwork?f={urllib.parse.quote(fname)}"
                            break
                except Exception: pass
                
                tracks.append({
                    "filename": fname,
                    "path":     path,
                    "artist":   a,
                    "title":    t,
                    "artwork":  art,
                    "size_mb":  round(os.path.getsize(path) / 1e6, 1),
                })
    return jsonify({"tracks": tracks})

@app.route("/api/local_artwork")
def local_artwork():
    filename = request.args.get("f", "")
    p = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(p):
        try:
            audio = mutagen.mp3.MP3(p)
            for tag in audio.tags.values() if audio.tags else []:
                if tag.FrameID == 'APIC':
                    return Response(tag.data, mimetype=tag.mime)
        except Exception: pass
    return Response(status=404)


@app.route("/api/library/delete", methods=["POST"])
def library_delete():
    filename = (request.json or {}).get("filename", "")
    if filename:
        p = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(p):
            os.remove(p)
            return jsonify({"ok": True})
    return jsonify({"ok": False})


# ── Playlists ─────────────────────────────────────────────────────────────────

@app.route("/api/playlists", methods=["GET"])
def get_playlists():
    return jsonify({"playlists": [{"name": pl.name, "count": len(pl.tracks)} for pl in list_playlists()]})

@app.route("/api/playlists", methods=["POST"])
def create_playlist():
    name = (request.json or {}).get("name", "").strip()
    if not name: return jsonify({"ok": False, "error": "Name required"})
    save_playlist(Playlist(name=name))
    return jsonify({"ok": True, "name": name})

@app.route("/api/playlists/<name>", methods=["GET"])
def get_playlist(name: str):
    pl = load_playlist(name)
    if not pl: return jsonify({"error": "Not found"}), 404
    return jsonify({"name": pl.name, "tracks": [t.to_dict() for t in pl.tracks]})

@app.route("/api/playlists/<name>", methods=["DELETE"])
def del_playlist(name: str):
    delete_playlist(name)
    return jsonify({"ok": True})

@app.route("/api/playlists/<name>/add", methods=["POST"])
def pl_add(name: str):
    data = request.json or {}
    track = PlTrack(
        title       = data.get("title",       ""),
        video_id    = data.get("video_id",     ""),
        webpage_url = data.get("webpage_url",  ""),
        artist      = data.get("artist",  "") or _st.artist,
        artwork_url = data.get("artwork_url", "") or _st.artwork,
    )
    pl = add_to_playlist(name, track)
    return jsonify({"ok": True, "count": len(pl.tracks)})

@app.route("/api/playlists/<name>/remove", methods=["POST"])
def pl_remove(name: str):
    vid = (request.json or {}).get("video_id", "")
    remove_from_playlist(name, vid)
    return jsonify({"ok": True})


# ── Trending & Artists ────────────────────────────────────────────────────────

@app.route("/api/trending")
def trending():
    try:
        req = urllib.request.Request("https://itunes.apple.com/us/rss/topsongs/limit=100/json", headers={"User-Agent": "TTube/0.2"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.load(r)
            results = []
            for e in data.get("feed", {}).get("entry", []):
                title = e.get("im:name", {}).get("label", "")
                artist = e.get("im:artist", {}).get("label", "")
                images = e.get("im:image", [])
                art = images[-1].get("label", "").replace("170x170bb", "600x600bb") if images else ""
                results.append({"title": title, "artist": artist, "artwork": art})
            if len(results) > 20:
                results = random.sample(results, 20)
            return jsonify({"results": results})
    except Exception: return jsonify({"results": []})

@app.route("/api/top_artists_tracks")
def top_artists_tracks():
    hist = get_artist_history()
    
    if not hist:
        default_artists = ["The Weeknd", "Taylor Swift", "Drake", "Ed Sheeran", "Ariana Grande", "Bad Bunny", "Billie Eilish"]
        for da in default_artists:
            hist[da] = random.randint(10, 50)
            
    top_artists = sorted(hist.items(), key=lambda x: x[1], reverse=True)[:3]
    results = []
    try:
        for artist, _ in top_artists:
            term = urllib.parse.quote(artist)
            req = urllib.request.Request(f"https://itunes.apple.com/search?term={term}&entity=song&limit=7", headers={"User-Agent": "TTube/0.2"})
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.load(r)
                for t in data.get("results", []):
                    art = t.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                    results.append({
                        "title": t.get("trackName", ""),
                        "artist": t.get("artistName", ""),
                        "artwork": art
                    })
        # Shuffle a bit so it's fresh
        random.shuffle(results)
        return jsonify({"results": results[:15]})
    except Exception:
        return jsonify({"results": results[:15]})


@app.route("/api/top_artists_list")
def top_artists_list():
    hist = get_artist_history()
    followed = get_followed_artists()
    
    # Merge history with followed (give followed a base count)
    for f in followed:
        hist[f] = hist.get(f, 0) + 5
        
    if not hist:
        default_artists = ["The Weeknd", "Taylor Swift", "Drake", "Ed Sheeran", "Ariana Grande", "Bad Bunny", "Billie Eilish"]
        for da in default_artists:
            hist[da] = random.randint(10, 50)
            
    top_artists = sorted(hist.items(), key=lambda x: x[1], reverse=True)[:10]
    results = []
    
    def fetch_artist_art(artist):
        try:
            term = urllib.parse.quote(artist)
            req = urllib.request.Request(f"https://itunes.apple.com/search?term={term}&entity=musicArtist&limit=1", headers={"User-Agent": "TTube/0.2"})
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.load(r)
                if data.get("results"):
                    # itunes often doesn't have great artist images, but we can try to find an album
                    req2 = urllib.request.Request(f"https://itunes.apple.com/search?term={term}&entity=album&limit=1", headers={"User-Agent": "TTube/0.2"})
                    with urllib.request.urlopen(req2, timeout=3) as r2:
                        d2 = json.load(r2)
                        if d2.get("results"):
                            return d2["results"][0].get("artworkUrl100", "").replace("100x100bb", "600x600bb")
        except Exception: pass
        return ""

    for artist, _ in top_artists:
        results.append({
            "name": artist,
            "image": fetch_artist_art(artist)
        })
        
    return jsonify({"results": results})

@app.route("/api/artists", methods=["GET"])
def get_artists():
    return jsonify({"artists": get_followed_artists()})

@app.route("/api/artists", methods=["POST"])
def follow_artist():
    name = (request.json or {}).get("name", "").strip()
    if name:
        arts = get_followed_artists()
        if name not in arts:
            arts.append(name)
            save_followed_artists(arts)
    return jsonify({"ok": True})

@app.route("/api/artists/<name>/unfollow", methods=["POST"])
def unfollow_artist(name: str):
    arts = get_followed_artists()
    if name in arts:
        arts.remove(name)
        save_followed_artists(arts)
    return jsonify({"ok": True})

@app.route("/api/artists/<name>")
def artist_profile(name: str):
    # Fetch top tracks for artist via iTunes
    try:
        term = urllib.parse.quote(name)
        req = urllib.request.Request(f"https://itunes.apple.com/search?term={term}&entity=song&limit=20", headers={"User-Agent": "TTube/0.2"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.load(r)
            results = []
            for t in data.get("results", []):
                art = t.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                results.append({
                    "title": t.get("trackName", ""),
                    "artist": t.get("artistName", ""),
                    "artwork": art
                })
            return jsonify({"name": name, "tracks": results})
    except Exception: return jsonify({"name": name, "tracks": []})


# ── Artwork proxy ─────────────────────────────────────────────────────────────

@app.route("/api/artwork")
def artwork_proxy():
    url = request.args.get("url", "")
    if not url: return Response(status=400)
    
    # Check if we have it cached locally
    os.makedirs(ART_DIR, exist_ok=True)
    c_path = os.path.join(ART_DIR, hashlib.md5(url.encode()).hexdigest() + ".jpg")
    
    if os.path.exists(c_path):
        with open(c_path, "rb") as f: data = f.read()
        resp = Response(data, content_type="image/jpeg")
        resp.headers["Cache-Control"] = "public, max-age=31536000"
        return resp

    allowed = ("itunes.apple.com", "mzstatic.com", "is1-ssl.mzstatic.com",
               "is2-ssl.mzstatic.com", "is3-ssl.mzstatic.com",
               "is4-ssl.mzstatic.com", "is5-ssl.mzstatic.com")
    if not any(d in url for d in allowed): return Response(status=400)
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TTube/0.2"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "image/jpeg")
        
        # Save to cache
        with open(c_path, "wb") as f: f.write(data)
        
        resp = Response(data, content_type=ct)
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception:
        return Response(status=404)

@app.route("/api/erase_data", methods=["POST"])
def erase_data():
    try:
        ttube_dir = os.path.join(os.path.expanduser("~"), "Music", "TTube")
        if os.path.exists(ttube_dir):
            import shutil
            shutil.rmtree(ttube_dir)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
