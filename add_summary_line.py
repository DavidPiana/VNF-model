"""
Script post-hoc per aggiungere la riga di riepilogo CSV ai file di risultati
che ne sono sprovvisti (mandala_balanced, mandala_inst1).

Esecuzione: uv run add_summary_line.py
"""

import os
import re
import statistics
import glob


def extract_summary_from_file(filepath):
    """Legge un file di risultati e ne estrae i campi per la riga CSV."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # --- nome_istanza ---
    m = re.search(r"ESECUZIONE TEST:.*?([^\\/]+)\.dat", content)
    if not m:
        print(f"  SKIP: impossibile trovare nome istanza in {filepath}")
        return None
    nome_istanza = m.group(1)

    # --- tempo ---
    m = re.search(r"Tempo di esecuzione:\s+([\d.]+)\s+secondi", content)
    tempo = float(m.group(1)) if m else 0.0

    # --- solve_result ---
    m = re.search(r"solve_result:\s+(\S+)", content)
    solve_result = m.group(1) if m else "unknown"
    ottimo = 1 if solve_result == "solved" else 0

    # --- gap ---
    if solve_result == "solved":
        gap_val = "0.0"
    elif solve_result == "limit":
        ub_match = re.search(r"Migliore soluzione \(Upper Bound\):\s+([\d.]+)", content)
        lb_match = re.search(r"Migliore lower bound:\s+([\d.]+)", content)
        if ub_match and lb_match:
            ub = float(ub_match.group(1))
            lb = float(lb_match.group(1))
            gap_val = f"{(ub - lb) / lb:.6f}" if lb != 0 else "inf"
        else:
            gap_val = "N/A"
    else:
        gap_val = "N/A"

    # --- modello ---
    if re.search(r"L_max\s*=", content):
        modello = "max"
    elif re.search(r"Sum_L\s*=", content):
        modello = "sum"
    else:
        modello = "max"  # default

    # --- num_domande (conta domande uniche nella sezione latenza) ---
    latency_matches = re.findall(r"Domanda\s+(\S+):\s+L\s*=\s*([\d.eE+-]+)", content)
    num_domande = len(latency_matches)
    L_dict = {name: float(val) for name, val in latency_matches}

    # --- Assegnazioni F4 (nodi AIF) ---
    # Pattern: "Domanda XXX: usa VNF F4 sul nodo YYY"
    f4_assignments = re.findall(
        r"Domanda\s+(\S+):\s+usa VNF F4 sul nodo\s+(\S+)", content
    )

    # Mappa nodo_AIF -> lista di domande assegnate
    aif_demand_map = {}
    for demand, node in f4_assignments:
        aif_demand_map.setdefault(node, []).append(demand)

    # Calcolo latenze totali per nodo AIF
    aif_nodes = sorted(aif_demand_map.keys())
    aif_latencies = {}
    for node in aif_nodes:
        total_lat = 0.0
        for demand in aif_demand_map[node]:
            total_lat += L_dict.get(demand, 0.0)
        aif_latencies[node] = total_lat

    aif_lat_values = [aif_latencies.get(n, 0.0) for n in aif_nodes]
    # Pad a 3 valori se meno di 3 nodi AIF attivi
    while len(aif_lat_values) < 3:
        aif_lat_values.append(0.0)

    var_aif = statistics.variance(aif_lat_values) if len(aif_lat_values) > 1 else 0.0

    return {
        "nome_istanza": nome_istanza,
        "num_domande": num_domande,
        "ottimo": ottimo,
        "tempo": f"{tempo:.2f}",
        "gap": gap_val,
        "modello": modello,
        "L_aif1": f"{aif_lat_values[0]:.6f}",
        "L_aif2": f"{aif_lat_values[1]:.6f}",
        "L_aif3": f"{aif_lat_values[2]:.6f}",
        "varianza_aif": f"{var_aif:.6f}",
    }


def process_file(filepath):
    """Aggiunge la riga di riepilogo CSV in cima al file se mancante."""
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()

    csv_header = "nome_istanza,num_domande,ottimo,tempo,gap,modello,L_aif1,L_aif2,L_aif3,varianza_aif"

    # Skip se già presente
    if first_line.strip() == csv_header:
        print(f"  SKIP (già presente): {os.path.basename(filepath)}")
        return False

    summary = extract_summary_from_file(filepath)
    if summary is None:
        return False

    csv_values = (
        f"{summary['nome_istanza']},{summary['num_domande']},{summary['ottimo']},"
        f"{summary['tempo']},{summary['gap']},{summary['modello']},"
        f"{summary['L_aif1']},{summary['L_aif2']},{summary['L_aif3']},"
        f"{summary['varianza_aif']}"
    )

    with open(filepath, "r", encoding="utf-8") as f:
        original_content = f.read()

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(csv_header + "\n")
        f.write(csv_values + "\n")
        f.write(original_content)

    print(f"  OK: {os.path.basename(filepath)}")
    print(f"       {csv_values}")
    return True


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    directories = [
        os.path.join(base_dir, "results", "mandala_balanced"),
        os.path.join(base_dir, "results", "mandala_inst1"),
    ]

    total_processed = 0
    total_skipped = 0

    for directory in directories:
        if not os.path.isdir(directory):
            print(f"Directory non trovata: {directory}")
            continue

        print(f"\n{'='*60}")
        print(f"  Processando: {directory}")
        print(f"{'='*60}")

        files = sorted(glob.glob(os.path.join(directory, "*_results.txt")))
        for filepath in files:
            if process_file(filepath):
                total_processed += 1
            else:
                total_skipped += 1

    print(f"\n--- Riepilogo ---")
    print(f"File processati: {total_processed}")
    print(f"File saltati:    {total_skipped}")


if __name__ == "__main__":
    main()
