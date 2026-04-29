# analytical/network_mm1.py
# M/M/1 Queue — Network packet queuing formulas
# Directly mirrors the textbook example structure

class NetworkMM1:
    """
    Single router/link modelled as M/M/1 queue.

    Parameters
    ----------
    lam  : float  packet arrival rate (packets/sec)
    mu   : float  packet service rate = link_bandwidth / avg_packet_size
    """
    def __init__(self, lam, mu):
        self.lam = lam
        self.mu  = mu
        self.rho = lam / mu          # link utilisation (0 to 1)

    def validate(self):
        if self.rho >= 1:
            raise ValueError(
                f"Network congested: ρ={self.rho:.3f} ≥ 1. "
                f"Packet loss will occur — buffer overflows."
            )

    # ── Core metrics ──────────────────────────────────────────────
    def Lq(self):
        """Avg packets waiting in router buffer."""
        return self.rho**2 / (1 - self.rho)

    def L(self):
        """Avg packets in system (buffer + being transmitted)."""
        return self.rho / (1 - self.rho)

    def Wq(self):
        """Avg queuing delay (seconds) — time waiting in buffer."""
        return self.Lq() / self.lam

    def W(self):
        """Avg total delay (queuing + transmission) in seconds."""
        return self.L() / self.lam

    def P0(self):
        """Probability router is idle (no packets being processed)."""
        return 1 - self.rho

    def Pn(self, n):
        """Probability of exactly n packets in system."""
        return (1 - self.rho) * (self.rho ** n)

    def buffer_size(self, overflow_prob=0.01):
        """
        Minimum buffer (packets) so overflow probability < overflow_prob.
        P(more than N in system) = rho^(N+1) < overflow_prob
        → N > log(overflow_prob) / log(rho) - 1
        """
        import math
        n = math.ceil(math.log(overflow_prob) / math.log(self.rho)) - 1
        return max(n, 1)

    def summary(self):
        self.validate()
        return {
            "Model":                        "M/M/1 (Network)",
            "λ  — Packet arrival rate":     f"{self.lam} pkt/s",
            "μ  — Service rate":            f"{self.mu} pkt/s",
            "ρ  — Link utilisation":        f"{self.rho:.4f}  ({self.rho*100:.1f}%)",
            "Lq — Avg buffer occupancy":    f"{self.Lq():.4f} packets",
            "L  — Avg packets in system":   f"{self.L():.4f} packets",
            "Wq — Avg queuing delay":       f"{self.Wq()*1000:.4f} ms",
            "W  — Avg total delay":         f"{self.W()*1000:.4f} ms",
            "P0 — Router idle probability": f"{self.P0()*100:.2f}%",
            "Buffer size (99% confidence)": f"{self.buffer_size()} packets",
        }


class NetworkMMK:
    """
    K parallel links / load-balanced router — M/M/K model.
    Models a router with K equal outgoing links sharing the traffic.
    """
    import math as _math

    def __init__(self, lam, mu, k):
        self.lam = lam
        self.mu  = mu
        self.k   = k
        self.rho = lam / (k * mu)

    def _P0(self):
        import math
        r = self.lam / self.mu
        k = self.k
        sum_terms = sum((r**n) / math.factorial(n) for n in range(k))
        last_term  = (r**k) / (math.factorial(k) * (1 - self.rho))
        return 1 / (sum_terms + last_term)

    def Lq(self):
        import math
        r  = self.lam / self.mu
        P0 = self._P0()
        return (P0 * (r**self.k) * self.rho) / \
               (math.factorial(self.k) * (1 - self.rho)**2)

    def Wq(self):
        return self.Lq() / self.lam

    def W(self):
        return self.Wq() + 1/self.mu

    def summary(self):
        return {
            "Model":                      f"M/M/{self.k} (Network)",
            "λ  — Arrival rate":          f"{self.lam} pkt/s",
            "μ  — Per-link service rate": f"{self.mu} pkt/s",
            "K  — Parallel links":        self.k,
            "ρ  — Per-link utilisation":  f"{self.rho:.4f}  ({self.rho*100:.1f}%)",
            "Lq — Avg buffer occupancy":  f"{self.Lq():.4f} packets",
            "Wq — Avg queuing delay":     f"{self.Wq()*1000:.4f} ms",
            "W  — Avg total delay":       f"{self.W()*1000:.4f} ms",
        }