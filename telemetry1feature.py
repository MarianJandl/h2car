from datetime import datetime
import subprocess
from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.widgets import Header, Footer, Static, RichLog, TabbedContent, TabPane, MarkdownViewer, DirectoryTree, ProgressBar, TextArea
from textual.binding import Binding
import os
from pathlib import Path
from typing import Iterable
import threading
from queue import Queue
import time
import json
import shlex

from bin.connectionscreen import *
from bin.connectionstatus import *
from bin.quitscreen import *
from bin.resourcemonitor import *
from bin.dashboard import *
from bin.statsdashboard import *
from bin.errorstatus import *
from bin.inputscreen import *

di = 0
tim = 0
lineno = 0
nodata = 0

napomenutiF = 0
napomenutiV = 0

x = datetime.now().strftime("%Y%m%d")
k = 0

if not os.path.exists("./logs/"):
    os.mkdir("logs")
    
while os.path.exists(f"./logs/appdatalog{x}_{k}.txt"):
    k += 1

with open(f"./logs/appdatalog{x}_{k}.txt", "a") as f:
    f.write(f"--- New session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")


def get_data(data):
    data = dict(p.split(":") for p in data.split())
    return data

def load_race_config():
    """Load race configuration from file"""
    config_path = Path("config/race_config.json")
    default_config = {
        "race_duration_seconds": 3600,
        "hydrogen_stick_count": 4,
        "battery_count": 2,
        "race_name": "Hydrogen Race",
        "enable_alerts": True,
        "alert_threshold_percent": 10
    }
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        except Exception:
            pass
    
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    return default_config

