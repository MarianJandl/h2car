from textual.app import  ComposeResult
from textual.containers import Container
from textual.widgets import Button, Label, Select, Input
from textual.screen import ModalScreen
from textual.binding import Binding

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
