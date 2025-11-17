from datetime import datetime
import subprocess
from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical, Container
from textual.widgets import Header, Footer, Static, RichLog, Button, Label, Select, Input, TabbedContent, TabPane, MarkdownViewer, DirectoryTree, ProgressBar
from textual.screen import ModalScreen
from textual.binding import Binding
import os
from pathlib import Path
from typing import Iterable
import threading
from queue import Queue
import time
import json

from bin.connectionscreen import *
from bin.connectionstatus import *
from bin.quitscreen import *
from bin.resourcemonitor import *

di = 0
tim = 0
lineno = 0
nodata = 0

def get_data(data):
    data = dict(p.split(":") for p in data.split())
    return data

def load_race_config():
    """Load race configuration from file"""
    config_path = Path("race_config.json")
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
        self.elapsed_time = 0
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
    
    def start_race(self):
        self.race_start_time = time.time()
        self.is_racing = True
        self.elapsed_time = 0
        self.stick_changes = 0
        self.battery_changes = 0
        self.last_stick_change_time = 0
        self.last_battery_change_time = 0
        self.current_stick_interval = self.stick_interval
        self.current_battery_interval = self.battery_interval
    
    def stop_race(self):
        self.is_racing = False
    
    def reset_race(self):
        self.race_start_time = None
        self.is_racing = False
        self.elapsed_time = 0
        self.stick_changes = 0
        self.battery_changes = 0
        self.last_stick_change_time = 0
        self.last_battery_change_time = 0
        self.current_stick_interval = self.stick_interval
        self.current_battery_interval = self.battery_interval
        self.update_display()
    
    def log_stick_change(self):
        if not self.is_racing:
            return
        
        self.stick_changes += 1
        self.last_stick_change_time = self.elapsed_time
        
        # Recalculate interval: distribute remaining time evenly among remaining sticks
        sticks_remaining = self.config["hydrogen_stick_count"] - self.stick_changes
        if sticks_remaining > 0:
            time_remaining = self.config["race_duration_seconds"] - self.elapsed_time
            self.current_stick_interval = time_remaining / sticks_remaining
        
        self.update_display()
    
    def log_battery_change(self):
        if not self.is_racing:
            return
        
        self.battery_changes += 1
        self.last_battery_change_time = self.elapsed_time
        
        # Recalculate interval: distribute remaining time evenly among remaining batteries
        batteries_remaining = self.config["battery_count"] - self.battery_changes
        if batteries_remaining > 0:
            time_remaining = self.config["race_duration_seconds"] - self.elapsed_time
            self.current_battery_interval = time_remaining / batteries_remaining
        
        self.update_display()
    
    def update_timer(self):
        if self.is_racing and self.race_start_time:
            self.elapsed_time = time.time() - self.race_start_time
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
            
            # Update text displays
            race_info = self.query_one("#race_info", Static)
            race_info.update(f"""[bold cyan]Race Tracker[/bold cyan] {status}

Race: {self.config['race_name']}
Time: {self.format_time(self.elapsed_time)} / {self.format_time(race_duration)}
Remaining: {self.format_time(time_remaining)} ({100-race_progress:.1f}%)
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

class ErrorStatus(Static):
    def __init__(self):
        super().__init__()
        
        self.update_status(None)
    
    def update_status(self, data):
        global nodata
        if data is None:
            self.update(f"[dim]No data ({nodata})[/dim]")
        else:
            err_code = data['Di']
            if err_code == "0x0" or err_code == "0":
               self.update("[green]Error code: 0 - OK[/green]")
               
            elif err_code == "0x1" or err_code == "1":
                self.update("[yellow]Error code: 1 - Vymen bombicku[/yellow]")
            elif err_code == "0x3" or err_code == "3":
                self.update("[red]Error code: 3 - Neco spatne se clankem[/red]")
            elif err_code == "0x8" or err_code == "8":
                self.update("[red]Error code: 8 - Vymen baterku[/red]")
            elif err_code == "0x9" or err_code == "9":
                self.update("[red]Error code: 9 - Vymen baterku a bombicku asi[/red]")
            elif err_code == "0xb" or err_code == "b" or err_code == "B":
                self.update("[red]Error code: B - Vsechno spatne[/red]")
            else:
                self.update(f"[bold red]Error code {err_code}: Unknown error - I suppose everything is completly fucked - Good luck[/bold red]")
                            
class Dashboard(Static):
    def __init__(self):
        super().__init__()
        self.update_data(None)
    
    def update_data(self, data):
        if data is None:
            self.update(
                "[bold cyan]Dashboard[/bold cyan]\n\n"
                #"[dim]No data[/dim]\n"
                #"Error code: --\n"
                "Napeti na baterce: -- V\n"
                "Proud do menice motoru: -- A\n"
                "Vykon menice motoru: -- W\n"
                "Napeti clanku: -- V\n"
                "Vykon clanku: -- W\n"
                "Teplota clanku: -- °C\n"
                "Seconds since last reset: -- s\n"
            )
        else:
            self.update(
                "[bold cyan]Dashboard[/bold cyan]\n\n"
                #f"Error code: {data['Di']}\n"
                f"Napeti na baterce: {data['Vbat']} V\n"
                f"Proud do menice motoru: {data['Iout']} A\n"
                f"Vykon menice motoru: {data['Pout']} W\n"
                f"Napeti clanku: {data['Vfc']} V\n"
                f"Vykon clanku: {data['Pfc'] } W\n"
                f"Teplota clanku: {data['Tfc']} °C\n"
                f"Seconds since last reset: {data['Tim']} s\n"
            )

class StatsDashboard(Static):
    def __init__(self):
        super().__init__()
        
        self.stats = {
            "Vbat": {"min": float('inf'), "max": float('-inf'), "avg": 0, "count": 0, "sum": 0},
            "Iout": {"min": float('inf'), "max": float('-inf'), "avg": 0, "count": 0, "sum": 0},
            "Pout": {"min": float('inf'), "max": float('-inf'), "avg": 0, "count": 0, "sum": 0},
            "Vfc": {"min": float('inf'), "max": float('-inf'), "avg": 0, "count": 0, "sum": 0},
            "Pfc": {"min": float('inf'), "max": float('-inf'), "avg": 0, "count": 0, "sum": 0},
            "Tfc": {"min": float('inf'), "max": float('-inf'), "avg": 0, "count": 0, "sum": 0}
        }
        self.update_stats(None)
    
    def update_stats(self, data):
        if data == None:
            if self.stats["Vbat"]["count"] == 0:
                self.update(
                    f"[bold cyan]Statistics[/bold cyan]\n\n"
                    f"Vbat: Min: -- V | "
                    f"Max: -- V | Avg: -- V\n"
                    f"Iout: Min: -- A | "
                    f"Max: -- A | Avg: -- A\n"
                    f"Pout: Min: -- W | "
                    f"Max: -- W | Avg: -- W\n"
                    f"Vfc:  Min: -- V | "
                    f"Max: -- V | Avg: -- V\n"
                    f"Pfc:  Min: -- W | "
                    f"Max: -- W | Avg: -- W\n"
                    f"Tfc:  Min: -- °C | "
                    f"Max: -- °C | Avg: -- °C\n"
                )
            else:
                self.update(
                    f"[bold cyan]Statistics[/bold cyan]\n\n"
                    f"Vbat: Min: {self.stats['Vbat']['min']:.2f}V | "
                    f"Max: {self.stats['Vbat']['max']:.2f}V | Avg: -- V\n"
                    f"Iout: Min: {self.stats['Iout']['min']:.2f}A | "
                    f"Max: {self.stats['Iout']['max']:.2f}A | Avg: -- A\n"
                    f"Pout: Min: {self.stats['Tfc']['min']}W | "
                    f"Max: {self.stats['Pout']['max']}W | Avg:-- W\n"
                    f"Vfc:  Min: {self.stats['Vfc']['min']:.2f}V | "
                    f"Max: {self.stats['Vfc']['max']:.2f}V | Avg: -- V\n"
                    f"Pfc:  Min: {self.stats['Tfc']['min']}W | "
                    f"Max: {self.stats['Pfc']['max']}W | Avg: -- W\n"
                    f"Tfc:  Min: {self.stats['Tfc']['min']}°C | "
                    f"Max: {self.stats['Tfc']['max']}°C | Avg: -- °C\n"
                )
        else:
            numeric_keys = ["Vbat", "Iout", "Pout", "Vfc","Pfc", "Tfc"]
            for key in numeric_keys:
                if key in data:
                    value = float(data[key])
                    stat = self.stats[key]
                    stat["min"] = min(stat["min"], value)
                    stat["max"] = max(stat["max"], value)
                    stat["count"] += 1
                    stat["sum"] += value
                    stat["avg"] = stat["sum"] / stat["count"]
            
            self.update(
                f"[bold cyan]Statistics[/bold cyan]\n\n"
                f"Vbat: Min: {self.stats['Vbat']['min']:.2f}V | "
                f"Max: {self.stats['Vbat']['max']:.2f}V | Avg: {self.stats['Vbat']['avg']:.2f}V\n"
                f"Iout: Min: {self.stats['Iout']['min']:.2f}A | "
                f"Max: {self.stats['Iout']['max']:.2f}A | Avg: {self.stats['Iout']['avg']:.2f}A\n"
                f"Pout: Min: {self.stats['Tfc']['min']}W | "
                f"Max: {self.stats['Pout']['max']}W | Avg: {self.stats['Pout']['avg']:.1f}W\n"
                f"Vfc:  Min: {self.stats['Vfc']['min']:.2f}V | "
                f"Max: {self.stats['Vfc']['max']:.2f}V | Avg: {self.stats['Vfc']['avg']:.2f}V\n"
                f"Pfc:  Min: {self.stats['Tfc']['min']}W | "
                f"Max: {self.stats['Pfc']['max']}W | Avg: {self.stats['Pfc']['avg']:.1f}W\n"
                f"Tfc:  Min: {self.stats['Tfc']['min']}°C | "
                f"Max: {self.stats['Tfc']['max']}°C | Avg: {self.stats['Tfc']['avg']:.1f}°C\n"
            )
    
    def reset_stats(self):
        for stat in self.stats.values():
            stat["min"] = float('inf')
            stat["max"] = float('-inf')
            stat["avg"] = 0
            stat["count"] = 0
            stat["sum"] = 0

class FilteredDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if (path.name.endswith(".md") or path.is_dir()) and not path.name.startswith(".")]

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
            padding: 1;
            
            
            border: solid gray;
        }

        ResourceMonitor {
            padding: 1;
            height: 3;
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
        RaceTracker {
            padding: 1 1 0 1;
            
            
        }
        """
    
    BINDINGS = [
        Binding("c", "open_connection", "Connection", show=True),
        Binding("ctrl+d", "disconnect", "Disconnect", show=True),
        Binding("q", "request_quit", "Quit", show=True),
        Binding("ctrl+q", "request_quit", "Quit", show=True),
        Binding("r", "start_race", "Start Race", show=True),
        Binding("ctrl+r", "reset_race", "Reset Race", show=True),
        Binding("ctrl+s", "log_stick", "Log Stick", show=True),
        Binding("ctrl+b", "log_battery", "Log Battery", show=True),
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
                    self.directory_tree = FilteredDirectoryTree("./", id="doc_tree")
                   
                    yield self.directory_tree

                    self.markdown_viewer = MarkdownViewer("# Documentation\n\nSelect a markdown file from the directory tree to view it here.", show_table_of_contents=True)
                    self.markdown_viewer.code_indent_guides = False
                    yield self.markdown_viewer

        yield Footer()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Called when a file is selected in the directory tree."""
        file_path = str(event.path)
        
        # Check if it's a markdown file
        if file_path.endswith('.md'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Update the markdown viewer with new content
                    self.markdown_viewer.document.update(content)
                    #self.write_log(f"Loaded documentation: {os.path.basename(file_path)}")
            except Exception as e:
                error_msg = f"# Error\n\nCould not load file: {file_path}\n\nError: {str(e)}"
                self.markdown_viewer.document.update(error_msg)
                #self.write_log(f"Error loading file: {str(e)}")
        else:
            self.markdown_viewer.document.update(f"# Unsupported File\n\nThe file `{os.path.basename(file_path)}` is not a markdown file.")
            #self.write_log(f"Selected non-markdown file: {os.path.basename(file_path)}")

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
        global lineno
        lineno += 1
        ln = str(lineno).zfill(5)
        self.data_log.write(f"{ln} {timestamp} | {data}")

    def action_request_quit(self):
        self.push_screen(QuitScreen(), self.actually_quit)
        
    def actually_quit(self, result):
        self.write_log(result)
        if result is None:
            return
        else:
            self.action_disconnect()

            if self.data_stream != None:
                self.data_stream.terminate()
            self.exit()

    def action_open_connection(self):
        """Open the connection settings dialog"""
        if self.is_connected:
            self.write_log("Already connected. Disconnect first to change connection.")
            return
        self.push_screen(ConnectionScreen(), self.handle_connection)

    def action_disconnect(self):
        #Disconnect from current data source
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
            #self.update_data()
    
    def handle_connection(self, config):
        #Handle the connection configuration from the dialog
        if config is None:
            return
        
        self.connection_config = config
        self.conn_status.update_status("Connecting")
        
        conn_type = config.get("type")
        conn_port= config.get("port")
        conn_baudrate = config.get("baudrate")
        if conn_type == "simulated":
            self.data_stream = subprocess.Popen(["python", "simulation_data.py"], stdout=subprocess.PIPE, text=True)
            self.start_data_stream()

        elif conn_type == "serial":
            self.data_stream = subprocess.Popen(["python", "serialcom.py", conn_port, conn_baudrate], stdout=subprocess.PIPE, text=True)
            self.write_log(f"{conn_type} connection to {conn_port} @ {conn_baudrate} ")
            self.start_data_stream()
        

    
    def start_data_stream(self):
        #Start receiving data

        self.is_connected = True
        self.conn_status.update_status("Connected", self.connection_config)
        if self.connection_config.get("type") == "simulated":
            self.write_log("Connected successfully to stdout of simulation_data.py script")
        elif self.connection_config.get("type") == "serial":
            self.write_log("Connected successfully to stdout of serialcom.py script")
        
        self.stop_event = threading.Event()
        self.read_thread = threading.Thread(target=self.reader_thread, args=(self.data_stream.stdout, self.queue, self.stop_event), daemon=True)
        self.read_thread.start()
        
        # Start the update timer
        if self.update_timer:
            self.update_timer.stop()
        self.update_timer = self.set_interval(1, self.update_data)
    
    def update_data(self):    
        #Update dashboard with new data
        #self.write_log("reading update")
        
        if not self.is_connected:
            data = None
            self.dashboard.update_data(None)
            self.stats.update_stats(None)
            self.err_status.update_status(None)
            return
            
        data = None
        parsed_data = None
        global nodata
        # Generate or read data based on connection type
   
        while not self.queue.empty():
            
            data = self.queue.get()
                       
            if not data:
                nodata += 1
                self.err_status.update_status(None)
                return
            

            nodata = 0

            data_type = data.split(":", 1)
            
            if data_type[0] == "data":
                parsed_data = get_data(data_type[1])
                self.write_log(f"{data_type[1].strip()}")
                self.dashboard.update_data(parsed_data)
                self.stats.update_stats(parsed_data)
                self.err_status.update_status(parsed_data)
            #self.update_css(parsed_data)
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
            
    def update_css(self, data):
        if data is None:
            self.err_status.styles.border("solid", "gray")
        else:
            err_code = data['Di']
            if err_code == "0x0" or err_code == "0":
              self.err_status.styles.border("solid", "green")
            elif err_code == "0x1" or err_code == "1":
                self.err_status.styles.border("solid", "yellow")
            elif err_code == "0x3" or err_code == "3":
                self.err_status.styles.border("solid", "red")
            elif err_code == "0x8" or err_code == "8":
                self.err_status.styles.border("solid", "red")
            elif err_code == "0x9" or err_code == "9":
                self.err_status.styles.border("solid", "red")
            elif err_code == "0xb" or err_code == "b" or err_code == "B":
                self.err_status.styles.border("solid", "red")
            else:
                self.err_status.styles.border("solid", "red")
    def action_start_race(self):
        if not self.race_tracker.is_racing:
            self.race_tracker.start_race()
            self.write_log("Race started")
            if self.race_timer:
                self.race_timer.stop()
            self.race_timer = self.set_interval(0.1, self.update_race)
        else:
            self.race_tracker.stop_race()
            self.write_log("Race paused")
            if self.race_timer:
                self.race_timer.stop()
    
    def action_reset_race(self):
        self.race_tracker.reset_race()
        self.write_log("Race reset")
        if self.race_timer:
            self.race_timer.stop()
    
    def action_log_stick(self):
        self.race_tracker.log_stick_change()
        self.write_log("Hydrogen stick changed")
    
    def action_log_battery(self):
        self.race_tracker.log_battery_change()
        self.write_log("Battery changed")
    
    def update_race(self):
        self.race_tracker.update_timer()
if __name__ == "__main__":
    DashboardLogApp().run()