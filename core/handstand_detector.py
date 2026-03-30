"""
Handstand detector using MediaPipe Tasks API.

Handstand condition:  avg(ankle_y) < avg(wrist_y)   — feet above hands
Standing condition:   avg(ankle_y) > avg(hip_y)     — feet below hips (back on feet)

In MediaPipe normalized coords y=0 = top of image, y=1 = bottom.

State machine (3 states):
  NO_PERSON  → UPRIGHT    (landmarks appear)
  UPRIGHT    → BALANCING  after _BALANCE_FRAMES consecutive handstand-condition frames (~1 sec)
                           → entered_balance=True (fires exactly once per session)
  BALANCING  → UPRIGHT    after _FALL_FRAMES consecutive standing-condition frames (~0.33 sec)
                           → lost_balance=True; any non-standing frame resets the counter
                           Lost landmarks while BALANCING: reset standing counter, stay BALANCING
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

MODEL_PATH = Path(__file__).parent.parent / "pose_landmarker_lite.task"

_BALANCE_FRAMES = 30   # ~1 second at 30 fps before confirming balance
_FALL_FRAMES    = 20   # ~0.67 seconds of clearly standing before ending session

_PoseLandmark = mp_vision.PoseLandmark


class HandstandState(Enum):
    NO_PERSON = auto()
    UPRIGHT = auto()
    BALANCING = auto()


@dataclass
class HandstandResult:
    state: HandstandState
    entered_balance: bool   # True for exactly one frame when UPRIGHT → BALANCING
    lost_balance: bool      # True for exactly one frame when BALANCING → UPRIGHT


class HandstandDetector:
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
        self._state = HandstandState.NO_PERSON
        self._true_count = 0
        self._false_count = 0

    def process(self, frame_rgb: np.ndarray) -> HandstandResult:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._landmarker.detect(mp_image)

        entered_balance = False
        lost_balance = False

        if not result.pose_landmarks:
            if self._state == HandstandState.BALANCING:
                # Lost tracking mid-hold: reset the standing counter but stay BALANCING.
                # Avoids falsely ending a session from a brief tracking dropout.
                self._false_count = 0
                return HandstandResult(
                    state=HandstandState.BALANCING,
                    entered_balance=False,
                    lost_balance=False,
                )
            else:
                self._state = HandstandState.NO_PERSON
                self._true_count = 0
                self._false_count = 0
                return HandstandResult(
                    state=HandstandState.NO_PERSON,
                    entered_balance=False,
                    lost_balance=False,
                )

        lm = result.pose_landmarks[0]

        # Transition from NO_PERSON → UPRIGHT on first detection
        if self._state == HandstandState.NO_PERSON:
            self._state = HandstandState.UPRIGHT

        if self._state == HandstandState.UPRIGHT:
            if self._is_handstand(lm):
                self._true_count += 1
                if self._true_count >= _BALANCE_FRAMES:
                    self._state = HandstandState.BALANCING
                    self._true_count = 0
                    self._false_count = 0
                    entered_balance = True
            else:
                self._true_count = 0

        elif self._state == HandstandState.BALANCING:
            if self._is_standing(lm):
                # Person is back on their feet — count toward session end
                self._false_count += 1
                if self._false_count >= _FALL_FRAMES:
                    self._state = HandstandState.UPRIGHT
                    self._true_count = 0
                    self._false_count = 0
                    lost_balance = True
            else:
                # Still in transition or mid-air — reset the counter
                self._false_count = 0

        return HandstandResult(
            state=self._state,
            entered_balance=entered_balance,
            lost_balance=lost_balance,
        )

    def reset(self) -> None:
        self._state = HandstandState.NO_PERSON
        self._true_count = 0
        self._false_count = 0

    def close(self) -> None:
        self._landmarker.close()

    def _is_handstand(self, lm) -> bool:
        """Return True if feet are above hands in the image."""
        WRIST_L, WRIST_R = _PoseLandmark.LEFT_WRIST, _PoseLandmark.RIGHT_WRIST
        ANKLE_L, ANKLE_R = _PoseLandmark.LEFT_ANKLE, _PoseLandmark.RIGHT_ANKLE
        MIN_VIS = 0.3

        wrist_ys = [lm[i].y for i in (WRIST_L, WRIST_R) if lm[i].visibility > MIN_VIS]
        ankle_ys = [lm[i].y for i in (ANKLE_L, ANKLE_R) if lm[i].visibility > MIN_VIS]

        if not wrist_ys or not ankle_ys:
            return False

        return (sum(ankle_ys) / len(ankle_ys)) < (sum(wrist_ys) / len(wrist_ys))

    def _is_standing(self, lm) -> bool:
        """Return True only when clearly back on feet: ankles below both wrists and hips.

        The wrist guard is the key protection: in any handstand (straight, bent, piked,
        wall-supported), wrists are on the floor (y ≈ 0.9-1.0). Ankles are always above
        them (lower y), so avg_ankle > avg_wrist is impossible during a handstand.
        Missing any landmark group returns False — unknown pose never ends a session.
        """
        WRIST_L, WRIST_R = _PoseLandmark.LEFT_WRIST, _PoseLandmark.RIGHT_WRIST
        HIP_L,   HIP_R   = _PoseLandmark.LEFT_HIP,   _PoseLandmark.RIGHT_HIP
        ANKLE_L, ANKLE_R = _PoseLandmark.LEFT_ANKLE,  _PoseLandmark.RIGHT_ANKLE
        MIN_VIS = 0.3

        wrist_ys = [lm[i].y for i in (WRIST_L, WRIST_R) if lm[i].visibility > MIN_VIS]
        hip_ys   = [lm[i].y for i in (HIP_L,   HIP_R)   if lm[i].visibility > MIN_VIS]
        ankle_ys = [lm[i].y for i in (ANKLE_L, ANKLE_R) if lm[i].visibility > MIN_VIS]

        if not wrist_ys or not hip_ys or not ankle_ys:
            return False

        avg_ankle = sum(ankle_ys) / len(ankle_ys)
        avg_wrist = sum(wrist_ys) / len(wrist_ys)
        avg_hip   = sum(hip_ys)   / len(hip_ys)

        return avg_ankle > avg_wrist and avg_ankle > avg_hip