class RaceTracker(Static):
    """Widget to track race progress and component changes"""
    
    def __init__(self):
        super().__init__()
        self.config = load_race_config()
        self.race_start_time = None
        self.is_racing = False
        self.is_paused = False
        self.elapsed_time = 0
        self.pause_start_time = None
        self.total_pause_duration = 0
        self.stick_changes = 0
        self.battery_changes = 0
        
        # Track when last changes occurred
        self.last_stick_change_time = 0
        self.last_battery_change_time = 0
        
        # Initial intervals
        self.stick_interval = self.config["race_duration_seconds"] / self.config["hydrogen_stick_count"]
        self.battery_interval = self.config["race_duration_seconds"] / self.config["battery_count"]
        
        # Current expected intervals (recalculated after each change)
        self.current_stick_interval = self.stick_interval
        self.current_battery_interval = self.battery_interval
    
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(id="race_info")
            yield Static("[bold]Hydrogen Stick Progress:[/bold]", id="stick_label")
            yield ProgressBar(total=100, show_eta=False, id="stick_progress")
            yield Static(id="stick_info")
            yield Static("[bold]Battery Progress:[/bold]", id="battery_label")
            yield ProgressBar(total=100, show_eta=False, id="battery_progress")
            yield Static(id="battery_info")
    
    def on_mount(self):
        self.update_display()
    
    def reload_race_config(self):
        self.config = load_race_config()
        # Recalculate base intervals
        self.stick_interval = self.config["race_duration_seconds"] / self.config["hydrogen_stick_count"]
        self.battery_interval = self.config["race_duration_seconds"] / self.config["battery_count"]
        
        # If racing, recalculate current intervals based on remaining items
        if self.is_racing and not self.is_paused:
            sticks_remaining = self.config["hydrogen_stick_count"] - self.stick_changes
            batteries_remaining = self.config["battery_count"] - self.battery_changes
            time_remaining = self.config["race_duration_seconds"] - self.elapsed_time
            
            if sticks_remaining > 0:
                self.current_stick_interval = time_remaining / sticks_remaining
            if batteries_remaining > 0:
                self.current_battery_interval = time_remaining / batteries_remaining
        else:
            self.current_stick_interval = self.stick_interval
            self.current_battery_interval = self.battery_interval

    def start_race(self):
        """Start the race from the beginning"""
        self.race_start_time = time.time()
        self.is_racing = True
        self.is_paused = False
        self.elapsed_time = 0
        self.total_pause_duration = 0
        self.pause_start_time = None
        self.stick_changes = 0
        self.battery_changes = 0
        self.last_stick_change_time = 0
        self.last_battery_change_time = 0
        self.current_stick_interval = self.stick_interval
        self.current_battery_interval = self.battery_interval
    
    def pause_race(self):
        """Pause the race"""
        if self.is_racing and not self.is_paused:
            self.is_paused = True
            self.pause_start_time = time.time()
    
    def resume_race(self):
        """Resume the race from pause"""
        if self.is_racing and self.is_paused:
            self.is_paused = False
            # Add the pause duration to total
            if self.pause_start_time:
                self.total_pause_duration += time.time() - self.pause_start_time
                self.pause_start_time = None
    
    def stop_race(self):
        """Stop/pause the race (alias for pause)"""
        self.pause_race()
    
    def reset_race(self):
        """Reset the race completely"""
        self.race_start_time = None
        self.is_racing = False
        self.is_paused = False
        self.elapsed_time = 0
        self.total_pause_duration = 0
        self.pause_start_time = None
        self.stick_changes = 0
        self.battery_changes = 0
        self.last_stick_change_time = 0
        self.last_battery_change_time = 0
        self.current_stick_interval = self.stick_interval
        self.current_battery_interval = self.battery_interval
        self.update_display()
    
    def log_stick_change(self):
        if not self.is_racing or self.is_paused:
            return 1
        
        # Check if we've reached the limit
        if self.stick_changes >= self.config["hydrogen_stick_count"]:
            return 1 # Already used all sticks
        
        self.stick_changes += 1
        self.last_stick_change_time = self.elapsed_time
        
        # Recalculate interval: distribute remaining time evenly among remaining sticks
        sticks_remaining = self.config["hydrogen_stick_count"] - self.stick_changes
        if sticks_remaining > 0:
            time_remaining = self.config["race_duration_seconds"] - self.elapsed_time
            self.current_stick_interval = time_remaining / sticks_remaining
        
        self.update_display()
        return 0
    
    def log_battery_change(self):
        if not self.is_racing or self.is_paused:
            return 1
        
        # Check if we've reached the limit
        if self.battery_changes >= self.config["battery_count"]:
            return 1 # Already used all batteries
        
        self.battery_changes += 1
        self.last_battery_change_time = self.elapsed_time
        
        # Recalculate interval: distribute remaining time evenly among remaining batteries
        batteries_remaining = self.config["battery_count"] - self.battery_changes
        if batteries_remaining > 0:
            time_remaining = self.config["race_duration_seconds"] - self.elapsed_time
            self.current_battery_interval = time_remaining / batteries_remaining
        
        self.update_display()
        return 0
    
    def update_timer(self):
        if self.is_racing and self.race_start_time:
            if not self.is_paused:
                # Calculate elapsed time excluding all pause durations
                self.elapsed_time = time.time() - self.race_start_time - self.total_pause_duration
            self.update_display()
    
    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def update_display(self):
        race_duration = self.config["race_duration_seconds"]
        
        if self.is_racing:
            race_progress = min((self.elapsed_time / race_duration) * 100, 100)
            time_remaining = max(race_duration - self.elapsed_time, 0)
            
            # Calculate time since last change
            time_since_stick = self.elapsed_time - self.last_stick_change_time
            time_since_battery = self.elapsed_time - self.last_battery_change_time
            
            # Calculate remaining percentage (100% = just changed, 0% = time to change)
            stick_remaining_percent = max(0, 100 - (time_since_stick / self.current_stick_interval) * 100)
            battery_remaining_percent = max(0, 100 - (time_since_battery / self.current_battery_interval) * 100)
            
            # Calculate time left until expected change
            stick_time_left = max(0, self.current_stick_interval - time_since_stick)
            battery_time_left = max(0, self.current_battery_interval - time_since_battery)
            
            # Calculate efficiency (how much longer than expected)
            stick_over_percent = 0
            battery_over_percent = 0
            
            if time_since_stick > self.current_stick_interval:
                stick_over_percent = ((time_since_stick - self.current_stick_interval) / self.current_stick_interval) * 100
            
            if time_since_battery > self.current_battery_interval:
                battery_over_percent = ((time_since_battery - self.current_battery_interval) / self.current_battery_interval) * 100
            
            sticks_remaining = self.config["hydrogen_stick_count"] - self.stick_changes
            batteries_remaining = self.config["battery_count"] - self.battery_changes
            
            # Set status based on pause state
            if self.is_paused:
                status = "[yellow]⏸ PAUSED[/yellow]"
            else:
                status = "[green]● RACING[/green]"
            
            # Update progress bars
            stick_bar = self.query_one("#stick_progress", ProgressBar)
            battery_bar = self.query_one("#battery_progress", ProgressBar)
            
            # Set progress and colors
            stick_bar.update(progress=stick_remaining_percent)
            if stick_over_percent > 0:
                stick_bar.styles.color = "green"
            elif stick_remaining_percent < 10:
                stick_bar.styles.color = "red"
            elif stick_remaining_percent < 25:
                stick_bar.styles.color = "yellow"
            else:
                stick_bar.styles.color = "green"
            
            battery_bar.update(progress=battery_remaining_percent)
            if battery_over_percent > 0:
                battery_bar.styles.color = "green"
            elif battery_remaining_percent < 10:
                battery_bar.styles.color = "red"
            elif battery_remaining_percent < 25:
                battery_bar.styles.color = "yellow"
            else:
                battery_bar.styles.color = "green"
            
            # Build status display
            stick_status = ""
            if stick_over_percent > 0:
                stick_status = f" [green]↑ {stick_over_percent:.1f}% over expected![/green]"
            elif stick_remaining_percent < 10:
                stick_status = " [bold red]Change now![/bold red]"
            elif stick_remaining_percent < 25:
                stick_status = " [yellow]Change soon[/yellow]"
            
            battery_status = ""
            if battery_over_percent > 0:
                battery_status = f" [green]↑ {battery_over_percent:.1f}% over expected![/green]"
            elif battery_remaining_percent < 10:
                battery_status = " [bold red]Change now[/bold red]"
            elif battery_remaining_percent < 25:
                battery_status = " [yellow]Change soon[/yellow]"
            
            # Build keyboard shortcuts hint
            if self.is_paused:
                shortcuts = "Press [bold]P[/bold] to resume | Press [bold]Shift+R[/bold] to reset"
            else:
                shortcuts = "Press [bold]P[/bold] to pause | Press [bold]Shift+R[/bold] to reset"
            
            # Update text displays
            race_info = self.query_one("#race_info", Static)
            race_info.update(f"""[bold cyan]Race Tracker[/bold cyan] {status}

Race: {self.config['race_name']}
Time: {self.format_time(self.elapsed_time)} / {self.format_time(race_duration)}
Remaining: {self.format_time(time_remaining)} ({100-race_progress:.1f}%)

{shortcuts}
""")
            
            stick_label = self.query_one("#stick_label", Static)
            stick_label.update(f"[bold]Hydrogen Stick:[/bold] {self.stick_changes}/{self.config['hydrogen_stick_count']} changes ({sticks_remaining} remaining)")
            
            stick_info = self.query_one("#stick_info", Static)
            if stick_time_left > 0:
                stick_info.update(f"Time left to estimated change: {self.format_time(stick_time_left)} ({stick_remaining_percent:.1f}% remaining){stick_status}")
            else:
                stick_info.update(f"Time in use: {self.format_time(time_since_stick)} (Expected: {self.format_time(self.current_stick_interval)}){stick_status}")
            
            battery_label = self.query_one("#battery_label", Static)
            battery_label.update(f"[bold]Battery:[/bold] {self.battery_changes}/{self.config['battery_count']} changes ({batteries_remaining} remaining)")
            
            battery_info = self.query_one("#battery_info", Static)
            if battery_time_left > 0:
                battery_info.update(f"Time left to estimated change: {self.format_time(battery_time_left)} ({battery_remaining_percent:.1f}% remaining){battery_status}")
            else:
                battery_info.update(f"Time in use: {self.format_time(time_since_battery)} (Expected: {self.format_time(self.current_battery_interval)}){battery_status}")
            
        else:
            race_info = self.query_one("#race_info", Static)
            race_info.update(f"""[bold cyan]Race Tracker[/bold cyan] [dim]○ Not Started[/dim]

Race: {self.config['race_name']}
Duration: {self.format_time(race_duration)}
Hydrogen sticks: {self.config['hydrogen_stick_count']} (change every {self.format_time(self.stick_interval)})
Batteries: {self.config['battery_count']} (change every {self.format_time(self.battery_interval)})

Press [bold]R[/bold] to start race | Press [bold]Shift+R[/bold] to reset
""")
            
            stick_label = self.query_one("#stick_label", Static)
            stick_label.update("[bold]Hydrogen Stick Progress:[/bold]")
            
            battery_label = self.query_one("#battery_label", Static)
            battery_label.update("[bold]Battery Progress:[/bold]")
            
            stick_info = self.query_one("#stick_info", Static)
            stick_info.update("Not started")
            
            battery_info = self.query_one("#battery_info", Static)
            battery_info.update("Not started")
            
            stick_bar = self.query_one("#stick_progress", ProgressBar)
            battery_bar = self.query_one("#battery_progress", ProgressBar)
            stick_bar.update(progress=100)
            battery_bar.update(progress=100)

