"""
Sound effects for the squat counter app.

Generates two short WAV tones on first use and caches them under sounds/.
Uses QSoundEffect for low-latency playback on the main thread.
"""

from __future__ import annotations

import array
import math
import struct
import wave
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtMultimedia import QSoundEffect

_SOUNDS_DIR = Path(__file__).parent.parent / "sounds"
_SAMPLE_RATE = 44100


def _generate_wav(path: Path, freqs: list[float], durations: list[float],
                  volume: float = 0.55) -> None:
    """Write a multi-tone WAV file (each freq plays for its duration in sequence)."""
    all_samples: list[int] = []
    fade_samples = int(_SAMPLE_RATE * 0.025)   # 25 ms fade-in/out per segment

    for freq, dur in zip(freqs, durations):
        n = int(_SAMPLE_RATE * dur)
        seg = [
            int(volume * 32767 * math.sin(2 * math.pi * freq * i / _SAMPLE_RATE))
            for i in range(n)
        ]
        # Fade in
        for i in range(min(fade_samples, n)):
            seg[i] = int(seg[i] * i / fade_samples)
        # Fade out
        for i in range(min(fade_samples, n)):
            seg[n - 1 - i] = int(seg[n - 1 - i] * i / fade_samples)
        all_samples.extend(seg)

    data = array.array('h', all_samples)
    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(data.tobytes())


def _ensure_sounds() -> tuple[Path, Path]:
    """Return paths to start and end WAV files, generating them if needed."""
    _SOUNDS_DIR.mkdir(exist_ok=True)
    start_path = _SOUNDS_DIR / "handstand_start.wav"
    end_path = _SOUNDS_DIR / "handstand_end.wav"

    if not start_path.exists():
        # Two ascending notes — bright, energetic
        _generate_wav(start_path, [660.0, 880.0], [0.12, 0.18])

    if not end_path.exists():
        # Two descending notes — conclusive
        _generate_wav(end_path, [660.0, 440.0], [0.15, 0.25])

    return start_path, end_path


class HandstandSounds:
    """Owns QSoundEffect instances for handstand start/end cues."""

    def __init__(self) -> None:
        start_path, end_path = _ensure_sounds()

        self._start = QSoundEffect()
        self._start.setSource(QUrl.fromLocalFile(str(start_path)))
        self._start.setVolume(0.9)

        self._end = QSoundEffect()
        self._end.setSource(QUrl.fromLocalFile(str(end_path)))
        self._end.setVolume(0.9)

    def play_start(self) -> None:
        self._start.play()

    def play_end(self) -> None:
        self._end.play()
