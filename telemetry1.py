import psutil
from datetime import datetime
import subprocess
from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical, Container
from textual.widgets import Header, Footer, Static, RichLog, Button, Label, Select, Input, TabbedContent, TabPane, MarkdownViewer, DirectoryTree
from textual.screen import ModalScreen
from textual.binding import Binding
import os
from pathlib import Path
from typing import Iterable

di = 0
tim = 0
lineno = 0
nodata = 0

def get_data(data):
    data = dict(p.split(":") for p in data.split())
    return data

class QuitScreen(ModalScreen):
    """Screen with a dialog to quit."""

    CSS = """
        QuitScreen {
        align: center middle;
        }

        #dialog {
            grid-size: 2;
            grid-gutter: 1 2;
            grid-rows: 1fr 3;
            padding: 0 1;
            width: 60;
            height: 11;
            border: thick $background 80%;
            background: $surface;
        }

        #question {
            column-span: 2;
            height: 1fr;
            width: 1fr;
            content-align: center middle;
        }

        Button {
            width: 100%;
        }   
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel", show=True),
    ]

    def __init__(self):
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Are you sure you want to quit?", id="question"),
            Button("Quit", variant="error", id="quit"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.dismiss({
                "result": True
            })
        elif event.button.id == "cancel":
            self.dismiss(None)

class ConnectionScreen(ModalScreen):
    CSS = """
    ConnectionScreen {
        align: center middle;
    }
    
    #connection_dialog {
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    #serial_settings {
        width:auto;
        height: auto;
        
        background: $surface;
        
    }
    
    #connection_dialog Label {
        margin: 1 0;
    }
    
    #connection_dialog Input {
        margin-bottom: 1;
    }
    
    #connection_dialog Select {
        margin-bottom: 1;
    }
    
    #button_container {
        layout: horizontal;
        height: auto;
        margin-top: 1;
    }
    
    #button_container Button {
        margin: 0 1;
    }
    .hidden {
        display: none;
    }
    """
    
    BINDINGS = [
        Binding("escape", "dismiss", "Cancel", show=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.connection_type = "simulated"
        self.port = ""
        self.baudrate = "9600"
    
    def compose(self) -> ComposeResult:
        with Container(id="connection_dialog"):
            yield Label("[bold cyan]Connection Settings[/bold cyan]")
            yield Label("Connection Type:")
            yield Select(
                [
                    ("Simulated Data", "simulated"),
                    ("Serial Port", "serial"),

                ],
                id="connection_type",
                value="simulated"
            )
            # Add visibility: hidden by default
            with Container(id="serial_settings", classes="hidden"):
                yield Label("Port/Address (for Serial):")
                yield Input(placeholder="e.g., COM3, /dev/ttyUSB0, or BT address", id="port")
                yield Label("Baudrate (for Serial):")
                yield Select(
                    [
                        ("9600", "9600"),
                        ("19200", "19200"),
                        ("38400", "38400"),
                        ("57600", "57600"),
                        ("115200", "115200"),
                    ],
                    id="baudrate",
                    value="9600"
                )
            with Container(id="button_container"):
                yield Button("Connect", variant="primary", id="connect")
                yield Button("Cancel", variant="default", id="cancel")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "connection_type":
            self.connection_type = event.value
            # Show/hide serial settings based on selection
            serial_container = self.query_one("#serial_settings")
            if event.value == "serial":
                serial_container.remove_class("hidden")
            else:
                serial_container.add_class("hidden")
        elif event.select.id == "baudrate":
            self.baudrate = event.value
    
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "port":
            self.port = event.value
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect":
            self.dismiss({
                "type": self.connection_type,
                "port": self.port,
                "baudrate": self.baudrate
            })
        elif event.button.id == "cancel":
            self.dismiss(None)

class ResourceMonitor(Static):
    def __init__(self):
        super().__init__()
        self.process = psutil.Process()
        self.update_resources()
    
    def update_resources(self):
        try:
            cpu_percent = self.process.cpu_percent(interval=0.1)    
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            self.update(
                f"Resources | "
                f"CPU: {cpu_percent:.2f}% | "
                f"RAM: {memory_mb:.1f} MB"
            )
        except Exception:
            self.update("[dim]Resource monitoring unavailable[/dim]")

class ConnectionStatus(Static):
    def __init__(self):
        super().__init__()
        self.status = "Disconnected"
        self.connection_info = {}
        self.update_status(None)
    
    def update_status(self, status: str, info: dict = None):
        self.status = status
        self.connection_info = info or {}
        
        if status == "Connected":
            conn_type = self.connection_info.get("type", "Unknown")
            if conn_type == "simulated":
                details = "Simulated Data"
            elif conn_type == "serial":
                details = f"Serial: {self.connection_info.get('port', 'N/A')} @ {self.connection_info.get('baudrate', 'N/A')}"
            elif conn_type == "bluetooth":
                details = f"Bluetooth: {self.connection_info.get('port', 'N/A')}"
            else:
                details = "Unknown"
            
            self.update(f"[green]● Connected[/green] - {details}")
        elif status == "Connecting":
            self.update(f"[bold yellow]⟳ Connecting...[/bold yellow]")
        else:
            self.update(f"[bold red]○ Disconnected[/bold red]")

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
        padding: 1;
    }
    StatsDashboard {
        padding: 1;
        margin-top: 1;
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
        margin-top: 1;
        
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
    """
    
    BINDINGS = [
        Binding("c", "open_connection", "Connection", show=True),
        Binding("ctrl+d", "disconnect", "Disconnect", show=True),
        Binding("q", "request_quit", "Quit", show=True),
        Binding("ctrl+q", "request_quit", "Quit", show=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.is_connected = False
        self.connection_config = None
        self.update_timer = None
        self.data_stream = None
    
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
            self.is_connected = False
            self.connection_config = None
            self.conn_status.update_status("Disconnected")
            self.write_log("Disconnected")
            self.update_data()
           
    
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
        
        # Start the update timer
        if self.update_timer:
            self.update_timer.stop()
        self.update_timer = self.set_interval(1, self.update_data)
    
    def update_data(self):    
        #Update dashboard with new data

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
        try:
            data = self.data_stream.stdout.readline().strip()
        except:
            self.write_log(f"No data")
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

if __name__ == "__main__":
    DashboardLogApp().run()