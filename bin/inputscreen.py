# input_modal.py
from textual.screen import ModalScreen
from textual.widgets import Input, Button, Label
from textual.containers import Vertical, Grid
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding

class InputScreen(ModalScreen):
    """Universal input modal for logging custom messages"""
    
    CSS = """
        InputScreen {
            align: center middle;
        }
        
        #input_dialog {
            grid-size: 2;
            grid-gutter: 1 2;
            grid-rows: auto auto 3;
            padding: 1 2;
            width: 60;
            height: 15;
            border: thick $background 80%;
            background: $surface;
        }
        
        #input_title {
            column-span: 2;
            height: auto;
            content-align: center middle;
        }
        
        #user_input {
            column-span: 2;
            width: 100%;
            height: 3;
        }
        
        Button {
            width: 100%;
        }
        """

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel", show=True),
    ]
    
    def __init__(self, title="Enter Input", placeholder="Type your message here..."):
        super().__init__()
        self.dialog_title = title
        self.input_placeholder = placeholder
        self.input_value = ""
    
    def compose(self) -> ComposeResult:
        yield Grid(
            Label(f"{self.dialog_title}", id="input_title"),
            Input(placeholder=self.input_placeholder, id="user_input"),
            Button("Submit", variant="primary", id="submit"),
            Button("Cancel", variant="default", id="cancel"),
            id="input_dialog",
        )
    
    def on_mount(self):
        # Focus the input field when the modal opens
        self.query_one("#user_input", Input).focus()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "user_input":
            self.input_value = event.value
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Allow Enter key to submit
        if event.input.id == "user_input":
            self.dismiss(self.input_value)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.dismiss(self.input_value)
        elif event.button.id == "cancel":
            self.dismiss(None)