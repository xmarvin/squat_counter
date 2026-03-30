# Squat Counter

A desktop application for automatically counting squats using a USB webcam and pose estimation ML.

## Features

- Live full-screen camera feed from USB webcam
- Real-time person detection with visual highlight overlay
- Automatic squat counting using MediaPipe pose estimation (knee/hip angle analysis)
- Session auto-save: rep count + timestamp written to SQLite on rest detection
- History view with daily bar chart

## Tech Stack

| Layer | Library |
|---|---|
| UI | PyQt6 |
| Camera / image | OpenCV (`cv2`) |
| Pose estimation | MediaPipe |
| Storage | SQLite (via Python `sqlite3`) |
| Charts | PyQtGraph or Matplotlib (embedded in PyQt6) |

## Requirements

- Linux Mint (tested), Python 3.10+
- USB webcam

## Installation

```bash
# Clone the repo
git clone <repo-url>
cd squat_counter

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
source .venv/bin/activate
python main.py
```

## Usage

1. Launch the app — the camera feed opens full-screen.
2. Step in front of the camera. A green bounding box highlights you when detected.
3. Start squatting. The rep counter increments on each clean squat (full down + up cycle).
4. Step away or pause — after a few seconds of inactivity the session is saved automatically and the counter resets.
5. Click **History** to view a daily chart of completed reps.

## Squat Detection Logic

MediaPipe provides 33 body landmarks per frame. A squat rep is counted when:
1. The knee angle drops below a configurable threshold (default ~90°) — **down phase**
2. The knee angle returns above the threshold — **up phase** (rep complete)

Only reps with a smooth angle curve are counted (noise filtering via a small moving average).

## Database Schema

```sql
CREATE TABLE sessions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    reps      INTEGER NOT NULL,
    started_at TEXT NOT NULL,   -- ISO-8601
    ended_at   TEXT NOT NULL    -- ISO-8601
);
```

## Project Structure

```
squat_counter/
├── main.py              # Entry point
├── ui/
│   ├── main_window.py   # Main camera window (PyQt6)
│   └── history_view.py  # History chart dialog
├── core/
│   ├── camera.py        # OpenCV camera thread
│   ├── detector.py      # MediaPipe pose + squat logic
│   └── session.py       # Session state machine
├── db/
│   └── database.py      # SQLite helpers
├── requirements.txt
└── squat_counter.db     # Created at runtime
```

## License

MIT
