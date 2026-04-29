from rich.console import Console
from rich.table import Table

console = Console()

def print_results(title, data: dict):
    table = Table(title=title, style="bold cyan", header_style="bold magenta")
    table.add_column("Metric", style="green")
    table.add_column("Value",  style="yellow")
    for k, v in data.items():
        table.add_row(str(k), str(v))
    console.print(table)