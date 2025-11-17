from textual.widgets import Static

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