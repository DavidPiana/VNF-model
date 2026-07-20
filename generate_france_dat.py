#!/usr/bin/env python3
"""
generate_france_dat.py
======================
Genera un file .dat compatibile con vnf_model.mod usando la topologia
SNDLIB France. I nodi AIF sono {N15, N19, N9}.

- N = N1..N24 (tutti i nodi France)
- A = archi bidirezionali dalla sezione LINKS di SNDLIB_France
- delay = distanza euclidea dalle coordinate dei nodi
- D = domande da SNDLIB escluse quelle in cui la sorgente e' un nodo AIF
- alpha: F1,F2,F3 = 1 per tutti i nodi; F4 = 1 solo per {N15, N19, N9}
- altri parametri: invariati rispetto ai file mandala esistenti
"""

import re
import math
from pathlib import Path

# --- Paths ---
SNDLIB = Path("Data/DataMedium/France/SNDLIB_France")
OUT    = Path("test/france_inst1.dat")

# --- AIF nodes ---
AIF_NODES = {"N15", "N19", "N9"}

# --- Fixed parameters (same as existing mandala files) ---
C_BATCH    = -102.564103
C_INV_MATR = {1: 230.7692308, 2: 115.3846154, 3: 230.7692308}
Q_BATCH    = 5102.5641
Q_INV_MATR = {1: 769.230769, 2: 384.615384, 3: 769.230769}
Q_QUEUE    = 384.615385
C_QUEUE    = 115.3846154
DS_MAX     = 40.0
T_TARGET   = 5000000.0
TT         = 1.65   # demand value per node (from parameters.dat)

SIGMA = {"F1": Q_QUEUE, "F2": 0.0, "F3": Q_QUEUE, "F4": 0.0}
GAMMA = {"F1": C_QUEUE, "F2": 0.0, "F3": C_QUEUE, "F4": 0.0}
Q     = {"F1": Q_QUEUE, "F2": DS_MAX, "F3": Q_INV_MATR[1], "F4": Q_INV_MATR[3]}
F     = ["F1", "F2", "F3", "F4"]
CHAIN = {1: "F1", 2: "F2", 3: "F3", 4: "F4"}


def parse_sndlib(text):
    """Parse SNDLIB native format file."""
    # Parse nodes with coordinates
    nodes = {}
    nodes_match = re.search(r"NODES\s*\((.*?)\)", text, re.S)
    if not nodes_match:
        raise ValueError("NODES section not found")
    for m in re.finditer(r"(N\d+)\s*\(\s*([\d.]+)\s+([\d.]+)\s*\)", nodes_match.group(1)):
        nid, x, y = m.group(1), float(m.group(2)), float(m.group(3))
        nodes[nid] = (x, y)

    # Parse links: format is
    #   <link_id> ( <src> <tgt> ) <pre_cap> <pre_cap_cost> <routing_cost> <setup_cost> (...)
    links = []
    links_match = re.search(r"LINKS\s*\((.*?)\)", text, re.S)
    if not links_match:
        raise ValueError("LINKS section not found")
    for m in re.finditer(
        r"L\w+\s*\(\s*(N\d+)\s+(N\d+)\s*\)\s*([\d.]+)\s*([\d.]+)\s*([\d.]+)",
        links_match.group(1)
    ):
        src, tgt = m.group(1), m.group(2)
        links.append((src, tgt))

    # Parse demands: format is
    #   <demand_id> ( <src> <tgt> ) <routing_unit> <demand_value> <max_path_length>
    demands = []
    demands_match = re.search(r"DEMANDS\s*\((.*?)\)", text, re.S)
    if not demands_match:
        raise ValueError("DEMANDS section not found")
    for m in re.finditer(
        r"(D\w+)\s*\(\s*(N\d+)\s+(N\d+)\s*\)\s*([\d.]+)\s*([\d.]+)",
        demands_match.group(1)
    ):
        did, src, tgt, val = m.group(1), m.group(2), m.group(3), float(m.group(5))
        demands.append((did, src, tgt, val))

    return nodes, links, demands


