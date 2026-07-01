#!/usr/bin/env python3
"""
build_medium_dataset.py
========================
Adapter che legge i dati grezzi in DataMedium/ (MAI modificati: solo lettura)
e genera un file .dat compatibile con lo schema atteso da vnf_model.mod
("Model Formulation 3": set N, A, D, F; param dem, o, chain, alpha,
delay, sigma, gamma, q, capArc, TAUNODE).

USO
---
Sintassi:
    python build_medium_dataset.py --clients {48,96} --topology {balanced,inst1} [--num-clients N] --out PATH

Esempi:
    python build_medium_dataset.py --clients 48 --topology balanced --out test/medium_48_balanced.dat
    python build_medium_dataset.py --clients 48 --topology balanced --num-clients 8 --out test/medium_8.dat

Il secondo esempio genera un'istanza "ridotta" (solo 8 client su 48) utile
per test di scalabilita' incrementale: 4 -> 8 -> 16 -> 24 -> 48 -> 96,
prima di lanciarsi sull'istanza completa.

ASSUNZIONI DI MAPPATURA (nessuna e' definita esplicitamente in DataMedium,
sono scelte di modellazione fatte per rendere i dati compatibili con lo
schema lineare attuale — vanno validate/riviste se poi si vuole
rappresentare fedelmente il costo a coda delle funzioni 5G Core):

  N        = DS (client) U V_EN U V_CN U V_BN U K
  A        = A0 U A1 U A2 U A4, resi bidirezionali (arco di ritorno
             con lo stesso delay), esclusi i self-loop (A_ee/A_cc/A_bb,
             che nel modello attuale non hanno alcun ruolo funzionale)
  delay    = bd + fd sommati per gli archi EN-CN/CN-BN (i due file sono
             complementari: fd copre EN-CN, bd copre CN-BN); 0 per i
             tratti DS-EN e BN-K, per cui DataMedium non fornisce dati
  F        = {F1, F2, F3, F4}, catena fissa F1 -> F2 -> F3 -> F4 (n = 4).
             Installabilita' basata sul livello 'lv' letto da
             inside_topology.dat (en=1, cn=2, bn=3):
               F1: livelli {1,2}   (edge + core)             -- da richiesta utente
               F2: livelli {1,2,3} (edge + core + border)    -- da richiesta utente
               F3: livello  {2,3}   (core + border)           -- da richiesta utente
               F4: livello  {3}     (solo border)             -- da richiesta utente
             I nodi DS e K non hanno livello definito in DataMedium:
             alpha=0 per loro su tutte le funzioni.
  q[f]     = capacita' (max domande servite) di ciascuna VNF per nodo.
              F2 <- DS_max (=40, capacita' reale dal file functions_5G_Core.dat).
              F1 <- q_queue, F3 <- q_inv_matr[1], F4 <- q_inv_matr[3]
              (placeholder numerici finche' non si hanno capacita' effettive).
  sigma[f] = gamma[f] = 0 per F1, F3, F4.
  Training time F2: il processing time di F2 e' dato dalla formula
              T[i,F2] = (c_batch + c_inv_matr[lv(i)]) * u + (q_batch + q_inv_matr[lv(i)]) * y
              dove u = num. domande assegnate, lv(i) = livello del nodo (1=EN, 2=CN, 3=BN).
              Questi parametri sono esportati nel .dat per il vincolo nel modello.
  T_target = 5000000 (da parameters.dat): vincolo T[i,F2] <= T_target.
  DS_max   = 40 (da functions_5G_Core.dat): vincolo sum z[k,i,F2] <= DS_max.
  o[k]     = k stesso (ogni client ds_i e' l'origine della domanda k=ds_i)
  dem[k]   = tt (da parameters.dat, unico fattore di traffico disponibile)
  capArc   = 1 (placeholder: il parametro esiste nel modello ma non e'
             usato da alcun vincolo)
  TAUNODE  = 'tau'
"""

import argparse
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "DataMedium"


