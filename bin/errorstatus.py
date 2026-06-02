from textual.app import ComposeResult
from textual.widgets import Static
import json
from pathlib import Path

def load_error_config():
    """Load error configuration from file"""
    config_path = Path("config/error_config.json")
    default_config = {
        "error_codes": [
            {
                "code": ["0x0", "0"],
                "priority": "info",
                "message": "OK - System operational",
                "action": None
            }
        ],
        "conditions": []
    }

    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        except Exception:
            pass

    # Create default config file if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=2)

    return default_config

class ErrorStatus(Static):
    """Shows the current error code (from the Di field) mapped to a message.

    Just the error code line — no condition-based alert list, so the widget
    stays a fixed couple of rows and needs no scrollbar.
    """

    def __init__(self):
        super().__init__()
        self.config = load_error_config()

    def compose(self) -> ComposeResult:
        yield Static(id="error_list")

    def reload_config(self):
        """Reload error codes from config"""
        self.config = load_error_config()

    def find_error_info(self, err_code):
        """Find error information from config"""
        for error in self.config.get("error_codes", []):
            if err_code in error["code"]:
                return error
        return None

    def get_priority_style(self, priority):
        """Get color based on priority"""
        styles = {
            "info": "green",
            "warning": "yellow",
            "error": "red",
            "critical": "bold red",
        }
        return styles.get(priority, "white")

    def update_status(self, data, nodata):
        error_list = self.query_one("#error_list", Static)

        if data is None:
            error_list.update(f"[dim]No data received ({nodata} cycles)[/dim]")
            return

        err_code = data.get('Di', 'unknown')
        error_info = self.find_error_info(err_code)

        if error_info:
            color = self.get_priority_style(error_info["priority"])
            error_list.update(f"[bold]Error Code:[/bold] [{color}]{error_info['message']}[/{color}]")
        elif err_code not in ["0x0", "0"]:
            error_list.update(f"[bold]Error Code:[/bold] [bold red]Unknown error code: {err_code}[/bold red]")
        else:
            error_list.update("[bold]Error Code:[/bold] [green]OK - System operational[/green]")
