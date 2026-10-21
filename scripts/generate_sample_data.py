"""Generate a synthetic labelled flow dataset for Phase 2 local verification.

Produces data/samples/flows_sample.csv with the fields we expect in
FlowRecord, plus a `label` column for supervised evaluation.

Three classes:
  - normal        : steady bidirectional traffic, high bytes, moderate packets
  - port_scan     : SYN-heavy, low byte counts, many distinct dest ports from same src IP
  - brute_force   : high packet rate to single service port (22/3389), short duration,
                    repeated patterns

This is NOT a real intrusion-detection dataset. Distributions are hand-tuned
so a RuleDemoDetector and a simple sklearn baseline can both get non-trivial
precision/recall against it. Real results MUST NOT be extrapolated to CICIDS
or other published datasets.
"""
from __future__ import annotations

import csv
import os
import random
from pathlib import Path
from typing import Tuple

import numpy as np

RNG = np.random.default_rng(42)
random.seed(42)


OUT = Path(__file__).resolve().parents[1] / "data" / "samples" / "flows_sample.csv"


# ---------------------- label-specific generators --------------------------

def _rand_ip(prefixes: list[str]) -> str:
    p = random.choice(prefixes)
    return f"{p}.{random.randint(1, 254)}"


def _normal_flow(src: str, dst: str) -> dict:
    """Web / database traffic — lots of bytes, balanced packets."""
    return {
        "src_ip": src,
        "dst_ip": dst,
        "src_port": random.randint(1024, 65535),
        "dst_port": random.choice([80, 443, 8080, 3306]),
        "protocol": "TCP",
        "duration_ms": max(1.0, RNG.normal(2000, 800)),
        "packets_src_to_dst": max(1, int(RNG.normal(120, 40))),
        "packets_dst_to_src": max(1, int(RNG.normal(100, 35))),
        "bytes_src_to_dst": max(60, int(RNG.normal(15000, 5000))),
        "bytes_dst_to_src": max(60, int(RNG.normal(12000, 4000))),
    }


def _port_scan_flow(src: str, dst: str) -> dict:
    """Port scan — low bytes, low duration, SYN-like packet counts."""
    return {
        "src_ip": src,
        "dst_ip": dst,
        "src_port": random.randint(40000, 65535),
        "dst_port": random.randint(1, 1023),
        "protocol": "TCP",
        "duration_ms": max(0.1, RNG.normal(30, 10)),
        "packets_src_to_dst": max(1, int(RNG.normal(3, 1))),
        "packets_dst_to_src": max(0, int(RNG.normal(0.5, 0.5))),
        "bytes_src_to_dst": max(40, int(RNG.normal(60, 10))),
        "bytes_dst_to_src": max(0, int(RNG.normal(10, 15))),
    }


def _brute_force_flow(src: str, dst: str) -> dict:
    """SSH / RDP brute force — short, many tiny packets, single dst_port."""
    target_port = random.choice([22, 3389])
    return {
        "src_ip": src,
        "dst_ip": dst,
        "src_port": random.randint(20000, 50000),
        "dst_port": target_port,
        "protocol": "TCP",
        "duration_ms": max(0.2, RNG.normal(150, 40)),
        "packets_src_to_dst": max(2, int(RNG.normal(15, 5))),
        "packets_dst_to_src": max(1, int(RNG.normal(5, 2))),
        "bytes_src_to_dst": max(60, int(RNG.normal(400, 120))),
        "bytes_dst_to_src": max(60, int(RNG.normal(300, 100))),
    }


def _compute_features(r: dict) -> dict:
    """Derive the numeric feature vector the detector will see.

    Keep the space small (~7 features) so a LogisticRegression baseline
    can fit it on CPU in under a second.
    """
    total_pkts = r["packets_src_to_dst"] + r["packets_dst_to_src"]
    total_bytes = r["bytes_src_to_dst"] + r["bytes_dst_to_src"]
    dur = max(r["duration_ms"], 1e-6)

    return {
        "pkt_rate": total_pkts / dur,              # packets per ms
        "byte_rate": total_bytes / dur,            # bytes per ms
        "pkt_ratio": r["packets_src_to_dst"] / max(r["packets_dst_to_src"], 1),
        "avg_pkt_size": total_bytes / max(total_pkts, 1),
        "dst_port_common": 1.0 if r["dst_port"] in {80, 443, 8080, 3306, 22, 3389} else 0.0,
        "is_short": 1.0 if dur < 50.0 else 0.0,   # < 50 ms — suspiciously short
        "byte_pkt_ratio": total_bytes / max(total_pkts, 1),  # alias kept for clarity
    }


def generate(n_per_class: int = 1000, seed: int = 42) -> Path:
    """Write the sample CSV. Returns the output path."""
    RNG = np.random.default_rng(seed)
    random.seed(seed)

    OUT.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []

    # --- Normal traffic: many src IPs, balanced destinations ---
    for _ in range(n_per_class):
        src = _rand_ip(["10.0", "172.16", "192.168"])
        dst = _rand_ip(["10.0"])
        r = _normal_flow(src, dst)
        r["label"] = "normal"
        rows.append(r)

    # --- Port scan: one persistent attacker IP sweeping many dst ports ---
    attacker = "192.168.250.99"
    victims = [_rand_ip(["10.0"]) for _ in range(8)]
    for _ in range(n_per_class):
        r = _port_scan_flow(attacker, random.choice(victims))
        r["label"] = "port_scan"
        rows.append(r)

    # --- Brute force: several attacker IPs hammering SSH/RDP ---
    attackers_bf = [_rand_ip(["192.168.200"]) for _ in range(5)]
    bf_targets = [_rand_ip(["10.0"]) for _ in range(3)]
    for _ in range(n_per_class):
        r = _brute_force_flow(random.choice(attackers_bf), random.choice(bf_targets))
        r["label"] = "brute_force"
        rows.append(r)

    # Shuffle so classes are interleaved (closer to real-world ordering)
    random.shuffle(rows)

    feature_cols = [
        "pkt_rate", "byte_rate", "pkt_ratio", "avg_pkt_size",
        "dst_port_common", "is_short", "byte_pkt_ratio",
    ]

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "src_ip", "dst_ip", "src_port", "dst_port", "protocol",
                "duration_ms",
                "packets_src_to_dst", "packets_dst_to_src",
                "bytes_src_to_dst", "bytes_dst_to_src",
                *feature_cols,
                "label",
            ],
        )
        writer.writeheader()
        for r in rows:
            feats = _compute_features(r)
            r.update(feats)
            writer.writerow(r)

    print(f"[generate_sample_data] wrote {len(rows)} rows → {OUT}")
    return OUT


if __name__ == "__main__":
    generate()
