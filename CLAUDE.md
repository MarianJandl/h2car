# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Textual-based terminal UI (TUI) that displays real-time telemetry from a hydrogen-powered race car. It reads a serial data stream (or simulated data), shows a live dashboard, stats, error/alert status, a race tracker for estimating hydrogen-stick/battery change timing, and logs everything to `logs/`.

## Commands

```powershell
pip install -r requirements.txt
python telemetry.py            # single entry point
```

There is no test suite, linter, or build step. The `test*.py` files at the repo root are throwaway scratch experiments, not tests — ignore them unless asked.

Plotting historical data (also invokable from inside the app via the `plot` command):
```powershell
python plotdata.py -f logs/rawdatalog<date>_<n>.txt -l 300 -v Vbat Iout Tfc
```

## Architecture

### Data flow (all in-process)
`telemetry.py` holds the `DashboardLogApp`. On connect, `handle_connection` instantiates a data source from `bin/datasource.py` and calls `.start()`:
- Simulated: `SimulatedSource` (random plausible telemetry, 1 Hz)
- Serial: `SerialSource(port, baudrate)` (pyserial, with auto-reconnect)

Each source runs its own **daemon thread** that pushes lines onto a shared `queue.Queue`. A 1-second Textual `set_interval` timer (`update_data`) drains the queue and fans data out to the widgets. This keeps blocking serial I/O off the UI event loop **without spawning a second Python process** (an earlier version `Popen`-ed a child script and parsed its stdout; that cost ~20-30 MB extra RAM and a hard `python`-on-PATH dependency). `plotdata.py` is still launched as a short-lived subprocess because it opens a matplotlib GUI window.

To change how data is read, edit `bin/datasource.py`. Both sources subclass `DataSource`, which owns the thread lifecycle (`start`/`stop`/`is_alive`) and raw-log file.

### Line protocol (queue messages)
Sources push strings in the form `prefix: payload`:
- `data: Tim:123 Di:0x0 Vbat:7.8 Iout:55.2 Pout:43.1 Vfc:7.9 Pfc:42.0 Tfc:60 ...` — space-separated `Key:Value` pairs. `get_data()` parses payload into a dict.
- `info: <message>` — status/log line, written to the log only.
- Anything else is logged as "wrong format".

Key fields consumed by widgets: `Di` (hex error code), `Vbat`, `Iout`, `Pout`, `Vfc`, `Pfc`, `Tfc`, `Tim`. When adding telemetry fields, update both the source(s) in `bin/datasource.py` and the consuming widget(s) in `bin/`.

### Widgets (`bin/`)
Custom Textual widgets, each in its own module: `dashboard`, `statsdashboard`, `connectionstatus`, `connectionscreen`, `errorstatus`, `resourcemonitor`, `quitscreen`, `inputscreen`. `RaceTracker` and `DashboardLogApp` live in `telemetry.py`. Panel titles are set via Textual `border_title` (CSS gives them rounded bordered frames), so widget bodies no longer print their own header lines.

> Import widgets by explicit name (`from bin.dashboard import Dashboard`), **not** `import *`. Several modules do `import datetime` etc. at module level, and a wildcard import leaks those names into the app and can shadow `from datetime import datetime`.

### Configuration (`config/`, hot-reloadable)
- `race_config.json` — race duration, hydrogen-stick count, battery count, race name. Drives `RaceTracker` interval math (it redistributes remaining time across remaining sticks/batteries after each logged change).
- `error_config.json` — `error_codes` (mapped from the `Di` field) and `conditions` (expression strings like `"warning: Vbat < 8: message {Vbat}"` evaluated against each data dict by `ErrorStatus`).

Both files are **auto-created with defaults if missing** (`load_race_config` / `load_error_config`), so deleting them is non-destructive. The in-app **Config tab** edits these JSON files and saves with `ctrl+s` (only when the editor is focused), which triggers a live config reload.

### Logging
`DashboardLogApp` opens one `logs/appdatalog<YYYYMMDD>_<n>.txt` per session and keeps the handle open for the app's lifetime (`write_log`). Data sources independently write raw streams to `logs/rawdatalog*.txt` (serial) or `logs/simrawdatalog*.txt` (simulation). `plotdata.py` defaults to the newest `logs/rawdatalog*.txt`. The `logs/` directory is auto-created.

### In-app command line (`m` key)
`handle_command` parses typed commands: `log <text>`, `n <v|f> <+|-> <amount>` (adjust warning counters held as instance state `napomenutiV`/`napomenutiF`), and `plot <args>` (spawns `plotdata.py`). Key bindings are in `DashboardLogApp.BINDINGS`; see the README "Key bindings" section for the full list.

## Notes for editing

- Part of the codebase (UI strings, comments, README TODOs) is in Czech. Match the surrounding language when editing user-facing text.
- The app is Windows-oriented (serial COM ports, PowerShell), but the data path no longer shells out to `python`, so it is more portable than before.
- Per-session counters and the log handle are instance attributes on `DashboardLogApp` (not module globals).
