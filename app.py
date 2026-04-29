# app.py  —  Flask backend for Network Queue Simulator Web UI
# Place this in ~/network-queue-sim/app.py
#
# Install:  pip install flask
# Run:      python app.py
# Open:     http://localhost:5000

from flask import Flask, request, jsonify, send_from_directory
import math
import subprocess
import re
import os

app = Flask(__name__, static_folder="static")

# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICAL MODELS  (same formulas as analytical/network_mm1.py)
# ─────────────────────────────────────────────────────────────────────────────

def compute_mm1(lam, mu):
    rho = lam / mu
    if rho >= 1:
        return {"error": f"System unstable: ρ = {rho:.4f} ≥ 1. Packets will be lost indefinitely."}
    lq  = rho**2 / (1 - rho)
    l   = rho / (1 - rho)
    wq  = lq / lam * 1000          # ms
    w   = l  / lam * 1000          # ms
    p0  = 1 - rho
    buf = max(math.ceil(math.log(0.01) / math.log(rho)) - 1, 1) if rho > 0 else 1
    return {
        "model":     "M/M/1",
        "rho":       round(rho,  6),
        "Lq":        round(lq,   6),
        "L":         round(l,    6),
        "Wq_ms":     round(wq,   4),
        "W_ms":      round(w,    4),
        "P0_pct":    round(p0 * 100, 2),
        "buffer":    buf,
        "stable":    True,
    }


def compute_mmk(lam, mu, k):
    rho = lam / (k * mu)
    if rho >= 1:
        return {"error": f"System unstable: ρ = {rho:.4f} ≥ 1 per server."}
    r = lam / mu
    sum_terms = sum((r**n) / math.factorial(n) for n in range(k))
    last_term  = (r**k) / (math.factorial(k) * (1 - rho))
    P0 = 1 / (sum_terms + last_term)
    lq = (P0 * (r**k) * rho) / (math.factorial(k) * (1 - rho)**2)
    l  = lq + r
    wq = lq / lam * 1000
    w  = wq + (1 / mu) * 1000
    return {
        "model":     f"M/M/{k}",
        "rho":       round(rho,  6),
        "Lq":        round(lq,   6),
        "L":         round(l,    6),
        "Wq_ms":     round(wq,   4),
        "W_ms":      round(w,    4),
        "P0_pct":    round(P0 * 100, 2),
        "buffer":    "-",
        "stable":    True,
    }


def run_analytical(lam, bw_mbps, k):
    mu = (bw_mbps * 1_000_000) / 8000   # packets/sec  (1000-byte packets)
    if k == 1:
        res = compute_mm1(lam, mu)
    else:
        res = compute_mmk(lam, mu, k)
    res["mu"] = round(mu, 2)
    res["lam"] = lam
    res["bw_mbps"] = bw_mbps
    res["k"] = k
    return res


# ─────────────────────────────────────────────────────────────────────────────
# RHO SWEEP  —  powers the main sensitivity chart
# ─────────────────────────────────────────────────────────────────────────────

def rho_sweep(mu, k, steps=40):
    """Return Lq and Wq for a range of lambda values (ρ from 0.05 to 0.97)."""
    results = []
    for i in range(1, steps + 1):
        rho_target = 0.05 + (0.92 / steps) * i
        lam = rho_target * k * mu
        if k == 1:
            r = compute_mm1(lam, mu)
        else:
            r = compute_mmk(lam, mu, k)
        if "error" not in r:
            results.append({
                "rho":    round(rho_target, 4),
                "lam":    round(lam, 2),
                "Lq":     r["Lq"],
                "Wq_ms":  r["Wq_ms"],
            })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# NS3 SIMULATION RUNNER
# ─────────────────────────────────────────────────────────────────────────────

NS3_PATH = os.path.expanduser("~/ns-3-dev")

