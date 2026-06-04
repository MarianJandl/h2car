"""h2car telemetry — redesigned TUI with a variant launcher.

A terminal-faithful restyle of the dashboard from the Claude Design handoff
("Telemetry Redesign.html"). Dark "TERM" palette, blue primary, live
block-character sparklines. Two directions are implemented and share one
backend; a launcher lets you pick which to run:

    python telemetry_redesign.py            # opens the launcher
    python telemetry_redesign.py --variant b # skip the launcher (a|b)

    A · Refined Classic   — left rail of panels beside the log (lowest-risk port)
    B · Hero Grid         — Pout/Pfc/Vbat/Tfc as big hero tiles (recommended)

Both variants share a Statistics tab showing min/max/avg for all six channels
(Vbat, Iout, Pout, Vfc, Pfc, Tfc) over a selectable time window — all time,
last hour, last 5 minutes, or a custom number of minutes.

The original `telemetry.py` is left untouched. Backend (in-process data sources,
config loaders, modal screens) is reused, so behaviour matches the real app;
only the presentation differs.
"""

import argparse
import json
import os
import subprocess
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from queue import Queue
from shlex import split
from typing import Iterable

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.theme import Theme
from textual.widgets import (
    Digits, DirectoryTree, Footer, Header, Input, MarkdownViewer, OptionList,
    ProgressBar, RadioButton, RadioSet, RichLog, Static, TabbedContent, TabPane,
    TextArea,
)
from textual.widgets.option_list import Option

from bin.connectionscreen import ConnectionScreen
from bin.datasource import SimulatedSource, SerialSource
from bin.errorstatus import load_error_config
from bin.inputscreen import InputScreen
from bin.quitscreen import QuitScreen

# ============================================================
# Design palette + Textual theme (from redesign/term.css)
# ============================================================
PALETTE = {
    "bg": "#0a0e14", "surface": "#0e131b", "panel": "#11161f",
    "line": "#232c38", "line2": "#2f3a48",
    "fg": "#c4ccd6", "fg_dim": "#69727e", "fg_faint": "#444d59",
    "accent": "#4d9dff", "cyan": "#4dd2e0", "yellow": "#e3b341",
    "red": "#f85149", "mag": "#bc8cff",
}

H2_THEME = Theme(
    name="h2car",
    primary=PALETTE["accent"],
    secondary=PALETTE["cyan"],
    accent=PALETTE["accent"],
    foreground=PALETTE["fg"],
    background=PALETTE["bg"],
    surface=PALETTE["surface"],
    panel=PALETTE["panel"],
    success=PALETTE["accent"],
    warning=PALETTE["yellow"],
    error=PALETTE["red"],
    dark=True,
)

METRICS = {
    "Pout": {"label": "Motor power · Pout", "unit": "W", "dec": 0, "color": PALETTE["accent"]},
    "Pfc":  {"label": "Cell power · Pfc",   "unit": "W", "dec": 1, "color": PALETTE["mag"]},
    "Vbat": {"label": "Battery · Vbat",     "unit": "V", "dec": 2, "color": PALETTE["cyan"]},
    "Tfc":  {"label": "Cell temp · Tfc",    "unit": "°C", "dec": 1, "color": PALETTE["yellow"]},
    "Iout": {"label": "Motor current · Iout", "unit": "A", "dec": 1, "color": PALETTE["cyan"]},
    "Vfc":  {"label": "Cell voltage · Vfc", "unit": "V", "dec": 2, "color": PALETTE["cyan"]},
}
HERO_KEYS = ["Pout", "Pfc", "Vbat", "Tfc"]
TABLE_KEYS = ["Vbat", "Iout", "Pout", "Vfc", "Pfc", "Tfc"]
ALL_KEYS = list(METRICS.keys())

SPARK_BLOCKS = "▁▂▃▄▅▆▇█"
HIST = 64
# Timestamped samples kept per channel for windowed stats (~2h at 1 Hz).
# "All time" uses O(1) running aggregates, so it stays accurate beyond this.
SAMPLE_CAP = 7200


def spark(values, width):
    vals = list(values)[-width:]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    return "".join(SPARK_BLOCKS[min(7, max(0, round((v - lo) / span * 7)))] for v in vals)


