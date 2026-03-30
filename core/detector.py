"""
Pose-based squat detector using MediaPipe Tasks API.

Squat rep state machine:
  STANDING -> GOING_DOWN  (knee angle drops below ANGLE_DOWN_THRESHOLD)
  GOING_DOWN -> BOTTOM    (knee angle drops below ANGLE_BOTTOM_THRESHOLD)
  BOTTOM -> GOING_UP      (knee angle rises above ANGLE_BOTTOM_THRESHOLD + hysteresis)
  GOING_UP -> STANDING    (knee angle rises above ANGLE_STANDING_THRESHOLD) -> rep counted
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# --- Thresholds (degrees) ---
ANGLE_DOWN_THRESHOLD = 130
ANGLE_BOTTOM_THRESHOLD = 100
ANGLE_STANDING_THRESHOLD = 155
SMOOTHING_WINDOW = 5

MODEL_PATH = Path(__file__).parent.parent / "pose_landmarker_lite.task"

_PoseLandmark = mp_vision.PoseLandmark
_Connections = mp_vision.PoseLandmarksConnections.POSE_LANDMARKS
_DrawingUtils = mp_vision.drawing_utils
_DrawingStyles = mp_vision.drawing_styles


class SquatState(Enum):
    NO_PERSON = auto()
    STANDING = auto()
    GOING_DOWN = auto()
    BOTTOM = auto()
    GOING_UP = auto()


@dataclass
class DetectorResult:
    annotated_frame: np.ndarray
    person_detected: bool
    rep_counted: bool
    current_reps: int
    state: SquatState
    knee_angle: float | None = None
    bbox: tuple[int, int, int, int] | None = None
    body_fraction: float = 0.0   # bbox_h / frame_h — used by camera to drive zoom


class SquatDetector:
    def __init__(self) -> None:
        options = mp_vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = mp_vision.PoseLandmarker.create_from_options(options)
        self._state = SquatState.NO_PERSON
        self._reps = 0
        self._angle_buffer: deque[float] = deque(maxlen=SMOOTHING_WINDOW)

    def process(self, frame_rgb: np.ndarray) -> DetectorResult:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._landmarker.detect(mp_image)
        annotated = frame_rgb.copy()
        rep_counted = False

        if not result.pose_landmarks:
            self._state = SquatState.NO_PERSON
            self._angle_buffer.clear()
            return DetectorResult(
                annotated_frame=annotated,
                person_detected=False,
                rep_counted=False,
                current_reps=self._reps,
                state=self._state,
            )

        _DrawingUtils.draw_landmarks(
            annotated,
            result.pose_landmarks[0],
            _Connections,
            _DrawingStyles.get_default_pose_landmarks_style(),
        )

        lm = result.pose_landmarks[0]
        h, w = frame_rgb.shape[:2]

        xs = [int(l.x * w) for l in lm if l.visibility > 0.3]
        ys = [int(l.y * h) for l in lm if l.visibility > 0.3]
        bbox = (min(xs), min(ys), max(xs), max(ys)) if xs else None
        if bbox:
            cv2.rectangle(annotated, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 80), 2)

        body_fraction = (bbox[3] - bbox[1]) / h if bbox else 0.0

        raw_angle = self._compute_knee_angle(lm, w, h)
        if raw_angle is not None:
            self._angle_buffer.append(raw_angle)

        smooth_angle = (
            sum(self._angle_buffer) / len(self._angle_buffer)
            if self._angle_buffer else None
        )

        if self._state == SquatState.NO_PERSON:
            self._state = SquatState.STANDING

        if smooth_angle is not None:
            rep_counted = self._advance_state(smooth_angle)

        if smooth_angle is not None:
            cv2.putText(
                annotated,
                f"{smooth_angle:.0f}deg  {self._state.name}",
                (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 0),
                2,
            )

        return DetectorResult(
            annotated_frame=annotated,
            person_detected=True,
            rep_counted=rep_counted,
            current_reps=self._reps,
            state=self._state,
            knee_angle=smooth_angle,
            bbox=bbox,
            body_fraction=body_fraction,
        )

    def reset_session(self) -> None:
        self._reps = 0
        self._state = SquatState.NO_PERSON
        self._angle_buffer.clear()

    def close(self) -> None:
        self._landmarker.close()

    def _advance_state(self, angle: float) -> bool:
        if self._state == SquatState.STANDING:
            if angle < ANGLE_DOWN_THRESHOLD:
                self._state = SquatState.GOING_DOWN
        elif self._state == SquatState.GOING_DOWN:
            if angle < ANGLE_BOTTOM_THRESHOLD:
                self._state = SquatState.BOTTOM
            elif angle >= ANGLE_STANDING_THRESHOLD:
                self._state = SquatState.STANDING
        elif self._state == SquatState.BOTTOM:
            if angle > ANGLE_BOTTOM_THRESHOLD + 10:
                self._state = SquatState.GOING_UP
        elif self._state == SquatState.GOING_UP:
            if angle >= ANGLE_STANDING_THRESHOLD:
                self._state = SquatState.STANDING
                self._reps += 1
                return True
        return False

    def _compute_knee_angle(self, lm, w: int, h: int) -> float | None:
        def pt(idx) -> np.ndarray:
            return np.array([lm[idx].x * w, lm[idx].y * h])

        def side(hip_i, knee_i, ankle_i) -> float | None:
            if min(lm[hip_i].visibility, lm[knee_i].visibility, lm[ankle_i].visibility) < 0.3:
                return None
            return _angle_between(pt(hip_i), pt(knee_i), pt(ankle_i))

        left = side(_PoseLandmark.LEFT_HIP, _PoseLandmark.LEFT_KNEE, _PoseLandmark.LEFT_ANKLE)
        right = side(_PoseLandmark.RIGHT_HIP, _PoseLandmark.RIGHT_KNEE, _PoseLandmark.RIGHT_ANKLE)
        valid = [a for a in (left, right) if a is not None]
        return sum(valid) / len(valid) if valid else None


def _angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba, bc = a - b, c - b
    cos_a = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return math.degrees(math.acos(float(np.clip(cos_a, -1.0, 1.0))))