def euclidean(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def alpha_val(node, f):
    if f in ("F1", "F2", "F3"):
        return 1
    else:  # F4
        return 1 if node in AIF_NODES else 0


def main():
    text = SNDLIB.read_text(encoding="utf-8")
    nodes, links, demands = parse_sndlib(text)

    # Node list ordered numerically
    N = sorted(nodes.keys(), key=lambda x: int(x[1:]))

    # Arcs: bidirectional from links, deduplicated
    seen_arcs = set()
    A = []
    delay = {}
    for src, tgt in links:
        d = euclidean(nodes[src], nodes[tgt])
        for a, b in [(src, tgt), (tgt, src)]:
            if (a, b) not in seen_arcs:
                seen_arcs.add((a, b))
                A.append((a, b))
                delay[(a, b)] = d

    # Demands: exclude those whose SOURCE is an AIF node
    D = []
    o = {}
    dem = {}
    for did, src, tgt, val in demands:
        if src in AIF_NODES:
            continue  # rimuovi demands dai nodi AIF
        D.append(did)
        o[did] = src
        dem[did] = val

    # lv: nodi AIF → livello 3 (border), tutti gli altri → livello 2
    lv = {n: (3 if n in AIF_NODES else 2) for n in N}

    # --- Write .dat in AMPL style ---
    lines = []
    lines.append("data;")
    lines.append("")
    lines.append("# Generato da generate_france_dat.py a partire da SNDLIB_France")
    lines.append("# Topologia France (24 nodi), nodi AIF: N9, N15, N19")
    lines.append("# DataMedium NON e' stato modificato: questo e' un file derivato.")
    lines.append("")

    lines.append(f"set N := {' '.join(N)};")
    lines.append("set A :=")
    lines.append(" ".join(f"({a},{b})" for a, b in A) + ";")
    lines.append("")

    lines.append(f"set D := {' '.join(D)};")
    lines.append(f"set F := {' '.join(F)};")
    lines.append("")

    lines.append(f"param n := {len(F)};")
    lines.append("param chain :=")
    lines.append(" ".join(f"{s} {f}" for s, f in CHAIN.items()) + ";")
    lines.append("")

    lines.append("param TAUNODE := tau;")
    lines.append("param o :=")
    lines.append(" ".join(f"{k} {v}" for k, v in o.items()) + ";")
    lines.append("")

    lines.append("param alpha:  " + "  ".join(F) + " :=")
    for i in N:
        row = "  ".join(str(alpha_val(i, f)) for f in F)
        lines.append(f"{i}  {row}")
    lines[-1] = lines[-1] + ";"
    lines.append("")

    lines.append("param delay :=")
    lines.append(" ".join(f"[{a},{b}] {delay[(a, b)]:.4f}" for a, b in A) + ";")
    lines.append("")

    lines.append("param sigma := " + " ".join(f"{f} {SIGMA[f]:.4f}" for f in F) + ";")
    lines.append("param gamma := " + " ".join(f"{f} {GAMMA[f]:.4f}" for f in F) + ";")
    lines.append("param q     := " + " ".join(f"{f} {Q[f]:.4f}" for f in F) + ";")
    lines.append("")

    lines.append("param dem :=")
    lines.append(" ".join(f"{k} {v:.4f}" for k, v in dem.items()) + ";")
    lines.append("param capArc := 1;")
    lines.append("")

    lines.append("# Parametri training time F2 (federated learning)")
    lines.append(f"param c_batch := {C_BATCH:.10g};")
    lines.append("param c_inv_matr :=")
    lines.append(" ".join(f"{k} {v:.10g}" for k, v in sorted(C_INV_MATR.items())) + ";")
    lines.append(f"param q_batch := {Q_BATCH:.10g};")
    lines.append("param q_inv_matr :=")
    lines.append(" ".join(f"{k} {v:.10g}" for k, v in sorted(Q_INV_MATR.items())) + ";")
    lines.append("param lv :=")
    lines.append(" ".join(f"{node} {level}" for node, level in lv.items()) + ";")
    lines.append(f"param T_target := {T_TARGET:.10g};")
    lines.append(f"param DS_max := {DS_MAX:.10g};")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Scritto {OUT}")
    print(f"  |N| = {len(N)}")
    print(f"  |A| = {len(A)}")
    print(f"  |D| = {len(D)}")
    print(f"  |F| = {len(F)}")
    print(f"  AIF nodes con F4=1: {sorted(AIF_NODES)}")
    print(f"  Demands escluse (sorgente AIF): {sum(1 for d,s,t,v in demands if s in AIF_NODES)}")


if __name__ == "__main__":
    main()