def run_ns3(lam, bw_mbps, k=1, sim_time=10, buffer=200):
    """Run NS3 subprocess, return parsed result dict."""
    # Copy the .cc script into NS3 scratch
    src = os.path.join(os.path.dirname(__file__),
                       "ns3_simulation", "network_queue.cc")
    dst = os.path.join(NS3_PATH, "scratch", "network_queue.cc")

    if not os.path.exists(src):
        return {"error": "network_queue.cc not found in ns3_simulation/"}

    with open(src) as f:
        content = f.read()
    with open(dst, "w") as f:
        f.write(content)

    cmd = [
        "./ns3", "run", "scratch/network_queue",
        "--",
        f"--arrivalRate={lam}",
        f"--linkBandwidth={bw_mbps}Mbps",
        f"--numServers={k}",
        f"--simTime={sim_time}",
        f"--bufferSize={buffer}",
    ]

    try:
        result = subprocess.run(
            cmd, cwd=NS3_PATH,
            capture_output=True, text=True, timeout=120
        )
        output = result.stdout + result.stderr
        parsed = {}
        for line in output.splitlines():
            m = re.match(r"NS3_RESULT:(\w+)=([\d.]+)", line)
            if m:
                parsed[m.group(1)] = float(m.group(2))
        if not parsed:
            return {"error": "NS3 produced no output. Check NS3 installation.",
                    "raw": output[-500:]}
        return {
            "avg_delay_ms":    round(parsed.get("avg_delay_ms", 0), 4),
            "rx_packets":      int(parsed.get("rx_packets", 0)),
            "tx_packets":      int(parsed.get("tx_packets", 0)),
            "loss_rate_pct":   round(parsed.get("loss_rate_pct", 0), 4),
            "throughput_kbps": round(parsed.get("throughput_kbps", 0), 2),
        }
    except subprocess.TimeoutExpired:
        return {"error": "NS3 simulation timed out after 120 seconds."}
    except FileNotFoundError:
        return {"error": f"NS3 not found at {NS3_PATH}. Run: git clone https://gitlab.com/nsnam/ns-3-dev.git ~/ns-3-dev"}


# ─────────────────────────────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────────────────────────────

PRESET_SCENARIOS = {
    "home_router": {
        "label":   "Home Router",
        "desc":    "Light browsing traffic — single link",
        "lam":     80,   "bw_mbps": 1.2,  "k": 1
    },
    "office_switch": {
        "label":   "Office Switch",
        "desc":    "Moderate business traffic — 2 parallel links",
        "lam":     200,  "bw_mbps": 3.0,  "k": 2
    },
    "isp_backbone": {
        "label":   "ISP Backbone",
        "desc":    "Heavy traffic — 3 load-balanced links",
        "lam":     500,  "bw_mbps": 8.0,  "k": 3
    },
    "congested_link": {
        "label":   "Congested Link",
        "desc":    "Near capacity — demonstrates ρ → 1 explosion",
        "lam":     148,  "bw_mbps": 1.2,  "k": 1
    },
}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/scenarios")
def get_scenarios():
    """Return all preset scenarios with pre-computed analytics."""
    out = {}
    for key, sc in PRESET_SCENARIOS.items():
        res = run_analytical(sc["lam"], sc["bw_mbps"], sc["k"])
        out[key] = {**sc, "analytical": res}
    return jsonify(out)


@app.route("/api/analyse", methods=["POST"])
def analyse():
    """Run analytical model for given parameters."""
    data = request.json
    lam     = float(data.get("lam",     100))
    bw_mbps = float(data.get("bw_mbps", 1.2))
    k       = int(data.get("k",         1))

    analytical = run_analytical(lam, bw_mbps, k)

    # Also return rho sweep for the chart
    mu    = (bw_mbps * 1_000_000) / 8000
    sweep = rho_sweep(mu, k)

    return jsonify({
        "analytical": analytical,
        "sweep":      sweep,
        "params":     {"lam": lam, "bw_mbps": bw_mbps, "k": k}
    })


@app.route("/api/simulate", methods=["POST"])
def simulate():
    """Run NS3 simulation and return comparison with analytical."""
    data    = request.json
    lam     = float(data.get("lam",      100))
    bw_mbps = float(data.get("bw_mbps",  1.2))
    k       = int(data.get("k",          1))
    sim_time= int(data.get("sim_time",   10))

    analytical = run_analytical(lam, bw_mbps, k)
    ns3_result = run_ns3(lam, bw_mbps, k, sim_time)

    # Compute accuracy if both succeeded
    comparison = {}
    if "error" not in ns3_result and "error" not in analytical:
        ana_wq = analytical["Wq_ms"]
        sim_wq = ns3_result["avg_delay_ms"]
        diff   = abs(ana_wq - sim_wq) / max(ana_wq, 0.001) * 100
        comparison = {
            "wq_diff_pct":   round(diff, 2),
            "verdict":       "Excellent" if diff < 5
                             else "Good" if diff < 15
                             else "Fair",
        }

    return jsonify({
        "analytical": analytical,
        "ns3":        ns3_result,
        "comparison": comparison,
        "params":     {"lam": lam, "bw_mbps": bw_mbps, "k": k}
    })


@app.route("/api/sweep", methods=["POST"])
def sweep():
    """Return rho sweep data for sensitivity chart."""
    data    = request.json
    bw_mbps = float(data.get("bw_mbps", 1.2))
    k       = int(data.get("k",         1))
    mu      = (bw_mbps * 1_000_000) / 8000
    return jsonify({"sweep": rho_sweep(mu, k), "mu": round(mu, 2)})


if __name__ == "__main__":
    print("\n🌐 Network Queue Simulator — Web UI")
    print("   Open: http://localhost:5000\n")
    app.run(debug=True, port=5000)
