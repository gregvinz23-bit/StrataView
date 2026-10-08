"""Segmented MP4 recorder: pulls frames from a source, writes time chunks."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

import cv2

from .backends import BaseSource
from .storage import camera_dir


class SegmentRecorder:
    """Records `source` into `segment_seconds`-long MP4 files.

    Runs its own thread grabbing the latest frame at `fps`. If the
    camera drops, the current segment is closed and a new one starts
    when frames return.
    """

    def __init__(
        self,
        source: BaseSource,
        segment_seconds: int = 600,
        fps: float = 10.0,
    ):
        self.source = source
        self.segment_seconds = max(30, int(segment_seconds))
        self.fps = fps
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._writer: cv2.VideoWriter | None = None
        self._writer_size: tuple[int, int] | None = None
        self._segment_start = 0.0
        self._lock = threading.Lock()
        self.current_file: Path | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name=f"rec-{self.source.name}", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self._close_writer()

    # -- internals ------------------------------------------------------
    def _clip_path(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return camera_dir(self.source.name) / f"{stamp}.mp4"

    def _open_writer(self, frame) -> None:
        h, w = frame.shape[:2]
        size = (w, h)
        if self._writer is not None and self._writer_size == size:
            return
        self._close_writer()
        path = self._clip_path()
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, self.fps, size)
        if not writer.isOpened():
            return
        self._writer = writer
        self._writer_size = size
        self.current_file = path
        self._segment_start = time.time()

    def _close_writer(self) -> None:
        with self._lock:
            if self._writer is not None:
                try:
                    self._writer.release()
                except Exception:
                    pass
                self._writer = None
                self._writer_size = None

    def _loop(self) -> None:
        interval = 1.0 / max(0.5, self.fps)
        while not self._stop.is_set():
            frame = self.source.latest()
            if frame is None:
                # No signal: close segment, wait for frames to return.
                self._close_writer()
                self._stop.wait(0.5)
                continue
            self._open_writer(frame)
            if self._writer is None:
                self._stop.wait(0.5)
                continue
            if time.time() - self._segment_start >= self.segment_seconds:
                self._close_writer()
                self._open_writer(frame)
                if self._writer is None:
                    self._stop.wait(0.5)
                    continue
            try:
                with self._lock:
                    if self._writer is not None:
                        self._writer.write(frame)
            except Exception:
                self._close_writer()
            self._stop.wait(interval)
        self._close_writer()
