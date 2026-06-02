# h2car Telemetry — User Guide

Real-time telemetry dashboard for the hydrogen race car. It reads a live data
stream (from a serial device, or simulated data for debugging), shows the
important values, tracks the race, and logs everything to disk.

## Start the app

```
pip install -r requirements.txt
python telemetry.py
```

Prefer a more modern look? Run the redesigned UI and pick a layout:

```
python telemetry_redesign.py
```

## Connecting to data

- Press **`c`** to open the connection dialog. Choose:
  - **Simulation** — generates fake but realistic data, for testing.
  - **Serial** — enter the **port** (e.g. `COM5`, `/dev/ttyUSB0`) and **baudrate**
    (e.g. `115200`), then connect.
- Press **`ctrl+d`** to disconnect the data stream.

The connection status (Connected / Connecting / Disconnected) is shown at the
top of the dashboard.

## The screen

The app has three tabs (switch with the mouse or `ctrl+p` → "Show tab"):

- **Dashboard & Log** — live readouts on the left, scrolling log on the right:
  - **Status** — current error code, decoded into a message.
  - **Dashboard** — the live values: battery voltage, motor current/power, fuel
    cell voltage/power/temperature, and seconds since reset.
  - **Statistics** — min / max / average for each value since connecting.
  - **Race Tracker** — race progress and when to change consumables (below).
  - **Resources** — CPU / RAM / battery of the machine running the app.
- **Docs** — browse and read the Markdown files in the project (this guide
  included). Pick a file from the tree on the left.
- **Config** — edit the JSON config files live (see Configuration below).

## Race Tracker

The race tracker estimates when you'll need to swap hydrogen sticks and
batteries, spreading the remaining ones evenly across the time left.

- **`r`** — start the race (and resume if paused)
- **`p`** — pause / resume
- **`ctrl+r`** — reset the race
- **`h`** — log a hydrogen-stick change
- **`ctrl+b`** — log a battery change

Each progress bar turns yellow, then red, as a change becomes due. After you log
a change, the remaining time is redistributed across the remaining items.

## Command line

Press **`m`** to open the command line. Commands:

- **`log <text>`** — write a custom note into the log.
- **`n <v|f> <+|-> <amount>`** — adjust a warning counter (e.g. `n v + 2`).
- **`plot <args>`** — plot logged data in a separate window. Useful arguments:
  - `-l <N>` — only the last N samples (e.g. `-l 300`)
  - `-v <vars...>` — which channels to plot (e.g. `-v Vbat Tfc`)
  - `-f <file>` — a specific log file (defaults to the newest)

  Example: `plot -l 300 -v Vbat Iout Tfc`

## Configuration

Config lives in `config/` and can be edited inside the **Config** tab:

- Select a file in the tree to open it in the editor.
- Edit, then press **`ctrl+s`** to save and reload it live (editor must be
  focused). Press **`ctrl+l`** to reload from disk without saving.

Files:

- **`race_config.json`** — race length and consumables:
  - `race_duration_seconds`, `hydrogen_stick_count`, `battery_count`,
    `race_name`.
- **`error_config.json`** — maps error codes (the `Di` field) to messages and a
  severity (`info` / `warning` / `error` / `critical`).

If a config file is missing it is recreated with sensible defaults, so deleting
one is safe.

## Key bindings (quick reference)

| Key | Action |
|-----|--------|
| `c` | Open connection dialog |
| `ctrl+d` | Disconnect |
| `r` | Start / resume race |
| `p` | Pause / resume race |
| `ctrl+r` | Reset race |
| `h` | Log hydrogen-stick change |
| `ctrl+b` | Log battery change |
| `m` | Open command line |
| `ctrl+s` | Save config (in Config tab) |
| `ctrl+l` | Reload config |
| `ctrl+p` | Command palette |
| `ctrl+q` | Quit (with confirmation) |

## Logs

Every session is written to `logs/`:

- `appdatalog<date>_<n>.txt` — the in-app log (what you see in the Log panel).
- `rawdatalog<date>_<n>.txt` / `simrawdatalog<date>_<n>.txt` — the raw serial /
  simulated stream, used by the `plot` command.
