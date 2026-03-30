"""
Sound effects for the squat counter app.

Generates WAV tones on first use and caches them under sounds/.
Plays via aplay (ALSA) in a daemon thread — avoids Qt multimedia backend issues on Linux.
"""

from __future__ import annotations

import array
import math
import subprocess
import threading
import wave
from pathlib import Path

_SOUNDS_DIR = Path(__file__).parent.parent / "sounds"
_SAMPLE_RATE = 44100


def _generate_wav(path: Path, freqs: list[float], durations: list[float],
                  volume: float = 0.65) -> None:
    """Write a multi-tone WAV file (each freq plays for its duration in sequence)."""
    all_samples: list[int] = []
    fade_samples = int(_SAMPLE_RATE * 0.025)   # 25 ms fade-in/out per segment

    for freq, dur in zip(freqs, durations):
        n = int(_SAMPLE_RATE * dur)
        seg = [
            int(volume * 32767 * math.sin(2 * math.pi * freq * i / _SAMPLE_RATE))
            for i in range(n)
        ]
        for i in range(min(fade_samples, n)):
            seg[i] = int(seg[i] * i / fade_samples)
        for i in range(min(fade_samples, n)):
            seg[n - 1 - i] = int(seg[n - 1 - i] * i / fade_samples)
        all_samples.extend(seg)

    data = array.array('h', all_samples)
    with wave.open(str(path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(data.tobytes())


def _play(path: Path) -> None:
    """Play a WAV file via aplay in a daemon thread (non-blocking)."""
    def _run():
        subprocess.run(["aplay", "-q", str(path)], check=False)
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _ensure_sounds() -> tuple[Path, Path]:
    _SOUNDS_DIR.mkdir(exist_ok=True)
    start_path = _SOUNDS_DIR / "handstand_start.wav"
    end_path = _SOUNDS_DIR / "handstand_end.wav"
    if not start_path.exists():
        _generate_wav(start_path, [660.0, 880.0], [0.12, 0.18])
    if not end_path.exists():
        _generate_wav(end_path, [660.0, 440.0], [0.15, 0.25])
    return start_path, end_path


def _ensure_squat_sounds() -> tuple[Path, Path]:
    _SOUNDS_DIR.mkdir(exist_ok=True)
    start_path = _SOUNDS_DIR / "squat_start.wav"
    end_path = _SOUNDS_DIR / "squat_end.wav"
    if not start_path.exists():
        _generate_wav(start_path, [523.0], [0.15])
    if not end_path.exists():
        _generate_wav(end_path, [523.0, 659.0, 784.0], [0.10, 0.10, 0.20])
    return start_path, end_path


class SquatSounds:
    def __init__(self) -> None:
        self._start, self._end = _ensure_squat_sounds()

    def play_start(self) -> None:
        _play(self._start)

    def play_end(self) -> None:
        _play(self._end)


class HandstandSounds:
    def __init__(self) -> None:
        self._start, self._end = _ensure_sounds()

    def play_start(self) -> None:
        _play(self._start)

    def play_end(self) -> None:
        _play(self._end)
