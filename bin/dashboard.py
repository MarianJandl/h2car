from textual.widgets import Static

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