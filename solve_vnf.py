"""
Risolve il modello AMPL (Model Formulation 3) con amplpy.

Installazione richiesta (una tantum):
    pip install amplpy
    python -m amplpy.modules install highs      # solver MILP open-source

codice si esegue con
uv run solve_vnf.py test/medium_8.dat --time-limit 120 [--out results/medium_8_results.txt]

"""

import os
import time
import argparse
import statistics
from amplpy import AMPL

start_time = time.time()

ampl = AMPL()

parser = argparse.ArgumentParser(description="Risolve il modello AMPL (Model Formulation 3) con amplpy.")
parser.add_argument("data_file", help="Percorso del file dati da risolvere")
parser.add_argument("--time-limit", type=int, default=120, dest="time_limit", help="Limite di tempo in secondi per il solver")
parser.add_argument("--model", type=str, default="models/vnf_model.mod", help="File del modello AMPL (default: models/vnf_model_coupling.mod)")
parser.add_argument("--out", type=str, default=None, help="Percorso del file di risultati (opzionale)")
args = parser.parse_args()

FILE_DATI = args.data_file

# Determina il tipo di modello dal nome del file
model_type = "sum" if "sum" in os.path.basename(args.model) else "max"

ampl.read(args.model)
ampl.read_data(FILE_DATI)

ampl.option["solver"] = "gurobi"
#ampl.option["solver"] = "highs"
ampl.option["gurobi_options"] = f"timelim={args.time_limit} return_bound=1"

ampl.solve()

end_time = time.time()
execution_time = end_time - start_time

if args.out:
    output_file = args.out
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
else:
    test_name = os.path.basename(FILE_DATI).split('.')[0]
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    output_file = os.path.join(results_dir, f"{test_name}_results.txt")

output_lines = []
def print_out(text=""):
    print(text)
    output_lines.append(str(text))

print_out(f"\n{'='*40}\n ESECUZIONE TEST: {FILE_DATI}\n{'='*40}\n")
print_out(f"Tempo di esecuzione: {execution_time:.2f} secondi")

result = ampl.get_value("solve_result")
print_out(f"solve_result: {result}")

# --- Raccolta metriche per riga di riepilogo ---
nome_istanza = os.path.basename(FILE_DATI).split('.')[0]
num_domande = len(list(ampl.get_set("D").members()))
ottimo = 1 if result == "solved" else 0
obj_name = "Obj_SumLatency" if model_type == "sum" else "Obj_MaxLatency"
upper_bound = None
lower_bound = None
gap_val = "N/A"

if result == "limit":
    print_out(f"\n--- LIMITE DI TEMPO ({args.time_limit}s) RAGGIUNTO ---")
    try:
        upper_bound = ampl.get_value(obj_name)
        lower_bound = ampl.get_value(f"{obj_name}.bestbound")
        print_out(f"Migliore soluzione (Upper Bound): {upper_bound}")
        print_out(f"Migliore lower bound: {lower_bound}")
        if lower_bound != 0:
            gap_val = f"{(upper_bound - lower_bound) / lower_bound:.6f}"
        else:
            gap_val = "inf"
    except Exception as e:
        print_out(f"Impossibile recuperare i bound: {e}")
elif result == "solved":
    gap_val = "0.0"

if result not in ("solved", "limit"):
    print_out("Nessuna soluzione ottima trovata.")
    aif_lat_values = [0.0, 0.0, 0.0]
    var_aif = 0.0
else:
    if model_type == "max":
        print_out(f"\nL_max = {ampl.get_value('Lmax')}")
    else:
        print_out(f"\nSum_L = {ampl.get_value(obj_name)}")

    print_out("\n--- Installazioni VNF (y_if = 1) ---")
    for (i, f), v in ampl.get_variable("y").get_values().to_dict().items():
        if v > 0.5:
            print_out(f"  VNF {f} installata sul nodo {i}")

    print_out("\n--- Assegnazioni domanda->VNF (z_if^k = 1) ---")
    z_dict = ampl.get_variable("z").get_values().to_dict()
    for (k, i, f), v in z_dict.items():
        if v > 0.5:
            print_out(f"  Domanda {k}: usa VNF {f} sul nodo {i}")

    print_out("\n--- Routing (x_ij^ks = 1) ---")
    for (k, i, j, s), v in ampl.get_variable("x").get_values().to_dict().items():
        if v > 0.5:
            print_out(f"  Domanda {k}, subpath {s}: arco ({i} -> {j})")

    print_out("\n--- Latenza per domanda ---")
    L_dict = ampl.get_variable("L").get_values().to_dict()
    for k, v in L_dict.items():
        print_out(f"  Domanda {k}: L = {v}")

    # Post-processing: calcolo latenze totali per nodo AIF (F4)
    alpha_dict = ampl.get_parameter("alpha").get_values().to_dict()
    aif_nodes = sorted([i for (i, f), v in alpha_dict.items() if f == 'F4' and v == 1])

    aif_latencies = {}
    for node in aif_nodes:
        total_lat = 0.0
        for (k, i, f), v in z_dict.items():
            if f == 'F4' and i == node and v > 0.5:
                total_lat += L_dict[k]
        aif_latencies[node] = total_lat

    aif_lat_values = [aif_latencies.get(n, 0.0) for n in aif_nodes]
    # Pad a 3 valori se meno di 3 nodi AIF attivi
    while len(aif_lat_values) < 3:
        aif_lat_values.append(0.0)

    var_aif = statistics.variance(aif_lat_values) if len(aif_lat_values) > 1 else 0.0

    print_out("\n--- Latenza totale per nodo AIF ---")
    for node in aif_nodes:
        print_out(f"  Nodo {node}: L_totale = {aif_latencies[node]:.6f}")
    print_out(f"  Varianza: {var_aif:.6f}")

# Costruisci riga CSV di riepilogo
csv_header = "nome_istanza,num_domande,ottimo,tempo,gap,modello,L_aif1,L_aif2,L_aif3,varianza_aif"
csv_values = (f"{nome_istanza},{num_domande},{ottimo},{execution_time:.2f},"
              f"{gap_val},{model_type},"
              f"{aif_lat_values[0]:.6f},{aif_lat_values[1]:.6f},{aif_lat_values[2]:.6f},"
              f"{var_aif:.6f}")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(csv_header + '\n')
    f.write(csv_values + '\n')
    f.write('\n'.join(output_lines) + '\n')
