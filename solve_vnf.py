"""
Risolve il modello AMPL (Model Formulation 3) con amplpy.

Installazione richiesta (una tantum):
    pip install amplpy
    python -m amplpy.modules install highs      # solver MILP open-source

codice si esegue con
uv run solve_vnf.py test/medium_8.dat --time-limit 120 [--out medium_8_results.txt]

"""

import os
import time
import argparse
from amplpy import AMPL

start_time = time.time()

ampl = AMPL()

parser = argparse.ArgumentParser(description="Risolve il modello AMPL (Model Formulation 3) con amplpy.")
parser.add_argument("data_file", help="Percorso del file dati da risolvere")
parser.add_argument("--time-limit", type=int, default=120, dest="time_limit", help="Limite di tempo in secondi per il solver")
parser.add_argument("--model", type=str, default="vnf_model.mod", help="File del modello AMPL (default: vnf_model.mod)")
parser.add_argument("--out", type=str, default=None, help="Percorso del file di risultati (opzionale)")
args = parser.parse_args()

FILE_DATI = args.data_file

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

if result == "limit":
    print_out(f"\n--- LIMITE DI TEMPO ({args.time_limit}s) RAGGIUNTO ---")
    try:
        upper_bound = ampl.get_value("Obj_MaxLatency")
        lower_bound = ampl.get_value("Obj_MaxLatency.bestbound")
        print_out(f"Migliore soluzione (Upper Bound): {upper_bound}")
        print_out(f"Migliore lower bound: {lower_bound}")
    except Exception as e:
        print_out(f"Impossibile recuperare i bound: {e}")

if result not in ("solved", "limit"):
    print_out("Nessuna soluzione ottima trovata.")
else:
    print_out(f"\nL_max = {ampl.get_value('Lmax')}")

    print_out("\n--- Installazioni VNF (y_if = 1) ---")
    for (i, f), v in ampl.get_variable("y").get_values().to_dict().items():
        if v > 0.5:
            print_out(f"  VNF {f} installata sul nodo {i}")

    print_out("\n--- Assegnazioni domanda->VNF (z_if^k = 1) ---")
    for (k, i, f), v in ampl.get_variable("z").get_values().to_dict().items():
        if v > 0.5:
            print_out(f"  Domanda {k}: usa VNF {f} sul nodo {i}")

    print_out("\n--- Routing (x_ij^ks = 1) ---")
    for (k, i, j, s), v in ampl.get_variable("x").get_values().to_dict().items():
        if v > 0.5:
            print_out(f"  Domanda {k}, subpath {s}: arco ({i} -> {j})")

    print_out("\n--- Latenza per domanda ---")
    for k, v in ampl.get_variable("L").get_values().to_dict().items():
        print_out(f"  Domanda {k}: L = {v}")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines) + '\n')
