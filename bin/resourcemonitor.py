from textual.widgets import Static
import psutil

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
