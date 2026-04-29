# python_bridge/run_sim.py
import subprocess
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from analytical.network_mm1 import NetworkMM1, NetworkMMK
from rich.console import Console
from rich.table   import Table
from rich import box

console = Console()

NS3_PATH    = os.path.expanduser("~/ns-3-dev")
SCRIPT_NAME = "network_queue"


def run_ns3(lam, bandwidth_mbps, num_servers=1, sim_time=10, buffer=100):
    """
    Compile and run the NS3 simulation, return parsed results dict.
    """
    # Step 1 — Copy our script into NS3's scratch folder
    src = os.path.join(os.path.dirname(__file__),
                       '..', 'ns3_simulation', 'network_queue.cc')
    dst = os.path.join(NS3_PATH, 'scratch', 'network_queue.cc')
    with open(src) as f:
        content = f.read()
    with open(dst, 'w') as f:
        f.write(content)

    # Step 2 — Build and run
    # mu = bandwidth (bits/s) / (packet_size_bytes * 8)
    # packet size fixed at 1000 bytes → 8000 bits
    cmd = [
        "./ns3", "run",
        f"scratch/network_queue",
        "--",
        f"--arrivalRate={lam}",
        f"--linkBandwidth={bandwidth_mbps}Mbps",
        f"--numServers={num_servers}",
        f"--simTime={sim_time}",
        f"--bufferSize={buffer}",
    ]

    console.print(f"[dim]Running NS3: λ={lam} pkt/s, "
                  f"BW={bandwidth_mbps}Mbps, K={num_servers}...[/dim]")

    result = subprocess.run(
        cmd, cwd=NS3_PATH,
        capture_output=True, text=True
    )

    # Step 3 — Parse NS3_RESULT lines from stdout
    output = result.stdout + result.stderr
    parsed = {}
    for line in output.splitlines():
        m = re.match(r'NS3_RESULT:(\w+)=([\d.]+)', line)
        if m:
            parsed[m.group(1)] = float(m.group(2))

    if not parsed:
        console.print(f"[red]NS3 produced no results. Output:[/red]\n{output}")
    return parsed


def compare(lam, bandwidth_mbps, num_servers=1):
    """
    Run both analytical model and NS3 simulation,
    display side-by-side comparison table.
    This is the network equivalent of your hospital
    analytical vs SimPy comparison.
    """
    # Compute mu from bandwidth
    # mu = link_rate_bits_per_sec / bits_per_packet
    # = (bandwidth_mbps * 1e6) / (1000 * 8)
    packet_bits = 1000 * 8
    mu = (bandwidth_mbps * 1_000_000) / packet_bits

    console.rule(
        f"[bold cyan]Network Queue Analysis  |  "
        f"λ={lam} pkt/s  μ={mu:.0f} pkt/s  K={num_servers}[/bold cyan]"
    )

    # ── Analytical ────────────────────────────────────────────────
    try:
        if num_servers == 1:
            model = NetworkMM1(lam, mu)
        else:
            model = NetworkMMK(lam, mu, num_servers)
        analytical = model.summary()
        console.print("\n[bold cyan]Analytical Model (M/M/1 Formulas):[/bold cyan]")
        from analytics.reporter import print_results
        print_results("Analytical", analytical)
        ana_wq_ms = model.Wq() * 1000
        ana_lq    = model.Lq()
    except ValueError as e:
        console.print(f"[bold red]⚠ {e}[/bold red]")
        ana_wq_ms = float('inf')
        ana_lq    = float('inf')

    # ── NS3 Simulation ────────────────────────────────────────────
    ns3_res = run_ns3(lam, bandwidth_mbps, num_servers)

    if not ns3_res:
        console.print("[red]NS3 simulation failed — check NS3 installation.[/red]")
        return

    # ── Side-by-side comparison table ────────────────────────────
    t = Table(
        title="[bold]Analytical Formula  vs  NS3 Network Simulation[/bold]",
        box=box.ROUNDED, show_lines=True,
        header_style="bold white"
    )
    t.add_column("Metric",          style="bold white",  width=28)
    t.add_column("Analytical",      justify="right",     width=18, style="cyan")
    t.add_column("NS3 Simulation",  justify="right",     width=18, style="green")
    t.add_column("Difference",      justify="right",     width=14)

    def diff_text(a, b):
        if a == float('inf') or b == 0:
            return "N/A"
        pct = abs(a - b) / max(abs(a), 1e-9) * 100
        color = "green" if pct < 10 else "yellow" if pct < 25 else "red"
        return f"[{color}]{pct:.1f}%[/{color}]"

    sim_wq_ms = ns3_res.get("avg_delay_ms", 0)
    t.add_row(
        "Avg Queuing Delay (Wq)",
        f"{ana_wq_ms:.3f} ms",
        f"{sim_wq_ms:.3f} ms",
        diff_text(ana_wq_ms, sim_wq_ms),
    )
    t.add_row(
        "Packet Loss Rate",
        "0%  (infinite buffer)",
        f"{ns3_res.get('loss_rate_pct', 0):.2f}%",
        "—",
    )
    t.add_row(
        "Throughput",
        f"{lam * 1000 * 8 / 1000:.0f} kbps",
        f"{ns3_res.get('throughput_kbps', 0):.0f} kbps",
        diff_text(lam * 8, ns3_res.get('throughput_kbps', 0) / 1000),
    )
    t.add_row(
        "Packets Transmitted",
        f"≈{int(lam * 10)}",
        str(int(ns3_res.get('tx_packets', 0))),
        "—",
    )
    t.add_row(
        "Packets Received",
        f"≈{int(lam * 10)}",
        str(int(ns3_res.get('rx_packets', 0))),
        "—",
    )
    console.print(t)