def ftime(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def render_segs(total, used):
    cells = []
    for i in range(total):
        color = PALETTE["accent"] if i < used else PALETTE["cyan"] if i == used else PALETTE["line2"]
        cells.append(f"[{color}]█[/]")
    return " ".join(cells)


def get_data(data):
    return dict(p.split(":") for p in data.split())


def load_race_config():
    config_path = Path("config/race_config.json")
    default = {
        "race_duration_seconds": 3600, "hydrogen_stick_count": 4, "battery_count": 2,
        "race_name": "Hydrogen Race", "enable_alerts": True, "alert_threshold_percent": 10,
    }
    if config_path.exists():
        try:
            with open(config_path) as f:
                return {**default, **json.load(f)}
        except Exception:
            pass
    return default


# ============================================================
# Data model
# ============================================================
class Series:
    def __init__(self):
        self.hist = deque(maxlen=HIST)          # recent values, for sparklines
        self.samples = deque(maxlen=SAMPLE_CAP)  # (timestamp, value), for windowed stats
        self.v = None
        self.min = float("inf")
        self.max = float("-inf")
        self.sum = 0.0
        self.n = 0

    def push(self, value):
        self.v = value
        self.hist.append(value)
        self.samples.append((time.time(), value))
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.sum += value
        self.n += 1

    @property
    def avg(self):
        return self.sum / self.n if self.n else None

    def window_stats(self, window):
        """(min, max, avg, count) over the last `window` seconds, or None if no
        samples. `window=None` means all time (uses O(1) running aggregates)."""
        if window is None:
            if self.n == 0:
                return None
            return self.min, self.max, self.sum / self.n, self.n
        cutoff = time.time() - window
        vals = [v for t, v in self.samples if t >= cutoff]
        if not vals:
            return None
        return min(vals), max(vals), sum(vals) / len(vals), len(vals)


class RaceModel:
    def __init__(self, config):
        self.apply_config(config)
        self.reset()

    def apply_config(self, c):
        self.duration = c["race_duration_seconds"]
        self.stick_count = c["hydrogen_stick_count"]
        self.battery_count = c["battery_count"]
        self.name = c["race_name"]

    def reset(self):
        self.start_time = None
        self.running = False
        self.paused = False
        self.elapsed = 0
        self.pause_total = 0
        self.pause_start = None
        self.stick_changes = 0
        self.battery_changes = 0
        self.last_stick = 0
        self.last_battery = 0

    def start(self):
        self.reset()
        self.start_time = time.time()
        self.running = True

    def pause(self):
        if self.running and not self.paused:
            self.paused = True
            self.pause_start = time.time()

    def resume(self):
        if self.running and self.paused:
            self.paused = False
            if self.pause_start:
                self.pause_total += time.time() - self.pause_start
                self.pause_start = None

    def tick(self):
        if self.running and self.start_time and not self.paused:
            self.elapsed = time.time() - self.start_time - self.pause_total

    def log_stick(self):
        if not self.running or self.paused or self.stick_changes >= self.stick_count:
            return False
        self.stick_changes += 1
        self.last_stick = self.elapsed
        return True

    def log_battery(self):
        if not self.running or self.paused or self.battery_changes >= self.battery_count:
            return False
        self.battery_changes += 1
        self.last_battery = self.elapsed
        return True

    def snapshot(self):
        remain = max(0, self.duration - self.elapsed)
        prog = min(self.elapsed / self.duration * 100, 100) if self.duration else 0

        def consumable(count, changes, last):
            left = count - changes
            iv = remain / left if left > 0 else 0
            since = self.elapsed - last
            pct = max(0.0, min(100.0, 100 - (since / iv * 100))) if iv > 0 else 0
            return left, pct, max(0, iv - since)

        _, s_pct, s_time = consumable(self.stick_count, self.stick_changes, self.last_stick)
        _, b_pct, b_time = consumable(self.battery_count, self.battery_changes, self.last_battery)
        return {
            "remain": remain, "race_pct": 100 - prog,
            "stick_pct": s_pct, "stick_time": s_time,
            "bat_pct": b_pct, "bat_time": b_time,
        }


# ============================================================
# Shared widgets
# ============================================================
class AlertStrip(Static):
    ICONS = {"ok": "●", "warn": "▲", "err": "■"}

    def on_mount(self):
        self.set_state("0", "All systems nominal", "info", 0)

    def set_state(self, code, message, priority, tim):
        cls = {"info": "ok", "warning": "warn", "error": "err", "critical": "err"}.get(priority, "ok")
        self.set_classes(["alertstrip", cls])
        self.update(
            f"{self.ICONS[cls]}  [b]Di {code}[/b]   {message}"
            f"   [dim]· {tim}s since reset[/dim]"
        )


class HeroTile(Vertical):
    def __init__(self, key):
        super().__init__(classes="tile")
        self.key = key
        self.meta = METRICS[key]

    def compose(self) -> ComposeResult:
        self.lbl = Static("", classes="tlabel")
        self.digits = Digits("--")
        self.spk = Static("", classes="spark")
        self.rng = Static("", classes="trange")
        yield self.lbl
        yield self.digits
        yield self.spk
        yield self.rng

    def on_mount(self):
        m = self.meta
        self.lbl.update(f"[b]{m['label'].upper()}[/b]  [dim]{m['unit']}[/dim]")
        self.digits.styles.color = m["color"]
        self.spk.styles.color = m["color"]
        self.rng.update("[dim]min[/dim] —  [dim]avg[/dim] —  [dim]max[/dim] —")

    def refresh_metric(self, series: Series):
        m = self.meta
        if series.v is None:
            return
        dec, color = m["dec"], m["color"]
        if self.key == "Tfc" and series.v >= 63:
            color = PALETTE["yellow"]
        elif self.key == "Vbat" and series.v <= 7.35:
            color = PALETTE["red"]
        self.digits.update(f"{series.v:.{dec}f}")
        self.digits.styles.color = color
        self.spk.update(spark(series.hist, 30))
        self.rng.update(
            f"[dim]min[/dim] {series.min:.{dec}f}   "
            f"[dim]avg[/dim] {series.avg:.{dec}f}   "
            f"[dim]max[/dim] {series.max:.{dec}f}"
        )


class RacePanel(Vertical):
    def __init__(self, model: RaceModel):
        super().__init__(classes="racepanel")
        self.model = model

    def compose(self) -> ComposeResult:
        self.head = Static("", classes="race-head")
        self.bar = ProgressBar(total=100, show_eta=False, show_percentage=True)
        self.stick_lbl = Static("", classes="seg-lbl")
        self.stick_segs = Static("", classes="segs")
        self.bat_lbl = Static("", classes="seg-lbl")
        self.bat_segs = Static("", classes="segs")
        yield self.head
        yield self.bar
        yield self.stick_lbl
        yield self.stick_segs
        yield self.bat_lbl
        yield self.bat_segs

    def on_mount(self):
        self.border_title = "Race Tracker"
        self.refresh_race()

    @staticmethod
    def bar_color(pct):
        if pct < 12:
            return PALETTE["red"]
        if pct < 28:
            return PALETTE["yellow"]
        return PALETTE["accent"]

    def refresh_race(self):
        m = self.model
        snap = m.snapshot()
        if m.running:
            state = "[dim]▶ paused[/dim]" if m.paused else f"[{PALETTE['accent']}]▶ running[/]"
        else:
            state = "[dim]○ not started[/dim]"
        self.head.update(
            f"[b]{m.name}[/b]   {state}\n"
            f"[dim]Elapsed[/dim] {ftime(m.elapsed)} [dim]/ {ftime(m.duration)} · "
            f"{ftime(snap['remain'])} left[/dim]"
        )
        self.bar.update(progress=snap["race_pct"])
        self.bar.styles.color = self.bar_color(snap["race_pct"])
        self.stick_lbl.update(
            f"[dim]Hydrogen stick[/dim] {m.stick_changes}/{m.stick_count}"
            f"  ·  [dim]{ftime(snap['stick_time'])} to change[/dim]"
        )
        self.stick_segs.update(render_segs(m.stick_count, m.stick_changes))
        self.bat_lbl.update(
            f"[dim]Battery[/dim] {m.battery_changes}/{m.battery_count}"
            f"  ·  [dim]{ftime(snap['bat_time'])} to change[/dim]"
        )
        self.bat_segs.update(render_segs(m.battery_count, m.battery_changes))


class MiniMetric(Static):
    def __init__(self, key):
        super().__init__(classes="panel mini")
        self.key = key
        self.meta = METRICS[key]

    def on_mount(self):
        self.refresh_metric(None)

    def refresh_metric(self, series):
        m = self.meta
        if series is None or series.v is None:
            self.update(f"[dim]{m['label']}   -- {m['unit']}[/dim]")
            return
        self.update(
            f"[dim]{m['label']}[/dim]   [{m['color']}]{spark(series.hist, 16)}[/]   "
            f"[b]{series.v:.{m['dec']}f}[/b] [dim]{m['unit']}[/dim]"
        )


class FilteredDirectoryTreeDocs(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [p for p in paths if (p.name.endswith(".md") or p.is_dir()) and not p.name.startswith(".")]


class FilteredDirectoryTreeConfig(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [p for p in paths if (p.name.endswith(".json") or p.is_dir()) and not p.name.startswith(".")]


# ============================================================
# Base app: backend + shared chrome (Header / tabs / Docs / Config / Footer)
# ============================================================
BASE_CSS = """
Screen { background: $background; }
#dash_pane { padding: 1 1 0 1; }
#docs_grid, #config_grid { grid-size: 2 1; grid-columns: 3fr 7fr; padding: 1; }

.alertstrip {
    height: 3; padding: 0 2; content-align: left middle;
    border: round #2061b8; background: #0c1626; color: $primary;
}
.alertstrip.warn { border: round #6b5418; background: #1a1608; color: $warning; }
.alertstrip.err  { border: round #6b201d; background: #1a0c0b; color: $error; }

.panel { border: round #232c38; background: $surface; border-title-color: $secondary; padding: 0 1; }
.tile  { height: 100%; border: round #232c38; background: $surface; padding: 0 1; }
.tile .tlabel { color: $text-muted; }
.tile Digits  { color: $primary; height: 3; }
.tile .spark  { height: 1; }
.tile .trange { color: #69727e; }

RichLog { border: round #232c38; background: #080b10; padding: 0 1; }

.racepanel { border: round #232c38; background: $surface; border-title-color: $secondary; padding: 0 1; }
.racepanel ProgressBar { margin: 1 0; }
.race-head { height: 2; }
.seg-lbl { margin-top: 1; }
.segs { height: 1; }

DirectoryTree, MarkdownViewer, TextArea {
    height: 100%; border: round #232c38; border-title-color: $secondary; background: $surface;
}

#stats_grid { grid-size: 2 1; grid-columns: 34 1fr; padding: 1; }
#stats_controls { height: 100%; }
#win_set {
    width: 100%; height: auto;
    border: round #232c38; background: $surface; border-title-color: $secondary;
}
#custom_min { margin-top: 1; border: round #232c38; background: $surface; }
#stats_table {
    height: 100%; padding: 1 2;
    border: round #232c38; background: $surface; border-title-color: $secondary;
}
"""


class BaseTelemetryApp(App):
    CSS = BASE_CSS
    VARIANT = "?"

    BINDINGS = [
        Binding("c", "open_connection", "Connect"),
        Binding("ctrl+d", "disconnect", "Disconnect", show=False),
        Binding("r", "toggle_race", "Race"),
        Binding("ctrl+r", "reset_race", "Reset", show=False),
        Binding("h", "log_stick", "Stick"),
        Binding("ctrl+b", "log_battery", "Battery"),
        Binding("m", "open_command", "Command"),
        Binding("ctrl+s", "save_config", "Save cfg", show=False),
        Binding("ctrl+l", "reload_config", "Reload cfg", show=False),
        Binding("ctrl+q", "request_quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.title = "h2car · telemetry"
        self.is_connected = False
        self.connection_config = None
        self.source = None
        self.queue = Queue()
        self.update_timer = None
        self.race_timer = None
        self.current_config_file = None

        self.series = {k: Series() for k in ALL_KEYS}
        self.tiles = {}
        self.stats_window = None  # None = all time; else seconds
        self.tim = 0
        self.last_di = "0"
        self.nodata = 0
        self.lineno = 0
        self.error_config = load_error_config()
        self.error_map = self._build_error_map(self.error_config)
        self.race = RaceModel(load_race_config())
        self.log_file = self._open_session_log()

    # ---------- session log ----------
    def _open_session_log(self):
        os.makedirs("logs", exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        k = 0
        while os.path.exists(f"./logs/appdatalog{date_str}_{k}.txt"):
            k += 1
        f = open(f"./logs/appdatalog{date_str}_{k}.txt", "a", encoding="utf-8")
        f.write(f"--- New session started at {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        f.flush()
        return f

    @staticmethod
    def _build_error_map(config):
        out = {}
        for entry in config.get("error_codes", []):
            for code in entry["code"]:
                out[code] = (entry["priority"], entry["message"])
        return out

    # ---------- shared chrome ----------
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab_dash"):
            with TabPane("Dashboard & Log", id="tab_dash"):
                yield from self.compose_dashboard()
            with TabPane("Statistics", id="tab_stats"):
                with Grid(id="stats_grid"):
                    with Vertical(id="stats_controls"):
                        rs = RadioSet(
                            RadioButton("All time", value=True, id="win_all"),
                            RadioButton("Last hour", id="win_hour"),
                            RadioButton("Last 5 min", id="win_5m"),
                            RadioButton("Custom (min)", id="win_custom"),
                            id="win_set",
                        )
                        rs.border_title = "Window"
                        yield rs
                        self.custom_min = Input(placeholder="custom minutes", id="custom_min", type="number")
                        yield self.custom_min
                    self.stats_table = Static("", id="stats_table")
                    self.stats_table.border_title = "Statistics — min · max · avg"
                    yield self.stats_table
            with TabPane("Docs", id="tab_docs"):
                with Grid(id="docs_grid"):
                    self.doc_tree = FilteredDirectoryTreeDocs("./", id="doc_tree")
                    self.doc_tree.border_title = "Files"
                    yield self.doc_tree
                    self.md = MarkdownViewer(
                        "# Documentation\n\nSelect a markdown file from the tree.",
                        show_table_of_contents=True,
                    )
                    self.md.border_title = "Viewer"
                    yield self.md
            with TabPane("Config", id="tab_config"):
                with Grid(id="config_grid"):
                    self.cfg_tree = FilteredDirectoryTreeConfig("./config", id="config_tree")
                    self.cfg_tree.border_title = "Files"
                    yield self.cfg_tree
                    self.cfg_view = TextArea("", language="json", show_line_numbers=True)
                    self.cfg_view.border_title = "Editor · ^s save & reload"
                    yield self.cfg_view
        yield Footer()

    def compose_dashboard(self) -> ComposeResult:
        raise NotImplementedError

    def on_mount(self):
        self.register_theme(H2_THEME)
        self.theme = "h2car"
        self.sub_title = f"{self.VARIANT}  ·  ○ Disconnected"
        self.paint()
        self.paint_race()

    # ---------- paint hooks ----------
    def paint(self):
        self.paint_dashboard()
        self.paint_stats()

    def paint_dashboard(self):  # overridden per variant
        raise NotImplementedError

    def paint_race(self):  # overridden per variant
        raise NotImplementedError

    # ---------- statistics tab ----------
    def _window_label(self):
        w = self.stats_window
        if w is None:
            return "all time"
        if w == 3600:
            return "last hour"
        if w == 300:
            return "last 5 minutes"
        return f"last {w / 60:g} min"

    def _custom_window(self):
        try:
            mins = float(self.custom_min.value)
            if mins > 0:
                return mins * 60
        except (ValueError, AttributeError):
            pass
        return 300

    def paint_stats(self):
        if not hasattr(self, "stats_table"):
            return
        header = f"[b]Statistics[/b]  [dim]· {self._window_label()}[/dim]\n\n"
        cols = f"[dim]{'Channel':<14}{'Min':>10}{'Max':>10}{'Avg':>10}[/dim]\n"
        rows = []
        for key in TABLE_KEYS:
            m = METRICS[key]
            chan = f"[{m['color']}]{key:<5}[/][dim]{m['unit']:<9}[/dim]"
            st = self.series[key].window_stats(self.stats_window)
            if st is None:
                rows.append(chan + f"{'--':>10}{'--':>10}{'--':>10}")
            else:
                mn, mx, avg, _ = st
                d = m["dec"]
                rows.append(chan + f"{mn:>10.{d}f}{mx:>10.{d}f}{avg:>10.{d}f}")
        self.stats_table.update(header + cols + "\n".join(rows))

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "win_set":
            return
        rid = event.pressed.id
        if rid == "win_hour":
            self.stats_window = 3600
        elif rid == "win_5m":
            self.stats_window = 300
        elif rid == "win_custom":
            self.stats_window = self._custom_window()
        else:
            self.stats_window = None
        self.paint_stats()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "custom_min":
            return
        custom = self.query_one("#win_custom", RadioButton)
        if not custom.value:
            custom.value = True  # selecting it fires on_radio_set_changed
        else:
            self.stats_window = self._custom_window()
            self.paint_stats()

    # ---------- helpers for variants ----------
    def fmt(self, key, value):
        return "--" if value is None else f"{value:.{METRICS[key]['dec']}f}"

    def smarkup(self, key, n):
        return f"[{METRICS[key]['color']}]{spark(self.series[key].hist, n)}[/]"

    def alert_tuple(self, code):
        pr, msg = self.error_map.get(code.lower()) or self.error_map.get(code) or (None, None)
        if pr is None:
            if code in ("0", "0x0"):
                pr, msg = "info", "All systems nominal"
            else:
                pr, msg = "critical", f"Unknown error code {code}"
        return code, msg, pr

    def update_alert(self):
        if hasattr(self, "alert"):
            code, msg, pr = self.alert_tuple(self.last_di)
            self.alert.set_state(code, msg, pr, self.tim)

    # ---------- connection ----------
    def action_open_connection(self):
        if self.cfg_view.has_focus:
            return
        if self.is_connected:
            self.write_log("Already connected. Disconnect first.")
            return
        self.push_screen(ConnectionScreen(), self.handle_connection)

    def handle_connection(self, config):
        if config is None:
            return
        self.connection_config = config
        ctype = config.get("type")
        if ctype == "simulated":
            self.source = SimulatedSource(self.queue)
        elif ctype == "serial":
            self.source = SerialSource(self.queue, config.get("port"), config.get("baudrate"))
        else:
            return
        self.source.start()
        self.is_connected = True
        self.tim = 0
        for s in self.series.values():
            s.__init__()
        label = "simulated" if ctype == "simulated" else f"serial {config.get('port')}@{config.get('baudrate')}"
        self.sub_title = f"{self.VARIANT}  ·  ● Connected — {label}"
        self.write_log(f"Connected to in-process {ctype} data source")
        self.paint()
        if self.update_timer:
            self.update_timer.stop()
        self.update_timer = self.set_interval(1, self.update_data)

    def action_disconnect(self):
        if self.cfg_view.has_focus or not self.is_connected:
            return
        if self.update_timer:
            self.update_timer.stop()
            self.update_timer = None
        self.is_connected = False
        self.sub_title = f"{self.VARIANT}  ·  ○ Disconnected"
        self.write_log("Disconnected")
        if self.source:
            self.source.stop()
            self.source = None
        while not self.queue.empty():
            self.queue.get()

    # ---------- data tick ----------
    def update_data(self):
        self._update_resources()
        try:
            while not self.queue.empty():
                line = self.queue.get()
                if not line:
                    self.nodata += 1
                    continue
                self.nodata = 0
                kind, _, payload = line.partition(":")
                if kind == "data":
                    try:
                        parsed = get_data(payload)
                    except Exception as e:
                        self.write_log(f"Error parsing data: {e}")
                        continue
                    self._ingest(parsed)
                    self.write_log(payload.strip())
                elif kind == "info":
                    self.write_log(payload.strip())
            if self.source is not None and not self.source.is_alive():
                self.write_log("Data source stopped unexpectedly")
                self.action_disconnect()
        except Exception as e:
            self.write_log(f"Error in update_data: {e}")

    def _ingest(self, parsed):
        self.tim += 1
        for key in ALL_KEYS:
            if key in parsed:
                try:
                    self.series[key].push(float(parsed[key]))
                except (ValueError, TypeError):
                    pass
        self.last_di = parsed.get("Di", "0")
        self.paint()

    def _update_resources(self):
        if not hasattr(self, "res"):
            return
        try:
            import psutil
            p = psutil.Process()
            self.res.update(
                f"[dim]Resources[/dim]   CPU {p.cpu_percent(interval=None):.1f}% "
                f"[dim]·[/dim] RAM {p.memory_info().rss / 1024 / 1024:.0f} MB"
            )
        except Exception:
            self.res.update("[dim]Resources unavailable[/dim]")

    # ---------- log ----------
    def write_log(self, data):
        self.lineno += 1
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"{self.lineno:05d} {ts} │ {data}"
        self.data_log.write(line)
        self.log_file.write(line + "\n")
        self.log_file.flush()

    # ---------- race ----------
    def action_toggle_race(self):
        if self.cfg_view.has_focus:
            return
        if not self.race.running:
            self.race.start()
            self.write_log("Race started")
            if self.race_timer:
                self.race_timer.stop()
            self.race_timer = self.set_interval(0.25, self._race_tick)
        elif self.race.paused:
            self.race.resume()
            self.write_log("Race resumed")
        else:
            self.race.pause()
            self.write_log("Race paused")
        self.paint_race()

    def action_reset_race(self):
        if self.cfg_view.has_focus:
            return
        self.race.reset()
        if self.race_timer:
            self.race_timer.stop()
            self.race_timer = None
        self.write_log("Race reset")
        self.paint_race()

    def action_log_stick(self):
        if self.cfg_view.has_focus:
            return
        if self.race.log_stick():
            self.write_log("Hydrogen stick changed")
            self.paint_race()

    def action_log_battery(self):
        if self.cfg_view.has_focus:
            return
        if self.race.log_battery():
            self.write_log("Battery changed")
            self.paint_race()

    def _race_tick(self):
        self.race.tick()
        self.paint_race()

    # ---------- command line ----------
    def action_open_command(self):
        self.push_screen(InputScreen(title="Command line"), self.handle_command)

    def handle_command(self, message):
        if not message:
            return
        if message.startswith("log "):
            self.write_log(message[4:].strip())
        elif message.startswith("plot "):
            try:
                args = split(message[5:].strip())
                subprocess.Popen(["python", "plotdata.py"] + args, stdout=subprocess.PIPE, text=True)
            except Exception as e:
                self.write_log(str(e))

    # ---------- config tab ----------
    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = str(event.path)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self.write_log(f"Error loading {path}: {e}")
            return
        if event.control.id == "config_tree" and path.endswith(".json"):
            self.cfg_view.load_text(content)
            self.current_config_file = path
        elif path.endswith(".md"):
            self.md.document.update(content)

    def action_save_config(self):
        if not self.cfg_view.has_focus or self.current_config_file is None:
            return
        try:
            with open(self.current_config_file, "w", encoding="utf-8") as f:
                f.write(self.cfg_view.text)
            self.write_log(f"Saved config: {os.path.basename(self.current_config_file)}")
            self.action_reload_config()
        except Exception as e:
            self.write_log(f"Error saving config: {e}")

    def action_reload_config(self):
        self.race.apply_config(load_race_config())
        self.error_config = load_error_config()
        self.error_map = self._build_error_map(self.error_config)
        self.paint_race()
        self.write_log("Config reloaded")

    # ---------- quit ----------
    def action_request_quit(self):
        self.push_screen(QuitScreen(), self._do_quit)

    def _do_quit(self, result):
        if result is None:
            return
        if self.source is not None:
            self.source.stop()
        try:
            self.log_file.close()
        except Exception:
            pass
        self.exit()


# ============================================================
# Direction B — Hero Grid (recommended)
# ============================================================
class HeroGridApp(BaseTelemetryApp):
    VARIANT = "B · Hero Grid"
    CSS = BASE_CSS + """
    #dash_pane { height: 1fr; }
    #heroes { height: 10; grid-size: 4 1; grid-gutter: 1; margin-bottom: 1; }
    #midrow { height: 1fr; margin-bottom: 1; }
    #midrow > .racepanel { width: 1fr; margin-right: 1; }
    #midrow > #log { width: 1fr; }
    #secondary { height: 3; }
    .mini { border: round #232c38; background: $surface; padding: 0 1; content-align: left middle; }
    #secondary > .mini { width: 1fr; margin-right: 1; }
    #secondary > #res { width: 1fr; border: round #232c38; background: $surface; padding: 0 1; content-align: left middle; }
    """

    def compose_dashboard(self) -> ComposeResult:
        with Vertical(id="dash_pane"):
            self.alert = AlertStrip()
            yield self.alert
            with Grid(id="heroes"):
                for key in HERO_KEYS:
                    tile = HeroTile(key)
                    self.tiles[key] = tile
                    yield tile
            with Horizontal(id="midrow"):
                self.race_panel = RacePanel(self.race)
                yield self.race_panel
                self.data_log = RichLog(highlight=False, markup=True, max_lines=200, id="log")
                self.data_log.border_title = "Log"
                yield self.data_log
            with Horizontal(id="secondary"):
                self.iout = MiniMetric("Iout")
                self.vfc = MiniMetric("Vfc")
                self.res = Static("", classes="panel", id="res")
                yield self.iout
                yield self.vfc
                yield self.res

    def paint_dashboard(self):
        self.update_alert()
        for key, tile in self.tiles.items():
            tile.refresh_metric(self.series[key])
        self.iout.refresh_metric(self.series["Iout"])
        self.vfc.refresh_metric(self.series["Vfc"])

    def paint_race(self):
        self.race_panel.refresh_race()


# ============================================================
# Direction A — Refined Classic
# ============================================================
class RefinedClassicApp(BaseTelemetryApp):
    VARIANT = "A · Refined Classic"
    CSS = BASE_CSS + """
    #a_grid { grid-size: 2 1; grid-columns: 42fr 58fr; height: 1fr; }
    #a_left { height: 100%; }
    #a_left > * { margin-bottom: 1; }
    #a_right { height: 100%; }
    #a_right > * { margin-bottom: 1; }
    #a_right > #log { height: 1fr; }
    .conn { height: 3; border: round #232c38; background: $surface; border-title-color: $primary; padding: 0 1; content-align: left middle; }
    .readouts { height: auto; }
    .stats { height: auto; }
    .res { height: 3; content-align: left middle; }
    """

    def compose_dashboard(self) -> ComposeResult:
        with Grid(id="a_grid"):
            with VerticalScroll(id="a_left"):
                self.conn_line = Static("", classes="conn")
                self.conn_line.border_title = "Connection"
                yield self.conn_line
                self.alert = AlertStrip()
                yield self.alert
                self.readouts = Static("", classes="panel readouts")
                self.readouts.border_title = "Live Readouts"
                yield self.readouts
                self.race_panel = RacePanel(self.race)
                yield self.race_panel
            with Vertical(id="a_right"):
                self.data_log = RichLog(highlight=False, markup=True, max_lines=200, id="log")
                self.data_log.border_title = "Log"
                yield self.data_log
                self.stats = Static("", classes="panel stats")
                self.stats.border_title = "Statistics"
                yield self.stats
                self.res = Static("", classes="panel res")
                yield self.res

    def paint_dashboard(self):
        self.update_alert()
        self._paint_conn()
        lines = []
        for key in TABLE_KEYS:
            m = METRICS[key]
            lines.append(
                f"[dim]{m['label']:<22}[/dim] {self.smarkup(key, 12)} "
                f"[b]{self.fmt(key, self.series[key].v)}[/b][dim]{m['unit']}[/dim]"
            )
        self.readouts.update("\n".join(lines))
        self.stats.update(self._stats_text())

    def _paint_conn(self):
        if self.is_connected:
            t = self.connection_config.get("type")
            src = "simulation_data.py" if t == "simulated" else \
                f"{self.connection_config.get('port')} @ {self.connection_config.get('baudrate')}"
            self.conn_line.update(f"[{PALETTE['accent']}]●[/] Connected   [dim]{src}[/dim]")
        else:
            self.conn_line.update(f"[{PALETTE['red']}]○[/] Disconnected")

    def _stats_text(self):
        rows = [f"[dim]window: {self._window_label()}[/dim]"]
        for key in TABLE_KEYS:
            m = METRICS[key]
            st = self.series[key].window_stats(self.stats_window)
            chan = f"[{m['color']}]{key:<5}[/][dim]{m['unit']:<4}[/dim]"
            if st is None:
                rows.append(f"{chan} [dim]-- · -- · --[/dim]")
            else:
                mn, mx, avg, n = st
                d = m["dec"]
                rows.append(f"{chan} {mn:.{d}f} · {mx:.{d}f} · [b]{avg:.{d}f}[/b]")
        return "\n".join(rows)

    def paint_race(self):
        self.race_panel.refresh_race()


VARIANTS = {"a": RefinedClassicApp, "b": HeroGridApp}
VARIANT_INFO = [
    ("a", "A · Refined Classic",
     "Your current layout, tidied: left rail of panels beside the log. Lowest-risk port."),
    ("b", "B · Hero Grid  (recommended)",
     "Pout / Pfc / Vbat / Tfc become big tiles with their own trend line."),
]


# ============================================================
# Launcher
# ============================================================
class LauncherApp(App):
    CSS = """
    Screen { background: $background; align: center middle; }
    #wrap { width: 78; height: auto; }
    #title { text-style: bold; color: $primary; margin-bottom: 1; }
    #subtitle { color: $text-muted; margin-bottom: 1; }
    OptionList { height: auto; border: round #232c38; background: $surface; padding: 1 1; }
    #hint { color: $text-muted; margin-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Quit"),
        Binding("1", "pick('a')", "A", show=False),
        Binding("2", "pick('b')", "B", show=False),
    ]

    def on_mount(self):
        self.register_theme(H2_THEME)
        self.theme = "h2car"
        self.title = "h2car · telemetry"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="wrap"):
            yield Static("h2car telemetry — choose a dashboard design", id="title")
            yield Static("Two terminal-faithful directions. Same live backend.", id="subtitle")
            opts = []
            for vid, name, desc in VARIANT_INFO:
                t = Text()
                t.append(f"{name}\n", style="bold")
                t.append(desc, style="dim")
                opts.append(Option(t, id=vid))
            yield OptionList(*opts, id="picker")
            yield Static("↑/↓ + Enter, or press 1 / 2 · Esc to quit", id="hint")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.exit(event.option.id)

    def action_pick(self, vid: str) -> None:
        self.exit(vid)

    def action_cancel(self) -> None:
        self.exit(None)


def main():
    parser = argparse.ArgumentParser(description="h2car telemetry — redesigned UI")
    parser.add_argument("--variant", choices=["a", "b"],
                        help="Skip the launcher and run a specific direction.")
    args = parser.parse_args()

    choice = args.variant or LauncherApp().run()
    if choice in VARIANTS:
        VARIANTS[choice]().run()


if __name__ == "__main__":
    main()
