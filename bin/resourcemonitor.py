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
            battery = psutil.sensors_battery()
            memory_mb = memory_info.rss / 1024 / 1024
            if battery == None:
                self.update(
                    f"Resources | "
                    f"CPU: {cpu_percent:.2f}% | "
                    f"RAM: {memory_mb:.1f} MB\n"
                    f"Battery: N/A"
                )
            else:
                if battery.secsleft == psutil.POWER_TIME_UNLIMITED:
                    self.update(
                        f"Resources | "
                        f"CPU: {cpu_percent:.2f}% | "
                        f"RAM: {memory_mb:.1f} MB\n"
                        f"Battery: plugged in" 
                )
            
                elif battery.secsleft == psutil.POWER_TIME_UNKNOWN:
                    self.update(
                        f"Resources | "
                        f"CPU: {cpu_percent:.2f}% | "
                        f"RAM: {memory_mb:.1f} MB\n"
                        f"Battery: {battery.percent}%"
                )
                else:
                    hours = battery.secsleft // 3600
                    minutes = (battery.secsleft % 3600) // 60
                    self.update(
                        f"Resources | "
                        f"CPU: {cpu_percent:.2f}% | "
                        f"RAM: {memory_mb:.1f} MB\n"
                        f"Battery: {battery.percent}% - {hours}h {minutes}m"
                    )
                    
        except Exception:
            self.update("[dim]Resource monitoring unavailable[/dim]")
