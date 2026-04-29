# main.py  — Network Queue Simulator entry point
from rich.console import Console
from rich.prompt  import Prompt, FloatPrompt, IntPrompt
from rich.panel   import Panel
from analytical.network_mm1 import NetworkMM1, NetworkMMK

console = Console()

SCENARIOS = {
    "home_router": {
        "desc":      "Home router — light browsing traffic",
        "lam":       80,
        "bw_mbps":   1.2,
        "servers":   1,
    },
    "office_switch": {
        "desc":      "Office switch — moderate business traffic",
        "lam":       200,
        "bw_mbps":   3.0,
        "servers":   2,
    },
    "isp_backbone": {
        "desc":      "ISP backbone router — heavy traffic",
        "lam":       500,
        "bw_mbps":   8.0,
        "servers":   3,
    },
    "congested_link": {
        "desc":      "Congested link — near capacity (demonstrates ρ→1)",
        "lam":       148,
        "bw_mbps":   1.2,
        "servers":   1,
    },
}


def run_analytical_only(scenario):
    """Run without NS3 — analytical results only."""
    packet_bits = 8000
    mu = (scenario["bw_mbps"] * 1_000_000) / packet_bits
    k  = scenario["servers"]

    console.rule(f"[bold yellow]{scenario['desc']}[/bold yellow]")
    try:
        model = NetworkMM1(scenario["lam"], mu) if k == 1 \
                else NetworkMMK(scenario["lam"], mu, k)
        s = model.summary()
        from analytics.reporter import print_results
        print_results("Network Queue (Analytical)", s)
    except ValueError as e:
        console.print(f"[bold red]⚠ {e}[/bold red]")


def main():
    console.print(Panel(
        "[bold cyan]🌐 Network Queue Simulator[/bold cyan]\n"
        "[dim]Data packets as queuing model — M/M/1 and M/M/K[/dim]\n"
        "[dim]Analytical formulas + NS3 discrete-event simulation[/dim]",
        padding=(1, 4)
    ))

    console.print("[bold]Scenarios:[/bold]")
    keys = list(SCENARIOS.keys())
    for i, (k, v) in enumerate(SCENARIOS.items(), 1):
        mu = (v["bw_mbps"] * 1_000_000) / 8000
        rho = v["lam"] / (v["servers"] * mu)
        console.print(f"  {i}. {v['desc']}")
        console.print(f"     λ={v['lam']} pkt/s  "
                      f"BW={v['bw_mbps']}Mbps  "
                      f"K={v['servers']}  ρ={rho:.3f}")

    console.print("  5. Custom parameters")
    console.print("  6. Run ALL (analytical only)")
    console.print("  7. Run with NS3 simulation (requires NS3 installed)\n")

    choice = Prompt.ask("Select", choices=["1","2","3","4","5","6","7"])

    if choice in ["1","2","3","4"]:
        run_analytical_only(SCENARIOS[keys[int(choice)-1]])
    elif choice == "6":
        for sc in SCENARIOS.values():
            run_analytical_only(sc)
    elif choice == "7":
        i = int(Prompt.ask("Which scenario to run with NS3? [1-4]")) - 1
        sc = SCENARIOS[keys[i]]
        from python_bridge.run_sim import compare
        compare(sc["lam"], sc["bw_mbps"], sc["servers"])
    else:
        lam = FloatPrompt.ask("Arrival rate λ (packets/sec)")
        bw  = FloatPrompt.ask("Link bandwidth (Mbps)")
        k   = IntPrompt.ask("Number of parallel links (servers K)")
        run_analytical_only({"desc": "Custom", "lam": lam,
                              "bw_mbps": bw, "servers": k})


if __name__ == "__main__":
    main()