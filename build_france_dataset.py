#!/usr/bin/env python3
"""
build_france_dataset.py
=======================
Legge i file dati intermedi in Data/France/ e il dataset SNDLIB_France 
per generare un file .dat compatibile con vnf_model.mod (Model Formulation 3).

Rispetto a DataMedium, la rete e' piatta (tutti nodi V). I nodi AIF hanno lv=2, gli altri lv=1.
Le domande sono lette da SNDLIB_France e collegate tramite nodi fittizi ds_* .

USO
---
python build_france_dataset.py [--num-demands N] --out PATH

Esempio:
    python build_france_dataset.py --num-demands 10 --out test/france_10.dat
"""

import argparse
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "Data" / "France"

def parse_set(text, name):
    m = re.search(rf"set\s+{name}\s*:=\s*(.*?);", text, re.S)
    if not m:
        raise ValueError(f"set {name} non trovato")
    return m.group(1).split()

def parse_arc_set(text, name):
    m = re.search(rf"set\s+{name}\s*:=\s*(.*?);", text, re.S)
    if not m:
        raise ValueError(f"set {name} non trovato")
    return [(a.strip(), b.strip()) for a, b in re.findall(r"\(([^,]+),([^)]+)\)", m.group(1))]

def parse_param_matrix(text, name):
    m = re.search(rf"param\s+{name}\s*:=\s*(.*?);", text, re.S)
    if not m:
        raise ValueError(f"param {name} non trovato")
    toks = m.group(1).split()
    return {(toks[i], toks[i + 1]): float(toks[i + 2]) for i in range(0, len(toks), 3)}

def parse_scalar(text, name):
    m = re.search(rf"param\s+{name}\s*:=\s*([^\s;]+)\s*;", text)
    if not m:
        raise ValueError(f"param {name} non trovato")
    return float(m.group(1))

def parse_indexed_col(text, name):
    m = re.search(rf"param\s+{name}\s*:=\s*(.*?);", text, re.S)
    if not m:
        raise ValueError(f"param {name} non trovato")
    toks = m.group(1).split()
    return {int(toks[i]): float(toks[i + 1]) for i in range(0, len(toks), 2)}

def parse_symbolic_param(text, name):
    m = re.search(rf"param\s+{name}\s*:=\s*(.*?);", text, re.S)
    if not m:
        raise ValueError(f"param {name} non trovato")
    toks = m.group(1).split()
    return {toks[i]: int(float(toks[i + 1])) for i in range(0, len(toks), 2)}

def parse_sndlib_demands(text):
    demands = []
    for m in re.finditer(r"(D\d+_\w+_\w+)\s*\(\s*(N\d+)\s+(N\d+)\s*\)\s*([\d.]+)\s*([\d.]+)\s*([\d.]+)", text):
        did, src, tgt, val = m.group(1), m.group(2), m.group(3), float(m.group(5))
        demands.append((did, src, tgt, val))
    return demands

def build(num_demands: int | None, start_demand: int = 0):
    # Leggi topologia
    inside = (DATA_DIR / "inside_topology_France").read_text()
    V = parse_set(inside, "V")
    AIF = set(parse_set(inside, "AIF"))
    A_links = parse_arc_set(inside, "A_links")
    lv = parse_symbolic_param(inside, "lv")
    
    # Leggi delay
    delay_data = parse_param_matrix((DATA_DIR / "delay_France.dat").read_text(), "delay_link")
    
    # Leggi parametri 5G
    funcs = (DATA_DIR / "functions_5G_Core.dat").read_text()
    DS_max_val = parse_scalar(funcs, "DS_max")
    c_queue = parse_scalar(funcs, "c_queue")
    c_batch = parse_scalar(funcs, "c_batch")
    c_inv_matr = parse_indexed_col(funcs, "c_inv_matr")
    q_queue = parse_scalar(funcs, "q_queue")
    q_batch = parse_scalar(funcs, "q_batch")
    q_inv_matr = parse_indexed_col(funcs, "q_inv_matr")
    
    # Leggi params generali
    params = (DATA_DIR / "parameters.dat").read_text()
    tt = parse_scalar(params, "tt")
    T_target = parse_scalar(params, "T_target")
    
    # Leggi SNDLIB_France per le domande
    sndlib_text = (DATA_DIR / "SNDLIB_France").read_text()
    all_demands = parse_sndlib_demands(sndlib_text)
    
    # Filtra domande: escludi se src è AIF
    valid_demands = [d for d in all_demands if d[1] not in AIF]
    
    if num_demands is not None:
        valid_demands = valid_demands[start_demand:start_demand + num_demands]
        
    D = []
    DS = []
    o = {}
    dem = {}
    A0 = [] # archi ds -> source
    
    for did, src, tgt, val in valid_demands:
        ds_id = f"ds_{did}"
        D.append(ds_id)
        DS.append(ds_id)
        o[ds_id] = ds_id
        dem[ds_id] = tt
        A0.append((ds_id, src))
        
    # Costruisci N e A — de-duplica archi dalla topologia
    seen_arcs = set()
    A_dedup = []
    for a, b in A_links:
        if (a, b) not in seen_arcs:
            seen_arcs.add((a, b))
            A_dedup.append((a, b))

    N = DS + V
    A = A_dedup + A0
    
    delay = {}
    for a, b in A_dedup:
        delay[(a, b)] = delay_data.get((a, b), 0.0)
    for a, b in A0:
        delay[(a, b)] = 0.0
        
    # Funzioni e parametri
    F = ["F1", "F2", "F3", "F4"]
    chain = {1: "F1", 2: "F2", 3: "F3", 4: "F4"}
    q = {"F1": q_queue, "F2": DS_max_val, "F3": q_inv_matr[1], "F4": q_inv_matr[3]}
    sigma = {"F1": q_queue, "F2": 0.0, "F3": q_queue, "F4": 0.0}
    gamma = {"F1": c_queue, "F2": 0.0, "F3": c_queue, "F4": 0.0}
    
    def alpha_val(node, f):
        if node in DS:
            return 0
        if f in ("F1", "F2", "F3"):
            return 1
        else: # F4
            return 1 if node in AIF else 0
            
    return {
        "N": N, "A": A, "delay": delay,
        "F": F, "chain": chain, "q": q, "sigma": sigma, "gamma": gamma,
        "alpha_val": alpha_val,
        "D": D, "o": o, "dem": dem,
        "lv": lv, "c_batch": c_batch, "c_inv_matr": c_inv_matr,
        "q_batch": q_batch, "q_inv_matr": q_inv_matr,
        "T_target": T_target, "DS_max": DS_max_val,
    }