# --------------------------------------------------------------------------
# Parsing minimale, mirato al layout esatto dei file in DataMedium
# --------------------------------------------------------------------------

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
    """param NAME := idx value idx value ... ;  -> dict[idx:int] = value"""
    m = re.search(rf"param\s+{name}\s*:=\s*(.*?);", text, re.S)
    if not m:
        raise ValueError(f"param {name} non trovato")
    toks = m.group(1).split()
    return {int(toks[i]): float(toks[i + 1]) for i in range(0, len(toks), 2)}


def parse_symbolic_param(text, name):
    """param NAME := node1 val1 node2 val2 ... ;  -> dict[str] = int"""
    m = re.search(rf"param\s+{name}\s*:=\s*(.*?);", text, re.S)
    if not m:
        raise ValueError(f"param {name} non trovato")
    toks = m.group(1).split()
    return {toks[i]: int(float(toks[i + 1])) for i in range(0, len(toks), 2)}


# Livelli su cui ciascuna funzione e' installabile (lv: en=1, cn=2, bn=3).
# F1, F2, F3, F4 da richiesta esplicita dell'utente
ALPHA_LEVELS = {
    "F1": {1, 2},
    "F2": {1, 2, 3},
    "F3": {2, 3},   
    "F4": {3},
}


# --------------------------------------------------------------------------


def build(clients: int, topology: str, num_clients: int | None):
    inside = (DATA_DIR / "inside_topology.dat").read_text()
    V_EN = parse_set(inside, "V_EN")
    V_CN = parse_set(inside, "V_CN")
    V_BN = parse_set(inside, "V_BN")
    K = parse_set(inside, "K")
    A1 = parse_arc_set(inside, "A1")
    A2 = parse_arc_set(inside, "A2")
    A4 = parse_arc_set(inside, "A4")
    lv = parse_symbolic_param(inside, "lv")

    topo_path = DATA_DIR / f"{clients}clients_{topology}_topology.dat"
    if not topo_path.exists():
        raise FileNotFoundError(f"Topologia non trovata: {topo_path.name}")
    topo = topo_path.read_text()
    DS_all = parse_set(topo, "DS")
    A0_all = parse_arc_set(topo, "A0")

    if num_clients is not None:
        DS = DS_all[:num_clients]
        ds_set = set(DS)
        A0 = [(a, b) for a, b in A0_all if a in ds_set]
    else:
        DS = DS_all
        A0 = A0_all

    bd = parse_param_matrix((DATA_DIR / "back_hauling_MAN.dat").read_text(), "bd")
    fd = parse_param_matrix((DATA_DIR / "front_hauling_MAN.dat").read_text(), "fd")

    funcs = (DATA_DIR / "functions_5G_Core.dat").read_text()
    DS_max_val = parse_scalar(funcs, "DS_max")
    c_batch = parse_scalar(funcs, "c_batch")
    c_inv_matr = parse_indexed_col(funcs, "c_inv_matr")
    q_queue = parse_scalar(funcs, "q_queue")
    q_batch = parse_scalar(funcs, "q_batch")
    q_inv_matr = parse_indexed_col(funcs, "q_inv_matr")

    params = (DATA_DIR / "parameters.dat").read_text()
    tt = parse_scalar(params, "tt")
    T_target = parse_scalar(params, "T_target")

    # ---- N ----
    N = list(DS) + V_EN + V_CN + V_BN + K

    # ---- A (bidirezionale) + delay ----
    def seg_delay(a, b):
        return bd.get((a, b), 0.0) + fd.get((a, b), 0.0)

    A_all = list(A0) + A1 + A2 + list(A4)
    delay = {}
    A = []
    for a, b in A_all:
        d = seg_delay(a, b)
        A.append((a, b))
        A.append((b, a))
        delay[(a, b)] = d
        delay[(b, a)] = d

    # ---- F, chain, q, sigma, gamma ----
    F = ["F1", "F2", "F3", "F4"]
    chain = {1: "F1", 2: "F2", 3: "F3", 4: "F4"}
    q = {
        "F1": q_queue,
        "F2": DS_max_val,     # capacita' reale: DS_max
        "F3": q_inv_matr[1],
        "F4": q_inv_matr[3],
    }
    sigma = {f: 0.0 for f in F}
    gamma = {f: 0.0 for f in F}

    # ---- alpha: installabilita' per livello (vedi ALPHA_LEVELS) ----
    def alpha_val(node, f):
        level = lv.get(node)
        return 1 if level is not None and level in ALPHA_LEVELS[f] else 0

    # ---- D, o, dem ----
    D = list(DS)
    o = {k: k for k in D}
    dem = {k: tt for k in D}

    return {
        "N": N, "A": A, "delay": delay,
        "F": F, "chain": chain, "q": q, "sigma": sigma, "gamma": gamma,
        "alpha_val": alpha_val,
        "D": D, "o": o, "dem": dem,
        # parametri training time F2 (federated learning)
        "lv": lv, "c_batch": c_batch, "c_inv_matr": c_inv_matr,
        "q_batch": q_batch, "q_inv_matr": q_inv_matr,
        "T_target": T_target, "DS_max": DS_max_val,
    }