class FilteredDirectoryTreeDocs(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if (path.name.endswith(".md") or path.is_dir()) and not path.name.startswith(".")]

class FilteredDirectoryTreeConfig(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if (path.name.endswith(".json") or path.is_dir()) and not path.name.startswith(".")]


class DashboardLogApp(App):
    CSS = """
        #main_grid {
            grid-size: 2 1;
            grid-columns: 4fr 6fr;
        
        }
        #docs_grid {
            grid-size: 2 1;
            grid-columns: 3fr 7fr;
        
        }
        #config_grid {
            grid-size: 2 1;
            grid-columns: 3fr 7fr;
        
        }
        Dashboard {
            padding: 1 1 0 1;
        }
        StatsDashboard {
            padding: 1 1 0 1;
            
        }
        RichLog {
            padding: 1;
        }
        ConnectionStatus {
            padding: 1 1 0 1;
            height: 2;
            
        }

        ErrorStatus {
            padding: 1 1 1 1;
            height: auto;
            max-height: 6;
            border: solid gray;
        }

        #error_scroll {
            height: auto;
            max-height: 6;

        }

        #error_header {
            padding: 0 0 1 0;
        }


        ResourceMonitor {
            padding: 1;
            height: 4;
            dock: bottom;
        }
        
        DirectoryTree {
            height: 100%;
            border: solid $primary;
        }
        
        MarkdownViewer {
            height: 100%;
            border: solid $primary;
        }
        TextArea {
            height: 100%;
            border: solid $primary;
        }

        RaceTracker {
            padding: 1 1 0 1;
            
            
        }
        """
    
    BINDINGS = [
        Binding("c", "open_connection", "Connection", show=True, priority=False),
        Binding("ctrl+d", "disconnect", "Disconnect", show=True, priority=False),
        Binding("ctrl+q", "request_quit", "Quit", show=True, priority=False),
        Binding("r", "start_race", "Start Race", show=True, priority=False),
        Binding("p", "pause_resume_race", "Pause/Resume", show=True, priority=False),
        Binding("ctrl+r", "reset_race", "Reset Race", show=True, priority=False),
        Binding("h", "log_hydrostick", "Log Hydrostick", show=True, priority=True),
        Binding("ctrl+b", "log_battery", "Log Battery", show=True, priority=False),
        Binding("ctrl+l", "reload_config", "Reload Config", show=True, priority=False),
        Binding("ctrl+s", "save_config", "Save Config", show=True, priority=False),
        Binding("m", "open_input", "Command line", show=True, priority=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.is_connected = False
        self.connection_config = None
        self.update_timer = None
        self.data_stream = None
        self.queue = Queue()
        self.read_thread = None
        self.stop_event = None
        self.race_timer = None
        self.current_config_file = None
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with TabbedContent():
            with TabPane("Dashboard & Log", id="tab_dashboard"):
                with Grid(id="main_grid"):
                    with Vertical():
                        self.conn_status = ConnectionStatus()
                        yield self.conn_status
                        
                        self.err_status = ErrorStatus()
                        yield self.err_status

                        self.dashboard = Dashboard()
                        yield self.dashboard

                        self.stats = StatsDashboard()
                        yield self.stats
                        
                        self.race_tracker = RaceTracker()
                        yield self.race_tracker

                        self.resource_monitor = ResourceMonitor()
                        yield self.resource_monitor
                        
                    self.data_log = RichLog(highlight=False, markup=True)
                    yield self.data_log
                    
            with TabPane("Docs", id="tab_docs"):
                with Grid(id="docs_grid"):
                    self.directory_tree = FilteredDirectoryTreeDocs("./", id="doc_tree")
                    yield self.directory_tree

                    self.markdown_viewer = MarkdownViewer("# Documentation\n\nSelect a markdown file from the directory tree to view it here.", show_table_of_contents=True)
                    self.markdown_viewer.code_indent_guides = False
                    yield self.markdown_viewer
                    
            with TabPane("Config", id="tab_config"):
                with Grid(id="config_grid"):
                    self.config_tree = FilteredDirectoryTreeConfig("./config", id="config_tree")
                    yield self.config_tree

                    self.config_viewer = TextArea("", language="json", show_line_numbers=True)
                    yield self.config_viewer

        yield Footer()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Called when a file is selected in the directory tree."""
        file_path = str(event.path)
        
        # Check if it's from the config tree
        if event.control.id == "config_tree" and file_path.endswith('.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.config_viewer.load_text(content)
                    self.current_config_file = file_path
            except Exception as e:
                self.config_viewer.load_text(f"# Error loading file: {str(e)}")

        # Check if it's a markdown file from docs tree
        elif file_path.endswith('.md'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.markdown_viewer.document.update(content)
            except Exception as e:
                error_msg = f"# Error\n\nCould not load file: {file_path}\n\nError: {str(e)}"
                self.markdown_viewer.document.update(error_msg)
                
    def reader_thread(self, stream, q, stop_event):
        while not stop_event.is_set():
            line = stream.readline()
            if line:
                q.put(line.strip())
            else:
                time.sleep(0.05)     

    def write_log(self, data):
        # Function to write to log with line number and time
        timestamp = datetime.now().strftime("%H:%M:%S")
        global lineno, x, k
        lineno += 1
        ln = str(lineno).zfill(5)
        self.data_log.write(f"{ln} {timestamp} | {data}")
        with open(f"./logs/appdatalog{x}_{k}.txt", "a") as f:
            f.write(f"{ln} {timestamp} | {data}\n")

    def action_request_quit(self):
        self.push_screen(QuitScreen(), self.actually_quit)
        
    def actually_quit(self, result):
        if result is None:
            return
        else:
            self.action_disconnect()
            if self.data_stream != None:
                self.data_stream.terminate()
            self.exit()

    def action_open_connection(self):
        """Open the connection settings dialog"""
        if self.config_viewer.has_focus:
            return
        if self.is_connected:
            self.write_log("Already connected. Disconnect first to change connection.")
            return
        self.push_screen(ConnectionScreen(), self.handle_connection)

    def action_disconnect(self):
        if self.config_viewer.has_focus:
            return
        if self.is_connected: 
            if self.update_timer:
                self.update_timer.stop()
                self.update_timer = None
            
            self.connection_config = None
            self.conn_status.update_status("Disconnected")
            self.is_connected = False
            self.update_data()
            self.write_log("Disconnected")
            
            self.stop_event.set()
            if self.read_thread.is_alive():
                self.read_thread.join(timeout=1)

            if self.data_stream:
                self.data_stream.kill()
                self.data_stream = None
            while not self.queue.empty():
                self.queue.get()
            self.stop_event.clear()
    
    def handle_connection(self, config):
        if config is None:
            return
        
        self.connection_config = config
        self.conn_status.update_status("Connecting")
        
        conn_type = config.get("type")
        conn_port = config.get("port")
        conn_baudrate = config.get("baudrate")
        
        if conn_type == "simulated":
            self.data_stream = subprocess.Popen(["python", "simulation_data.py"], stdout=subprocess.PIPE, text=True)
            self.start_data_stream()
        elif conn_type == "serial":
            self.data_stream = subprocess.Popen(["python", "serialcomfeature.py", conn_port, conn_baudrate], stdout=subprocess.PIPE, text=True)
            self.write_log(f"{conn_type} connection to {conn_port} @ {conn_baudrate} ")
            self.start_data_stream()
        
    def action_open_input(self):
        """Open the input dialog to log custom message"""
        self.push_screen(
            InputScreen(title="Command line", placeholder="Enter command..."),
            self.handle_input
        )
    
    def handle_input(self, message):
        """Handle the input from the dialog"""
        if message:
            if message.startswith("log "):
                self.write_log(f"{message[3:].strip()}")
            elif message.startswith("n "):
                global napomenutiF, napomenutiV
                args = message.split()
                try:
                    if args[1].lower() == "v":
                        if args[2] == "+":
                            try:
                                napomenutiV += int(args[3])
                            except Exception as e:
                                self.write_log(e)
                                return
                        if args[2] == "-":
                            try:
                                napomenutiV -= int(args[3])
                            except Exception as e:
                                self.write_log(e)
                                return
                    elif args[1].lower() == "f":
                        if args[2] == "+":
                            try:
                                napomenutiF += int(args[3])
                            except Exception as e:
                                self.write_log(e)
                                return
                        if args[2] == "-":
                            try:
                                napomenutiF -= int(args[3])
                            except Exception as e:
                                self.write_log(e)
                                return
                    else:
                        self.write_log(f"unknown name {args[1]}")
                except Exception as e:
                    self.write_log(e)
            elif message.startswith("plot "):
                try:
                    args = shlex.split(message[4:].strip())
                    subprocess.Popen(["python", "plotdata.py"]+args, stdout=subprocess.PIPE, text=True)
                except Exception as e:
                    self.write_log(e)
            else:
                return
        else:
            return
    
    def start_data_stream(self):
        self.is_connected = True
        self.conn_status.update_status("Connected", self.connection_config)
        
        if self.connection_config.get("type") == "simulated":
            self.write_log("Connected successfully to stdout of simulation_data.py script")
        elif self.connection_config.get("type") == "serial":
            self.write_log("Connected successfully to stdout of serialcom.py script")
        
        self.stop_event = threading.Event()
        self.read_thread = threading.Thread(target=self.reader_thread, args=(self.data_stream.stdout, self.queue, self.stop_event), daemon=True)
        self.read_thread.start()
        
        if self.update_timer:
            self.update_timer.stop()
        self.update_timer = self.set_interval(1, self.update_data)
    
    def update_data(self):    
        self.resource_monitor.update_resources()
        try:
            global nodata, napomenutiF, napomenutiV

            if not self.is_connected:
                data = None
                self.dashboard.update_data(None)
                self.stats.update_stats(None, napomenutiF, napomenutiV)
                self.err_status.update_status(None, nodata)
                return
                
            data = None
            parsed_data = None
    
            while not self.queue.empty():
                data = self.queue.get()
                        
                if not data:
                    nodata += 1
                    self.err_status.update_status(None, nodata)
                    return

                nodata = 0
                data_type = data.split(":", 1)
                
                if data_type[0] == "data":
                    try:
                        parsed_data = get_data(data_type[1])
                    except Exception as e:
                        self.write_log(f"Error parsing data: {str(e)}")
                        return
                    self.write_log(f"{data_type[1].strip()}")
                    self.dashboard.update_data(parsed_data)
                    self.stats.update_stats(parsed_data, napomenutiF, napomenutiV)
                    self.err_status.update_status(parsed_data, nodata)
                elif data_type[0] == "info":
                    self.write_log(f"{data_type[1].strip()}")
                    return
                else:
                    self.write_log(f"Data in wrong format: {data}")
                    return
                    
            data_stream_status = self.data_stream.poll()
            if data_stream_status is not None:
                self.write_log(f"Data stream status: {data_stream_status}")
                self.action_disconnect()
        except Exception as e:
            self.write_log(f"Error in update_data: {str(e)}")        
            return
            
    def action_start_race(self):
        """Start or resume the race"""
        if self.config_viewer.has_focus:
            return
            
        if not self.race_tracker.is_racing:
            # Starting a new race
            self.race_tracker.start_race()
            self.write_log("Race started")
            if self.race_timer:
                self.race_timer.stop()
            self.race_timer = self.set_interval(0.1, self.update_race)
        elif self.race_tracker.is_paused:
            # Resuming from pause
            self.race_tracker.resume_race()
            self.write_log("Race resumed")
            if self.race_timer:
                self.race_timer.stop()
            self.race_timer = self.set_interval(0.1, self.update_race)
        else:
            # Already racing, do nothing or show message
            self.write_log("Race already in progress")
    
    def action_pause_resume_race(self):
        """Toggle pause/resume for the race"""
        if self.config_viewer.has_focus:
            return
            
        if not self.race_tracker.is_racing:
            self.write_log("No race in progress to pause")
            return
            
        if self.race_tracker.is_paused:
            # Resume the race
            self.race_tracker.resume_race()
            self.write_log("Race resumed")
            if self.race_timer:
                self.race_timer.stop()
            self.race_timer = self.set_interval(0.1, self.update_race)
        else:
            # Pause the race
            self.race_tracker.pause_race()
            self.write_log("Race paused")
            if self.race_timer:
                self.race_timer.stop()
    
    def action_reset_race(self):
        """Reset the race completely"""
        if self.config_viewer.has_focus:
            return
        self.race_tracker.reset_race()
        self.write_log("Race reset")
        if self.race_timer:
            self.race_timer.stop()
    
    def action_log_hydrostick(self):
        """Log a hydrogen stick change"""
        if self.config_viewer.has_focus:
            return
        c = self.race_tracker.log_stick_change()
        if c == 0:
            self.write_log("Hydrogen stick changed")
    
    def action_log_battery(self):
        """Log a battery change"""
        if self.config_viewer.has_focus:
            return
        c = self.race_tracker.log_battery_change()
        if c == 0:
            self.write_log("Battery changed")
    
    def update_race(self):
        """Update the race timer display"""
        self.race_tracker.update_timer()
    
    def action_reload_config(self):
        """Reload the race configuration"""
        self.race_tracker.reload_race_config()
        self.race_tracker.update_display()
        self.write_log("Race configuration reloaded")

    def action_save_config(self):
        """Save the current config file - only works when text editor has focus"""
        if not self.config_viewer.has_focus:
            return
        
        if self.current_config_file is None:
            self.write_log("No config file loaded")
            return
        
        try:
            content = self.config_viewer.text
            with open(self.current_config_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self.write_log(f"Saved config: {os.path.basename(self.current_config_file)}")
            self.action_reload_config()
        except Exception as e:
            self.write_log(f"Error saving config: {str(e)}")
            
if __name__ == "__main__":
    DashboardLogApp().run()