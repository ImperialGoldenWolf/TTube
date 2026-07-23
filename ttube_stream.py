from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
import queue




def _resolve_ffmpeg_exe(ffmpeg: str) -> str:
    path = shutil.which(ffmpeg)
    if path:
        return path

    # Optional fallback that downloads/locates a bundled ffmpeg binary.
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


@dataclass
class AudioFormat:
    samplerate: int = 48000
    channels: int = 2
    sample_width_bytes: int = 2  # s16le

    @property
    def bytes_per_frame(self) -> int:
        return self.channels * self.sample_width_bytes


class RingBuffer:
    def __init__(self, capacity_bytes: int):
        if capacity_bytes <= 0:
            raise ValueError("capacity_bytes must be > 0")
        self._buf = bytearray(capacity_bytes)
        self._cap = capacity_bytes
        self._r = 0
        self._w = 0
        self._size = 0
        self._cv = threading.Condition()

    def clear(self) -> None:
        with self._cv:
            self._r = self._w = self._size = 0
            self._cv.notify_all()

    def available(self) -> int:
        with self._cv:
            return self._size

    def write_blocking(self, data: bytes, stop_event: threading.Event) -> None:
        mv = memoryview(data)
        offset = 0
        while offset < len(data) and not stop_event.is_set():
            with self._cv:
                while self._size >= self._cap and not stop_event.is_set():
                    self._cv.wait(timeout=0.05)
                if stop_event.is_set():
                    return

                free = self._cap - self._size
                n = min(free, len(data) - offset)

                first = min(n, self._cap - self._w)
                self._buf[self._w : self._w + first] = mv[offset : offset + first]
                self._w = (self._w + first) % self._cap
                self._size += first
                offset += first

                remaining = n - first
                if remaining:
                    self._buf[self._w : self._w + remaining] = mv[offset : offset + remaining]
                    self._w = (self._w + remaining) % self._cap
                    self._size += remaining
                    offset += remaining

                self._cv.notify_all()

    def read_nonblocking(self, nbytes: int) -> bytes:
        if nbytes <= 0:
            return b""
        with self._cv:
            n = min(nbytes, self._size)
            if n == 0:
                return b""

            out = bytearray(n)
            first = min(n, self._cap - self._r)
            out[0:first] = self._buf[self._r : self._r + first]
            self._r = (self._r + first) % self._cap
            self._size -= first

            remaining = n - first
            if remaining:
                out[first:first + remaining] = self._buf[self._r : self._r + remaining]
                self._r = (self._r + remaining) % self._cap
                self._size -= remaining

            self._cv.notify_all()
            return bytes(out)


