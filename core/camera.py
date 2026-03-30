"""
CameraThread — captures frames in a background QThread, runs the detector,
and emits annotated QImage frames + events to the main (GUI) thread.

Auto-zoom: when a person is detected and their body fills more than
ZOOM_OUT_THRESHOLD of the frame height, the camera's digital zoom is
decreased so more of the scene becomes visible.
"""

from __future__ import annotations

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from core.detector import DetectorResult, SquatDetector

# Fraction of frame height at which we start zooming out
ZOOM_OUT_THRESHOLD = 0.82
# Try to keep body at this fraction after zooming
ZOOM_TARGET_FRACTION = 0.70
# Camera zoom property range (typical USB webcam)
ZOOM_MIN = 100
ZOOM_MAX = 500
ZOOM_STEP = 15          # units to change per adjustment
ZOOM_EVERY_N_FRAMES = 20  # rate-limit zoom changes


class CameraThread(QThread):
    frame_ready = pyqtSignal(QImage)
    person_detected = pyqtSignal(bool)
    rep_counted = pyqtSignal(int)

    def __init__(self, camera_index: int = 0, parent=None) -> None:
        super().__init__(parent)
        self._camera_index = camera_index
        self._running = False
        self._reset_pending = False
        self._last_person_state: bool | None = None
        self._frame_count = 0
        # _detector is created inside run() so its GL context belongs to the camera thread

    def run(self) -> None:
        # Create detector here — MediaPipe initialises an EGL/GL context that must
        # stay on the same thread it was created on.
        detector = SquatDetector()
        zoom_supported = False
        current_zoom = ZOOM_MIN

        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            detector.close()
            return

        zoom_supported = _init_zoom(cap)
        current_zoom = int(cap.get(cv2.CAP_PROP_ZOOM)) if zoom_supported else ZOOM_MIN

        self._running = True
        while self._running:
            if self._reset_pending:
                detector.reset_session()
                self._reset_pending = False
                self._last_person_state = None

            ok, frame_bgr = cap.read()
            if not ok:
                continue

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result: DetectorResult = detector.process(frame_rgb)

            if zoom_supported and result.person_detected:
                self._frame_count += 1
                if self._frame_count % ZOOM_EVERY_N_FRAMES == 0:
                    if result.body_fraction > ZOOM_OUT_THRESHOLD and current_zoom > ZOOM_MIN:
                        current_zoom = max(ZOOM_MIN, current_zoom - ZOOM_STEP)
                        cap.set(cv2.CAP_PROP_ZOOM, current_zoom)

            if result.person_detected != self._last_person_state:
                self._last_person_state = result.person_detected
                self.person_detected.emit(result.person_detected)

            if result.rep_counted:
                self.rep_counted.emit(result.current_reps)

            self.frame_ready.emit(_to_qimage(result.annotated_frame))

        cap.release()
        detector.close()

    def stop(self) -> None:
        self._running = False
        self.wait()

    def reset_session(self) -> None:
        # Safe cross-thread reset: set flag, camera thread picks it up next frame
        self._reset_pending = True

def _init_zoom(cap: cv2.VideoCapture) -> bool:
    """
    Try to set the camera zoom to minimum (widest FOV).
    Returns True if zoom control is supported by this camera.
    """
    before = cap.get(cv2.CAP_PROP_ZOOM)
    cap.set(cv2.CAP_PROP_ZOOM, ZOOM_MIN)
    after = cap.get(cv2.CAP_PROP_ZOOM)
    # Supported if the value changed or already at minimum
    return after == ZOOM_MIN or after != before


def _to_qimage(rgb: np.ndarray) -> QImage:
    h, w, ch = rgb.shape
    # .copy() makes QImage own its pixel buffer so the numpy array can be freed safely
    return QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888).copy()
