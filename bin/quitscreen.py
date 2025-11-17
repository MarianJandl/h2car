from textual.app import ComposeResult
from textual.containers import Grid
from textual.widgets import Button, Label
from textual.screen import ModalScreen
from textual.binding import Binding

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
