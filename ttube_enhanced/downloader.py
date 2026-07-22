"""
Download manager – yt-dlp → MP3 320 kbps + embedded artwork + VTT lyrics.
Downloads land in ~/Music/TTube/.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from typing import Dict, Optional

import yt_dlp

DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Music", "TTube")


@dataclass
class DownloadJob:
    video_id: str
    display:  str
    status:   str = "queued"      # queued|downloading|postprocessing|done|error
    progress: int = 0
    path:     str = ""
    error:    str = ""


class DownloadManager:
    def __init__(self) -> None:
        self._registry: Dict[str, str] = {}
        self._lock = threading.Lock()
        self.current: Optional[DownloadJob] = None

    def find_local(self, video_id: str) -> Optional[str]:
        with self._lock:
            path = self._registry.get(video_id)
        return path if path and os.path.exists(path) else None

    def start(self, video_id: str, webpage_url: str,
              title: str, artist: str) -> DownloadJob:
        label = f"{artist} – {title}" if artist else title
        job   = DownloadJob(video_id=video_id, display=label)
        self.current = job
        threading.Thread(target=self._run,
                         args=(job, webpage_url, title, artist),
                         daemon=True).start()
        return job

    def _run(self, job: DownloadJob, url: str, title: str, artist: str) -> None:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        def safe(s: str) -> str:
            return re.sub(r'[<>:"/\\|?*]', "", s).strip()[:80]

        stem    = f"{safe(artist)} - {safe(title)}" if artist and title else "%(title)s"
        out_tpl = os.path.join(DOWNLOAD_DIR, stem + ".%(ext)s")

        def hook(d: dict) -> None:
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done  = d.get("downloaded_bytes", 0)
                job.progress = int(done / total * 100) if total else 0
                job.status   = "downloading"
            elif d["status"] == "finished":
                job.status   = "postprocessing"
                job.progress = 100

        opts = {
            "quiet": True, "no_warnings": True,
            "format": "bestaudio/best", "outtmpl": out_tpl,
            "noplaylist": True, "progress_hooks": [hook],
            "postprocessors": [
                {"key": "FFmpegExtractAudio",
                 "preferredcodec": "mp3", "preferredquality": "320"},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ],
            "writesubtitles": True, "writeautomaticsub": True,
            "subtitleslangs": ["en"], "subtitlesformat": "vtt",
            "writethumbnail": True, "embedthumbnail": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info     = ydl.extract_info(url, download=True)
                raw_path = ydl.prepare_filename(info)
            mp3 = os.path.splitext(raw_path)[0] + ".mp3"
            if os.path.exists(mp3):
                job.path, job.status = mp3, "done"
                with self._lock:
                    self._registry[job.video_id] = mp3
            else:
                job.status = "error"
                job.error  = "Output file not found"
        except Exception as exc:
            job.status = "error"
            job.error  = str(exc)[:120]
