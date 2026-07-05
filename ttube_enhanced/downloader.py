"""
Offline download manager for TTube Enhanced.

Downloads the selected track as a high-quality MP3 (320 kbps) with:
  - Embedded album artwork
  - Embedded ID3 metadata (title, artist, album)
  - A companion .vtt lyrics/subtitle file

Downloads land in  ~/Music/TTube/  by default.

Offline playback: once a video_id is in the local registry the app
will play the local MP3 file instead of streaming from YouTube.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

import yt_dlp


# ── Configuration ─────────────────────────────────────────────────────────────

DOWNLOAD_DIR: str = os.path.join(os.path.expanduser("~"), "Music", "TTube")


# ── Job state ─────────────────────────────────────────────────────────────────

@dataclass
class DownloadJob:
    video_id: str
    display:  str           # "Artist - Title" label for UI
    status:   str = "queued"  # queued | downloading | postprocessing | done | error
    progress: int = 0         # 0-100 while downloading
    path:     str = ""        # absolute path to finished file
    error:    str = ""


# ── Manager ───────────────────────────────────────────────────────────────────

class DownloadManager:
    """
    Thread-safe download manager.  One job runs at a time; the current
    job's state is polled by the draw loop.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, str] = {}   # video_id → file path
        self._lock     = threading.Lock()
        self.current:  Optional[DownloadJob] = None

    # ── Public ────────────────────────────────────────────────────────────────

    def find_local(self, video_id: str) -> Optional[str]:
        """Return the local file path if this video has already been downloaded."""
        with self._lock:
            path = self._registry.get(video_id)
        if path and os.path.exists(path):
            return path
        return None

    def start(
        self,
        video_id:    str,
        webpage_url: str,
        title:       str,
        artist:      str,
    ) -> DownloadJob:
        """
        Begin an async download.  Returns the DownloadJob immediately so
        the caller can display status.  Previous job is replaced.
        """
        label = f"{artist} – {title}" if artist else title
        job   = DownloadJob(video_id=video_id, display=label)
        self.current = job

        thread = threading.Thread(
            target=self._run,
            args=(job, webpage_url, title, artist),
            daemon=True,
        )
        thread.start()
        return job

    # ── Private ───────────────────────────────────────────────────────────────

    def _run(
        self,
        job:         DownloadJob,
        webpage_url: str,
        title:       str,
        artist:      str,
    ) -> None:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        # Safe filename: strip path-unsafe characters
        def safe(s: str) -> str:
            return re.sub(r'[<>:"/\\|?*]', "", s).strip()[:80]

        if artist and title:
            stem = f"{safe(artist)} - {safe(title)}"
        else:
            stem = "%(title)s"

        out_tmpl = os.path.join(DOWNLOAD_DIR, stem + ".%(ext)s")

        def _progress_hook(d: dict) -> None:
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done  = d.get("downloaded_bytes", 0)
                job.progress = int(done / total * 100) if total else 0
                job.status   = "downloading"
            elif d["status"] == "finished":
                job.status   = "postprocessing"
                job.progress = 100

        ydl_opts: dict = {
            "quiet":         True,
            "no_warnings":   True,
            "format":        "bestaudio/best",
            "outtmpl":       out_tmpl,
            "noplaylist":    True,
            "progress_hooks":[_progress_hook],
            # Audio conversion → MP3 320 kbps
            "postprocessors": [
                {
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   "mp3",
                    "preferredquality": "320",
                },
                {
                    "key":          "FFmpegMetadata",
                    "add_metadata": True,
                },
                {
                    "key": "EmbedThumbnail",
                },
            ],
            # Lyrics / subtitles
            "writesubtitles":     True,
            "writeautomaticsub":  True,
            "subtitleslangs":     ["en"],
            "subtitlesformat":    "vtt",
            # Artwork for embedding
            "writethumbnail":    True,
            "embedthumbnail":    True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(webpage_url, download=True)
                raw_path = ydl.prepare_filename(info)

            # Postprocessor changes extension to .mp3
            base = os.path.splitext(raw_path)[0]
            mp3  = base + ".mp3"

            if os.path.exists(mp3):
                job.path   = mp3
                job.status = "done"
                with self._lock:
                    self._registry[job.video_id] = mp3
            else:
                # Try to find any matching file
                for fname in os.listdir(DOWNLOAD_DIR):
                    if fname.endswith(".mp3") and safe(title)[:20] in fname:
                        full = os.path.join(DOWNLOAD_DIR, fname)
                        job.path   = full
                        job.status = "done"
                        with self._lock:
                            self._registry[job.video_id] = full
                        break
                else:
                    job.status = "error"
                    job.error  = "Output file not found after download"

        except Exception as exc:
            job.status = "error"
            job.error  = str(exc)[:120]
