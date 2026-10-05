# SoftTimer

A tiny neumorphic countdown timer for Windows. It runs as a compact always-on-top
desktop widget instead of a browser tab.

Built with [pywebview](https://pywebview.flowrl.com/), so the entire UI is HTML/CSS/JS
rendered in a native window, and the whole app ships as a single Python file.

## Features

- **Type or scroll to set a duration.** Click the time display and type `25`, `1:30`,
  `90s`, `1h30m`, or scroll over the digits to nudge them.
- **Selectable alert sounds**, generated in pure Python at runtime with the standard
  `wave` module. No bundled audio files, no dependencies beyond pywebview.
- **RGB flash on time-up** so it catches your eye across the room.
- **Completed-count pill** that increments every time a countdown reaches `00:00`.
- **Frameless, semi-transparent window** roughly 200x320 px, sits in a corner.

## Requirements

- Windows
- Python 3.13 or newer
- `pywebview`

```bash
pip install -r requirements.txt
```

## Run

```bash
py timer.py
```

Or double-click `launch.bat`, which runs it with `pyw` so no console window appears.

## Build a standalone .exe

PyInstaller spec is included:

```bash
pip install pyinstaller
pyinstaller SoftTimer.spec
```

The executable lands in `dist/SoftTimer.exe`.

## Project layout

```
timer.py          entire application: sound synthesis, TimerAPI, HTML/CSS/JS UI
SoftTimer.spec    PyInstaller build definition
launch.bat        console-free launcher
requirements.txt  runtime dependencies
```

## How the sounds work

There are no `.wav` assets in this repo. `_build_sound_dir()` synthesises each alert
tone on first run into the system temp directory, using a frequency function fed
through `wave` and `struct`. Adding a new alert means adding one frequency function
to that table, nothing else.

## License

MIT. See `LICENSE`.