class StreamPlayer:
    def __init__(
        self,
        ffmpeg: str = "ffmpeg",
        audio_format: AudioFormat | None = None,
        buffer_seconds: float = 6.0,
    ):
        self._ffmpeg = ffmpeg
        self._fmt = audio_format or AudioFormat()
        self._buffer_seconds = float(buffer_seconds)

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._paused = threading.Event()

        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._reader: Optional[threading.Thread] = None
        self._buf: Optional[RingBuffer] = None
        self._sd_stream = None

        # Playback timeline
        self._stream_url: str | None = None
        self._http_headers: Dict[str, str] | None = None
        self._duration_seconds: float | None = None
        self._seek_offset_seconds: float = 0.0
        self._played_frames: int = 0

        # Simple visualizer (peak meter), updated from the audio callback.
        self._viz_levels: tuple[float, float] = (0.0, 0.0)
        self._viz_stride_frames: int = 4  # sample every N frames for cheap peak estimation
        self._viz_decay: float = 0.85



    def is_active(self) -> bool:
        return self._sd_stream is not None

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def levels(self) -> tuple[float, float]:
        return self._viz_levels



    def toggle_pause(self) -> None:
        if self._paused.is_set():
            self.resume()
        else:
            self.pause()

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()

            # Stop audio first so callbacks stop touching the ring buffer.
            if self._sd_stream is not None:
                try:
                    self._sd_stream.stop()
                except Exception:
                    pass
                try:
                    self._sd_stream.close()
                except Exception:
                    pass
                self._sd_stream = None

            if self._proc is not None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass

            if self._reader is not None:
                self._reader.join(timeout=1.0)
                self._reader = None


            if self._proc is not None:
                try:
                    self._proc.kill()
                except Exception:
                    pass
                self._proc = None

            if self._buf is not None:
                self._buf.clear()
                self._buf = None

            self._paused.clear()
            self._stop.clear()

            self._stream_url = None
            self._http_headers = None
            self._duration_seconds = None
            self._seek_offset_seconds = 0.0
            self._played_frames = 0
            self._viz_levels = (0.0, 0.0)


    def play(
        self,
        stream_url: str,
        http_headers: Dict[str, str] | None = None,
        *,
        start_seconds: float = 0.0,
        duration_seconds: float | None = None,
        start_paused: bool = False,
    ) -> None:
        """Start streaming playback from a direct media URL."""
        with self._lock:
            self.stop()

            if start_paused:
                self._paused.set()

            self._stream_url = stream_url
            self._http_headers = dict(http_headers) if http_headers else None
            self._duration_seconds = float(duration_seconds) if duration_seconds is not None else None
            self._seek_offset_seconds = max(0.0, float(start_seconds))
            self._played_frames = 0

            ffmpeg_exe = _resolve_ffmpeg_exe(self._ffmpeg)
            if not ffmpeg_exe:
                raise RuntimeError(
                    "ffmpeg not found. Install ffmpeg (and ensure it's on PATH) "
                    "or install the Python fallback dependency: imageio-ffmpeg."
                )

            # Lazy import so the module can be imported without sounddevice installed.
            import sounddevice as sd

            cap = int(self._fmt.samplerate * self._fmt.bytes_per_frame * self._buffer_seconds)
            self._buf = RingBuffer(max(cap, 64 * 1024))

            headers_arg = ""
            if http_headers:
                # ffmpeg expects CRLF-separated header lines.
                headers_arg = "\r\n".join([f"{k}: {v}" for k, v in http_headers.items() if k and v is not None])
                if headers_arg:
                    headers_arg += "\r\n"

            cmd = [
                ffmpeg_exe,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "quiet",  # quiet so stderr is purely raw video
                "-rtbufsize",
                "2M",
            ]
            if stream_url.startswith("http"):
                cmd += [
                    "-reconnect", "1",
                    "-reconnect_streamed", "1",
                    "-reconnect_delay_max", "10",
                ]
            
            if headers_arg:
                cmd += ["-headers", headers_arg]

            # Seek: best-effort. For HTTP sources this often works via Range requests.
            if self._seek_offset_seconds > 0:
                cmd += ["-ss", str(self._seek_offset_seconds)]

            cmd += [
                "-i",
                stream_url,
                "-map", "0:a:0?",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ac",
                str(self._fmt.channels),
                "-ar",
                str(self._fmt.samplerate),
                "pipe:1",
            ]
            


            import sys
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                bufsize=0,
            )

            bytes_per_frame = self._fmt.bytes_per_frame

            def reader_loop() -> None:
                assert self._proc is not None
                assert self._proc.stdout is not None
                assert self._buf is not None

                stdout = self._proc.stdout
                carry = b""
                try:
                    while not self._stop.is_set():
                        if self._paused.is_set():
                            time.sleep(0.02)
                            continue

                        chunk = stdout.read(16 * 1024)
                        if not chunk:
                            break

                        if carry:
                            chunk = carry + chunk
                            carry = b""

                        aligned = (len(chunk) // bytes_per_frame) * bytes_per_frame
                        if aligned:
                            self._buf.write_blocking(chunk[:aligned], self._stop)
                        carry = chunk[aligned:]
                finally:
                    try:
                        stdout.close()
                    except Exception:
                        pass

            self._reader = threading.Thread(target=reader_loop, name="ttube-ffmpeg-reader", daemon=True)
            self._reader.start()



            bytes_per_frame = self._fmt.bytes_per_frame

            def callback(outdata, frames, _time, _status):
                # outdata is a raw byte buffer for RawOutputStream.
                nbytes = int(frames) * bytes_per_frame

                if self._paused.is_set() or self._stop.is_set() or self._buf is None:
                    # Decay the meter towards silence.
                    l, r = self._viz_levels
                    self._viz_levels = (l * 0.80, r * 0.80)
                    outdata[:] = b"\x00" * nbytes
                    return

                data = self._buf.read_nonblocking(nbytes)

                # Update a simple peak meter from the most recent PCM chunk.
                if data:
                    stride = max(1, int(self._viz_stride_frames))
                    ch = int(self._fmt.channels)
                    peak_l = 0
                    peak_r = 0

                    if sys.byteorder == "little":
                        samples = memoryview(data).cast("h")
                        if ch == 1:
                            step = stride
                            for i in range(0, len(samples), step):
                                v = samples[i]
                                if v < 0:
                                    v = -v
                                if v > peak_l:
                                    peak_l = v
                            peak_r = peak_l
                        elif ch == 2:
                            step = 2 * stride
                            end = len(samples) - 1
                            for i in range(0, end, step):
                                v = samples[i]
                                if v < 0:
                                    v = -v
                                if v > peak_l:
                                    peak_l = v

                                v = samples[i + 1]
                                if v < 0:
                                    v = -v
                                if v > peak_r:
                                    peak_r = v
                        else:
                            # Fallback: peak across all channels.
                            step = ch * stride
                            end = len(samples) - (ch - 1)
                            for i in range(0, end, step):
                                for j in range(ch):
                                    v = samples[i + j]
                                    if v < 0:
                                        v = -v
                                    if v > peak_l:
                                        peak_l = v
                            peak_r = peak_l
                    else:
                        # Rare: big-endian host. Decode s16le manually.
                        mv = memoryview(data)
                        bps = 2
                        if ch == 1:
                            step_b = bps * stride
                            for off in range(0, len(mv) - 1, step_b):
                                v = int.from_bytes(mv[off : off + 2], "little", signed=True)
                                if v < 0:
                                    v = -v
                                if v > peak_l:
                                    peak_l = v
                            peak_r = peak_l
                        elif ch == 2:
                            step_b = (bps * ch) * stride
                            end = len(mv) - 3
                            for off in range(0, end, step_b):
                                v = int.from_bytes(mv[off : off + 2], "little", signed=True)
                                if v < 0:
                                    v = -v
                                if v > peak_l:
                                    peak_l = v

                                v = int.from_bytes(mv[off + 2 : off + 4], "little", signed=True)
                                if v < 0:
                                    v = -v
                                if v > peak_r:
                                    peak_r = v
                        else:
                            step_b = (bps * ch) * stride
                            end = len(mv) - (bps * ch - 1)
                            for off in range(0, end, step_b):
                                for j in range(ch):
                                    o = off + j * bps
                                    v = int.from_bytes(mv[o : o + 2], "little", signed=True)
                                    if v < 0:
                                        v = -v
                                    if v > peak_l:
                                        peak_l = v
                            peak_r = peak_l

                    norm = 32768.0
                    raw_l = min(1.0, peak_l / norm)
                    raw_r = min(1.0, peak_r / norm)
                    prev_l, prev_r = self._viz_levels
                    decay = float(self._viz_decay)
                    lvl_l = raw_l if raw_l > prev_l else prev_l * decay
                    lvl_r = raw_r if raw_r > prev_r else prev_r * decay
                    self._viz_levels = (lvl_l, lvl_r)
                else:
                    l, r = self._viz_levels
                    d = float(self._viz_decay)
                    self._viz_levels = (l * d, r * d)

                played_frames = len(data) // bytes_per_frame
                self._played_frames += played_frames

                if len(data) < nbytes:
                    data += b"\x00" * (nbytes - len(data))
                outdata[:] = data

            self._sd_stream = sd.RawOutputStream(
                samplerate=self._fmt.samplerate,
                channels=self._fmt.channels,
                dtype="int16",
                callback=callback,
            )
            self._sd_stream.start()

    def buffered_seconds(self) -> float:
        buf = self._buf
        if buf is None:
            return 0.0
        bytes_available = buf.available()
        denom = float(self._fmt.bytes_per_frame * self._fmt.samplerate)
        return float(bytes_available) / denom if denom else 0.0

    def position_seconds(self) -> float:
        return float(self._seek_offset_seconds) + (float(self._played_frames) / float(self._fmt.samplerate))

    def duration_seconds(self) -> float | None:
        return self._duration_seconds

    def seek_to(self, seconds: float) -> None:
        with self._lock:
            if self._stream_url is None:
                return

            # Clamp if we know duration.
            target = max(0.0, float(seconds))
            if self._duration_seconds is not None:
                target = min(target, max(0.0, float(self._duration_seconds)))

            was_paused = self._paused.is_set()
            stream_url = self._stream_url
            headers = self._http_headers
            duration = self._duration_seconds

        # Restart via play() (fastest path). Keep pause state if currently paused.
        self.play(
            stream_url,
            http_headers=headers,
            start_seconds=target,
            duration_seconds=duration,
            start_paused=was_paused,
        )

    def seek_relative(self, delta_seconds: float) -> None:
        self.seek_to(self.position_seconds() + float(delta_seconds))
