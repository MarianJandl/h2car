from textual.screen import ModalScreen
from textual.widgets import Input, Button, Label, Static, RichLog
from textual.containers import Vertical, Grid, Horizontal
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding


class InputScreen(ModalScreen):
    """Command-line style input modal with history"""
    
    CSS = """
    InputScreen {
        align: center middle;
    }
    
    #input_dialog {
        width: 80;
        height: 25;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }
    
    #command_title {
        height: 1;
        width: 100%;
        content-align: left middle;
        margin-bottom: 1;
    }
    
    #command_history {
        height: 1fr;
        width: 100%;
        border: solid $primary;
        margin-bottom: 1;
        padding: 1;
    }
    
    #input_line {
        height: auto;
        width: 100%;
        margin-bottom: 1;
    }
    
    #prompt {
        width: auto;
        height: 3;
        content-align: left middle;
        padding-right: 1;
    }
    
    #user_input {
        width: 1fr;
        height: 3;
    }
    
    #help_text {
        height: auto;
        width: 100%;
        content-align: left middle;
    }
    """
    
    BINDINGS = [
        Binding("escape", "dismiss", "Cancel", show=True),
        Binding("up", "history_prev", "Previous", show=False),
        Binding("down", "history_next", "Next", show=False),
    ]
    
    # Class variable to store command history across instances
    command_history = []
    
    def __init__(self, title="Command Input"):
        super().__init__()
        self.dialog_title = title
        self.input_value = ""
        self.history_index = len(InputScreen.command_history)
        self.current_input = ""
    
    def compose(self) -> ComposeResult:
        with Vertical(id="input_dialog"):
            yield Static(f"[bold cyan]{self.dialog_title}[/bold cyan]", id="command_title")
            yield RichLog(highlight=True, markup=True, id="command_history")
            with Horizontal(id="input_line"):
                yield Static("[bold green]>[/bold green]", id="prompt")
                yield Input(placeholder="Type command and press Enter...", id="user_input")
            yield Static(
                "[dim]↑/↓: History | Enter: Submit | Esc: Cancel [/dim]",
                id="help_text"
            )
    
    def on_mount(self):
        # Focus the input field when the modal opens
        self.query_one("#user_input", Input).focus()
        
        # Show recent command history
        history_log = self.query_one("#command_history", RichLog)
        history_log.write("[dim]Command History:[/dim]")
        if InputScreen.command_history:
            for i, cmd in enumerate(InputScreen.command_history[-10:], 1):  # Show last 10
                history_log.write(f"[dim]{i}.[/dim] {cmd}")
        else:
            history_log.write("[dim]No previous commands[/dim]")
    
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "user_input":
            self.input_value = event.value
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Allow Enter key to submit
        if event.input.id == "user_input":
            if self.input_value.strip():
                # Add to history
                InputScreen.command_history.append(self.input_value)
                # Keep history to reasonable size
                if len(InputScreen.command_history) > 100:
                    InputScreen.command_history.pop(0)
                
                self.dismiss(self.input_value)
            else:
                self.dismiss(None)
    
    def action_history_prev(self):
        """Navigate to previous command in history"""
        if not InputScreen.command_history:
            return
        
        # Save current input if at the end of history
        if self.history_index == len(InputScreen.command_history):
            self.current_input = self.input_value
        
        # Move back in history
        if self.history_index > 0:
            self.history_index -= 1
            input_widget = self.query_one("#user_input", Input)
            input_widget.value = InputScreen.command_history[self.history_index]
            input_widget.cursor_position = len(input_widget.value)
    
    def action_history_next(self):
        """Navigate to next command in history"""
        if not InputScreen.command_history:
            return
        
        # Move forward in history
        if self.history_index < len(InputScreen.command_history):
            self.history_index += 1
            input_widget = self.query_one("#user_input", Input)
            
            if self.history_index == len(InputScreen.command_history):
                # Restore current input
                input_widget.value = self.current_input
            else:
                input_widget.value = InputScreen.command_history[self.history_index]
            
            input_widget.cursor_position = len(input_widget.value)