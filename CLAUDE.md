# CLAUDE.md — Squat Counter

## Project Overview

Desktop app that counts squat repetitions from a live USB webcam feed, stores sessions in SQLite, and shows history charts. Runs on Linux Mint.

## Stack

- **Language:** Python 3.10+
- **UI:** PyQt6 — main window, widgets, event loop
- **Camera:** OpenCV (`cv2`) — captures frames in a background QThread
- **Pose estimation:** MediaPipe (`mediapipe`) — `Pose` solution, 33 landmarks
- **Squat logic:** custom Python in `core/detector.py`
- **Storage:** SQLite via stdlib `sqlite3`
- **Charts:** PyQtGraph (preferred, GPU-accelerated) or Matplotlib via `FigureCanvasQTAgg`

## Architecture

```
QApplication
└── MainWindow (PyQt6 QMainWindow)
    ├── CameraThread (QThread) — emits QImage frames via signal
    │   └── Detector — runs MediaPipe per frame, emits rep events
    ├── VideoWidget — renders QImage + draws overlay (person box, landmarks)
    ├── CounterWidget — live rep counter HUD
    ├── SessionManager — tracks current session state, writes to DB on end
    └── HistoryDialog — opens on demand, queries DB, renders chart
```

### Threading model

- Camera capture and MediaPipe inference run in `CameraThread` (never on the GUI thread).
- Results are pushed to the main thread via Qt signals (`frame_ready`, `rep_counted`, `person_detected`).
- SQLite writes happen on the main thread (single-writer, no concurrency needed).

## Key Files

| File | Responsibility |
|---|---|
| `main.py` | Creates `QApplication`, opens `MainWindow`, runs event loop |
| `ui/main_window.py` | Lays out camera feed, counter HUD, history button |
| `ui/history_view.py` | Modal dialog with date-range picker and bar chart |
| `core/camera.py` | `CameraThread(QThread)` — `cv2.VideoCapture` loop |
| `core/detector.py` | MediaPipe `Pose`, angle calculation, rep state machine |
| `core/session.py` | `SessionManager` — start/end session, idle timeout |
| `db/database.py` | `init_db()`, `save_session()`, `get_sessions(from, to)` |

## Squat Detection Algorithm

Uses MediaPipe landmarks `LEFT_HIP`, `LEFT_KNEE`, `LEFT_ANKLE` (mirrored on right side). Knee angle computed via dot product of thigh and shin vectors.

States: `IDLE → PERSON_DETECTED → STANDING → DESCENDING → BOTTOM → ASCENDING → STANDING` (rep += 1 on ASCENDING→STANDING transition).

Configurable constants live at the top of `core/detector.py`:
- `KNEE_DOWN_ANGLE = 90` — angle threshold for "bottom" phase
- `KNEE_UP_ANGLE = 160` — angle threshold for "standing" phase
- `IDLE_TIMEOUT_SEC = 5` — seconds of no person before session ends

## Development Commands

```bash
# Activate env
source .venv/bin/activate

# Install deps
pip install -r requirements.txt

# Run
python main.py

# Run with verbose pose debug overlay
python main.py --debug

# Lint
flake8 .

# Type check
mypy .
```

## Dependencies (requirements.txt)

```
PyQt6
opencv-python
mediapipe
pyqtgraph        # charts
numpy
```

## Database

File: `squat_counter.db` (created next to `main.py` on first run).

Schema:
```sql
CREATE TABLE sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    reps       INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT NOT NULL
);
```

## Coding Conventions

- PEP 8, 4-space indent, max line length 100.
- Qt signals/slots for all cross-thread communication — no shared mutable state between threads.
- No logic in `__init__` beyond attribute assignment; use `setup()` methods.
- SQLite access only through `db/database.py` — no raw SQL elsewhere.
- Keep MediaPipe and OpenCV imports inside `core/` — UI layer must not import them directly.