# --------------------------------------------------------------------------
# Scrittura .dat in stile AMPL (stesso stile di test/test_1.dat)
# --------------------------------------------------------------------------

def write_dat(data, out_path: Path, source_label: str):
    N, A, delay = data["N"], data["A"], data["delay"]
    F, chain, q, sigma, gamma = data["F"], data["chain"], data["q"], data["sigma"], data["gamma"]
    alpha_val = data["alpha_val"]
    D, o, dem = data["D"], data["o"], data["dem"]
    lv = data["lv"]
    c_batch = data["c_batch"]
    c_inv_matr = data["c_inv_matr"]
    q_batch = data["q_batch"]
    q_inv_matr = data["q_inv_matr"]
    T_target = data["T_target"]
    DS_max = data["DS_max"]

    lines = []
    lines.append("data;")
    lines.append("")
    lines.append(f"# Generato da build_medium_dataset.py a partire da DataMedium/ ({source_label})")
    lines.append("# DataMedium NON è stato modificato: questo è un file derivato.")
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
    lines.append(" ".join(f"{s} {f}" for s, f in chain.items()) + ";")
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
    lines.append("param sigma := " + " ".join(f"{f} {sigma[f]:.4f}" for f in F) + ";")
    lines.append("param gamma := " + " ".join(f"{f} {gamma[f]:.4f}" for f in F) + ";")
    lines.append("param q     := " + " ".join(f"{f} {q[f]:.4f}" for f in F) + ";")
    lines.append("")
    lines.append("param dem :=")
    lines.append(" ".join(f"{k} {v:.4f}" for k, v in dem.items()) + ";")
    lines.append("param capArc := 1;")
    lines.append("")
    # ---- Parametri training time F2 (federated learning) ----
    lines.append("# Parametri training time F2 (federated learning)")
    lines.append(f"param c_batch := {c_batch:.10g};")
    lines.append("param c_inv_matr :=")
    lines.append(" ".join(f"{k} {v:.10g}" for k, v in sorted(c_inv_matr.items())) + ";")
    lines.append(f"param q_batch := {q_batch:.10g};")
    lines.append("param q_inv_matr :=")
    lines.append(" ".join(f"{k} {v:.10g}" for k, v in sorted(q_inv_matr.items())) + ";")
    lines.append("param lv :=")
    lines.append(" ".join(f"{node} {level}" for node, level in lv.items()) + ";")
    lines.append(f"param T_target := {T_target:.10g};")
    lines.append(f"param DS_max := {DS_max:.10g};")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"Scritto {out_path}  (|N|={len(N)}, |A|={len(A)}, |D|={len(D)}, |F|={len(F)})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clients", type=int, choices=[48, 96], required=True,
                     help="Quale file di topologia usare come base (48 o 96 client)")
    ap.add_argument("--topology", choices=["balanced", "inst1"], required=True,
                     help="Variante di topologia")
    ap.add_argument("--num-clients", type=int, default=None,
                     help="Limita ai primi N client (per test incrementali). Default: tutti.")
    ap.add_argument("--out", type=Path, required=True, help="Percorso file .dat di output")
    args = ap.parse_args()

    data = build(args.clients, args.topology, args.num_clients)
    label = f"{args.clients}clients_{args.topology}"
    if args.num_clients:
        label += f"_first{args.num_clients}"
    write_dat(data, args.out, label)


if __name__ == "__main__":
    main()
