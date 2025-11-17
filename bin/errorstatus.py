from textual.widgets import Static

class ErrorStatus(Static):
    def __init__(self):
        super().__init__()
        
        self.update_status(None, 0)
    
    def update_status(self, data, nodata):
        if data is None:
            self.update(f"[dim]No data ({nodata})[/dim]")
        else:
            err_code = data['Di']
            if err_code == "0x0" or err_code == "0":
               self.update("[green]Error code: 0 - OK[/green]")
               
            elif err_code == "0x1" or err_code == "1":
                self.update("[yellow]Error code: 1 - Vymen bombicku[/yellow]")
            elif err_code == "0x3" or err_code == "3":
                self.update("[red]Error code: 3 - Neco spatne se clankem[/red]")
            elif err_code == "0x8" or err_code == "8":
                self.update("[red]Error code: 8 - Vymen baterku[/red]")
            elif err_code == "0x9" or err_code == "9":
                self.update("[red]Error code: 9 - Vymen baterku a bombicku asi[/red]")
            elif err_code == "0xb" or err_code == "b" or err_code == "B":
                self.update("[red]Error code: B - Vsechno spatne[/red]")
            else:
                self.update(f"[bold red]Error code {err_code}: Unknown error - I suppose everything is completly fucked - Good luck[/bold red]")
                            