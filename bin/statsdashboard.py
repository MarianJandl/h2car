from textual.widgets import Static

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
