"""
Camera capture module with threading support.
Author: А. Свидович / А. Петляков для PROGRESS
"""
import cv2
import threading
import time
import numpy as np
from typing import Optional
from config import CONFIG


class CameraCapture:
    """Threaded camera capture for continuous scanning."""

    def __init__(self, camera_index: int = CONFIG.CAMERA_INDEX):
        self.camera_index = camera_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._fps = 0.0
        self._frame_count = 0
        self._fps_start_time = time.time()
        self._last_frame_time = 0.0

    def open(self) -> bool:
        """Open the camera."""
        try:
            self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                # Try VFW backend
                self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_VFW)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                return False

            # Set resolution
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG.CAMERA_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG.CAMERA_HEIGHT)
            self._cap.set(cv2.CAP_PROP_FPS, CONFIG.CAMERA_FPS)

            # Try to set additional properties
            try:
                self._cap.set(cv2.CAP_PROP_FOURCC,
                               cv2.VideoWriter_fourcc(*'MJPG'))
            except Exception:
                pass

            # Apply settings
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(self._cap.get(cv2.CAP_PROP_FPS))

            return True
        except Exception:
            return False

    def start(self):
        """Start continuous capture in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self):
        """Background capture loop."""
        while self._running:
            if self._cap is not None and self._cap.isOpened():
                ret, frame = self._cap.read()
                if ret:
                    with self._lock:
                        self._frame = frame.copy()
                    self._frame_count += 1
                    now = time.time()
                    self._last_frame_time = now - self._fps_start_time
                    if now - self._fps_start_time >= 1.0:
                        self._fps = self._frame_count / (now - self._fps_start_time)
                        self._frame_count = 0
                        self._fps_start_time = now
                else:
                    # Try to reconnect
                    time.sleep(0.1)
                    self._cap.release()
                    time.sleep(0.5)
                    self._cap = cv2.VideoCapture(self.camera_index)
            else:
                time.sleep(0.05)

    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def get_fps(self) -> float:
        """Get current FPS."""
        return self._fps

    def stop(self):
        """Stop capture and release camera."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def is_opened(self) -> bool:
        """Check if camera is opened."""
        return self._cap is not None and self._cap.isOpened()

    def get_properties(self) -> dict:
        """Get current camera properties."""
        if self._cap is None or not self._cap.isOpened():
            return {}
        return {
            "width": int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": self._fps,
            "backend": self._cap.getBackendName(),
        }

    def __enter__(self):
        self.open()
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