def write_dat(data, out_path: Path):
    lines = []
    lines.append("data;")
    lines.append("")
    lines.append(f"set N := {' '.join(data['N'])};")
    lines.append("set A :=")
    lines.append(" ".join(f"({a},{b})" for a, b in data["A"]) + ";")
    lines.append("")
    
    lines.append(f"set D := {' '.join(data['D'])};")
    lines.append(f"set F := {' '.join(data['F'])};")
    lines.append("")
    
    lines.append(f"param n := {len(data['F'])};")
    lines.append("param chain :=")
    lines.append(" ".join(f"{s} {f}" for s, f in data["chain"].items()) + ";")
    lines.append("")
    
    lines.append("param TAUNODE := tau;")
    lines.append("param o :=")
    lines.append(" ".join(f"{k} {v}" for k, v in data["o"].items()) + ";")
    lines.append("")
    
    lines.append("param alpha:  " + "  ".join(data["F"]) + " :=")
    for i in data["N"]:
        row = "  ".join(str(data["alpha_val"](i, f)) for f in data["F"])
        lines.append(f"{i}  {row}")
    lines[-1] += ";"
    lines.append("")
    
    lines.append("param delay :=")
    lines.append(" ".join(f"[{a},{b}] {data['delay'][(a,b)]:.4f}" for a, b in data["A"]) + ";")
    lines.append("")
    
    lines.append("param sigma := " + " ".join(f"{f} {data['sigma'][f]:.4f}" for f in data["F"]) + ";")
    lines.append("param gamma := " + " ".join(f"{f} {data['gamma'][f]:.4f}" for f in data["F"]) + ";")
    lines.append("param q     := " + " ".join(f"{f} {data['q'][f]:.4f}" for f in data["F"]) + ";")
    lines.append("")
    
    lines.append("param dem :=")
    lines.append(" ".join(f"{k} {v:.4f}" for k, v in data["dem"].items()) + ";")
    lines.append("param capArc := 1;")
    lines.append("")
    
    lines.append(f"param c_batch := {data['c_batch']:.10g};")
    lines.append("param c_inv_matr :=")
    lines.append(" ".join(f"{k} {v:.10g}" for k, v in sorted(data["c_inv_matr"].items())) + ";")
    lines.append(f"param q_batch := {data['q_batch']:.10g};")
    lines.append("param q_inv_matr :=")
    lines.append(" ".join(f"{k} {v:.10g}" for k, v in sorted(data["q_inv_matr"].items())) + ";")
    
    lines.append("param lv :=")
    lines.append(" ".join(f"{node} {level}" for node, level in data["lv"].items()) + ";")
    lines.append(f"param T_target := {data['T_target']:.10g};")
    lines.append(f"param DS_max := {data['DS_max']:.10g};")
    lines.append("")
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Scritto {out_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-demands", type=int, default=None)
    parser.add_argument("--start-demand", type=int, default=0)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args()
    
    data = build(num_demands=args.num_demands, start_demand=args.start_demand)
    write_dat(data, Path(args.out))

if __name__ == "__main__":
    main()
