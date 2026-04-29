# 🌐 Network Queue Simulator

> **Business System Modelling — Assignment**
> Queuing model network simulator that treats data packets as queue entities,
> modelled using Poisson arrivals and verified with NS3 discrete-event simulation.

---

## Table of Contents

1. [What This Project Does](#what-this-project-does)
2. [BSM Context](#bsm-context)
3. [Folder Structure](#folder-structure)
4. [Prerequisites](#prerequisites)
5. [Installation](#installation)
6. [Running the Project](#running-the-project)
7. [Using the Web Interface](#using-the-web-interface)
8. [Using the CLI](#using-the-cli)
9. [NS3 Setup](#ns3-setup)
10. [Scenarios Explained](#scenarios-explained)
11. [Troubleshooting](#troubleshooting)

---

## What This Project Does

This project simulates data packets moving through a network router as a
**queuing system**. It solves the same class of problem as the textbook
inspection station example, but applied to networking:

| Textbook Example          | This Project                        |
|---------------------------|-------------------------------------|
| Jobs arriving at λ=2/hr   | Packets arriving at λ=100 pkt/s     |
| Quality control engineer  | Router / network link               |
| Service time (Erlang)     | Transmission delay = size/bandwidth |
| Waiting room floor space  | Router buffer size (packets)        |
| Lq, Wq, idle time         | Buffer occupancy, queuing delay, utilisation |

**Two modes of analysis run side by side:**

- **Analytical** — closed-form M/M/1 and M/M/K formulas give exact
  steady-state results instantly
- **NS3 Simulation** — discrete-event network simulator independently
  generates stochastic packet behaviour and verifies the formulas

---

## BSM Context

The project implements the following queuing models from the course:

| Model    | Notation       | Used For                          |
|----------|---------------|-----------------------------------|
| Model I  | M/M/1 : ∞/FCFS | Single router link                |
| Model VII| M/M/K : ∞/FCFS | K parallel load-balanced links    |

**Kendall notation for the network scenario:**

```
M  /  M  /  K  :  ∞  /  FCFS
↑     ↑     ↑      ↑     ↑
│     │     │      │     └── First Come First Served (DropTail queue)
│     │     │      └──────── Infinite buffer capacity
│     │     └─────────────── K parallel links (servers)
│     └───────────────────── Exponential service (transmission delay)
└─────────────────────────── Poisson packet arrivals (M = Markovian)
```

---

## Folder Structure

```
~/network-queue-sim/              ← Project root
│
├── app.py                        ← Flask web server (API + serves frontend)
├── main.py                       ← CLI entry point (no browser needed)
├── requirements.txt              ← Python dependencies
├── README.md                     ← This file
│
├── static/
│   └── index.html                ← Web UI (single file, Chart.js graphs)
│
├── analytical/
│   ├── __init__.py
│   └── network_mm1.py            ← M/M/1 and M/M/K analytical formulas
│
├── ns3_simulation/
│   └── network_queue.cc          ← NS3 C++ simulation script
│
├── python_bridge/
│   ├── __init__.py
│   └── run_sim.py                ← Runs NS3 as subprocess, parses output
│
├── analytics/
│   ├── __init__.py
│   └── reporter.py               ← Rich table printer (copied from hospital project)
│
├── results/
│   └── comparison.py             ← Matplotlib charts (optional)
│
└── .vscode/
    └── settings.json             ← VS Code Pylance path configuration
```

**Relationship to NS3:**

```
~/
├── network-queue-sim/    ← your Python project (this repo)
└── ns-3-dev/             ← NS3 cloned separately (NOT inside this project)
```

NS3 lives beside this project in your home directory. At runtime,
`python_bridge/run_sim.py` copies `network_queue.cc` into
`~/ns-3-dev/scratch/` and calls NS3 as an external subprocess.

---

## Prerequisites

- **Ubuntu 22.04** (WSL or native)
- **Python 3.10+** via pyenv (`python3 --version` to check)
- **NS3** cloned and built at `~/ns-3-dev` (see [NS3 Setup](#ns3-setup))
- **VS Code** with Pylance extension (optional, for editing)

---

## Installation

### Step 1 — Clone or create the project folder

```bash
cd ~
# If starting fresh:
mkdir network-queue-sim
cd network-queue-sim
```

### Step 2 — Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Your prompt should now show `(venv)` at the start.

### Step 3 — Install Python dependencies

```bash
pip install flask rich numpy matplotlib
```

Or if you have a `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Step 4 — Create all required folders

```bash
mkdir -p analytical ns3_simulation python_bridge analytics results static .vscode
touch analytical/__init__.py python_bridge/__init__.py analytics/__init__.py
```

### Step 5 — Copy reporter from hospital project

```bash
cp ~/hospital-queue-sim/analytics/reporter.py ~/network-queue-sim/analytics/reporter.py
```

### Step 6 — Configure VS Code Pylance

Create `.vscode/settings.json` with exactly this content:

```json
{
    "python.defaultInterpreterPath": "./venv/bin/python3",
    "python.analysis.extraPaths": [
        "/home/aprel/network-queue-sim"
    ]
}
```

> **Note:** Replace `aprel` with your actual Linux username if different.
> Run `whoami` in terminal to check.

---

## Running the Project

### Option A — Web Interface (recommended)

```bash
cd ~/network-queue-sim
source venv/bin/activate
python app.py
```

Then open your browser at:

```
http://localhost:5000
```

To stop the server: press `Ctrl + C` in the terminal.

---

### Option B — Command Line Interface

```bash
cd ~/network-queue-sim
source venv/bin/activate
python main.py
```

Menu options:

```
1. Home Router          — light traffic, single link
2. Office Switch        — moderate traffic, 2 parallel links
3. ISP Backbone         — heavy traffic, 3 links
4. Congested Link       — near-capacity, demonstrates ρ→1 explosion
5. Custom parameters    — enter your own λ, bandwidth, K
6. Run ALL              — analytical results for all 4 scenarios
7. Run with NS3         — requires NS3 installed (see below)
```

---

## Using the Web Interface

### Preset Scenarios (left sidebar)

Click any of the 4 coloured scenario cards to instantly load results.
The ρ badge on each card is colour-coded:

- 🟢 **Green** — ρ < 70% — system comfortably stable
- 🟡 **Yellow** — ρ 70–85% — moderate load, watch queue growth
- 🔴 **Red** — ρ > 85% — critical, queue explodes non-linearly

### Custom Parameters

Fill in the three fields and press **Enter** or click **▶ Analyse**:

| Field | Description | Example |
|-------|-------------|---------|
| λ — Arrival Rate | Packets arriving per second | `100` |
| Bandwidth | Link speed in Mbps | `1.2` |
| K — Parallel Links | Number of server links | `1` |

### Running NS3 Simulation

1. Make sure NS3 is installed (see [NS3 Setup](#ns3-setup))
2. Select a scenario or enter custom parameters
3. Choose simulation duration from the dropdown
4. Click **⚡ Run NS3 Simulation**
5. Wait 10–60 seconds depending on duration
6. A verification table appears comparing analytical vs NS3 results

### Reading the Charts

**Queue Length vs Utilisation (Lq chart):**
Shows how the average number of buffered packets grows as the link
becomes more loaded. The white dot marks your current operating point.
Notice the curve becomes nearly vertical near ρ = 1 — this is the
core non-linear insight of queuing theory.

**Queuing Delay vs Utilisation (Wq chart):**
Same shape but in milliseconds. This is the delay a packet experiences
waiting in the buffer before transmission begins.

**Scenario Comparison bar chart:**
All 4 preset scenarios plotted side by side by queuing delay —
lets you see at a glance which network environment has the worst congestion.

---

## NS3 Setup

NS3 must be installed **separately** in your home directory.

### Step 1 — Install build dependencies

```bash
sudo apt update
sudo apt install -y g++ python3 python3-dev cmake ninja-build git
```

### Step 2 — Clone NS3

```bash
cd ~
git clone https://gitlab.com/nsnam/ns-3-dev.git
# Takes 2–3 minutes
```

### Step 3 — Build NS3

```bash
cd ~/ns-3-dev
./ns3 configure --enable-examples
./ns3 build
# Takes 5–15 minutes on first build
```

### Step 4 — Test NS3 works

```bash
./ns3 run hello-simulator
# Should print: Hello Simulator
```

### Step 5 — Copy the simulation script

```bash
cp ~/network-queue-sim/ns3_simulation/network_queue.cc ~/ns-3-dev/scratch/
```

### Step 6 — Test the network script manually

```bash
cd ~/ns-3-dev
./ns3 run "scratch/network_queue --arrivalRate=100 --linkBandwidth=1.2Mbps"
```

Expected output includes lines like:

```
NS3_RESULT:avg_delay_ms=7.94907
NS3_RESULT:rx_packets=989
NS3_RESULT:tx_packets=989
NS3_RESULT:loss_rate_pct=0
NS3_RESULT:throughput_kbps=791.2
```

If you see these, NS3 is working correctly and the web app's
"Run NS3 Simulation" button will work.

---

## Scenarios Explained

### 1. Home Router (M/M/1)
- λ = 80 pkt/s, BW = 1.2 Mbps, K = 1
- μ = 150 pkt/s → ρ = 0.533 (53.3% utilised)
- Represents a home broadband router under normal browsing load
- Queue is stable and short — typical everyday operation

### 2. Office Switch (M/M/2)
- λ = 200 pkt/s, BW = 3.0 Mbps, K = 2
- μ = 375 pkt/s → ρ = 0.267 per link
- Two parallel uplinks share the load — very low utilisation
- Demonstrates M/M/K: adding a second link dramatically reduces per-server load

### 3. ISP Backbone (M/M/3)
- λ = 500 pkt/s, BW = 8.0 Mbps, K = 3
- μ = 1000 pkt/s → ρ = 0.167 per link
- Three load-balanced links on a high-speed backbone
- Despite heavy absolute traffic, low ρ keeps queues short

### 4. Congested Link (M/M/1)
- λ = 148 pkt/s, BW = 1.2 Mbps, K = 1
- μ = 150 pkt/s → ρ = 0.987 (98.7% utilised)
- Deliberately near-capacity to demonstrate queue explosion
- Lq ≈ 78 packets — compare to ρ=0.5 where Lq ≈ 0.5

---

## Troubleshooting

### `Import "analytics.reporter" could not be resolved` (Pylance)

```bash
# Make sure reporter.py exists:
ls ~/network-queue-sim/analytics/
# If missing:
cp ~/hospital-queue-sim/analytics/reporter.py ~/network-queue-sim/analytics/
```

Then check `.vscode/settings.json` contains `python.analysis.extraPaths`
pointing to `/home/aprel/network-queue-sim`.

---

### `ModuleNotFoundError: No module named 'flask'`

```bash
cd ~/network-queue-sim
source venv/bin/activate   # make sure venv is active
pip install flask
```

---

### NS3 button gives "NS3 not found" error

```bash
# Check NS3 exists:
ls ~/ns-3-dev/ns3
# If missing, clone it:
cd ~ && git clone https://gitlab.com/nsnam/ns-3-dev.git
cd ~/ns-3-dev && ./ns3 configure --enable-examples && ./ns3 build
```

---

### NS3 button gives "network_queue.cc not found"

```bash
ls ~/network-queue-sim/ns3_simulation/
# Should show: network_queue.cc
# If missing, create the ns3_simulation folder and add the file.
```

---

### Port 5000 already in use

```bash
# Find and kill the process using port 5000:
sudo lsof -i :5000
sudo kill -9 <PID>
# Then restart:
python app.py
```

---

### `pyenv: python: command not found`

```bash
pyenv global 3.11.9   # or whichever version you installed
python --version       # verify
```

---

## Quick Reference

```bash
# Every time you open a new terminal:
cd ~/network-queue-sim
source venv/bin/activate

# Start web app:
python app.py
# → open http://localhost:5000

# Start CLI:
python main.py

# Run NS3 manually:
cd ~/ns-3-dev
./ns3 run "scratch/network_queue --arrivalRate=100 --linkBandwidth=1.2Mbps --numServers=1"
```
