"""
Risolve il modello AMPL (Model Formulation 3) con amplpy.

Installazione richiesta (una tantum):
    pip install amplpy
    python -m amplpy.modules install highs      # solver MILP open-source
"""

from amplpy import AMPL

ampl = AMPL()

#FILE_DATI = "test/vnf_data.dat"
FILE_DATI = "test/test_1.dat"
# = "test/test_2.dat"
#FILE_DATI = "test/test_3.dat"

ampl.read("vnf_model.mod")
ampl.read_data(FILE_DATI)

ampl.option["solver"] = "gurobi"
ampl.solve()

print(f"\n{'='*40}\n ESECUZIONE TEST: {FILE_DATI}\n{'='*40}\n")
result = ampl.get_value("solve_result")
print("solve_result:", result)

if result not in ("solved", "limit"):
    print("Nessuna soluzione ottima trovata.")
else:
    print(f"\nL_max = {ampl.get_value('Lmax')}")

    print("\n--- Installazioni VNF (y_if = 1) ---")
    for (i, f), v in ampl.get_variable("y").get_values().to_dict().items():
        if v > 0.5:
            print(f"  VNF {f} installata sul nodo {i}")

    print("\n--- Assegnazioni domanda->VNF (z_if^k = 1) ---")
    for (k, i, f), v in ampl.get_variable("z").get_values().to_dict().items():
        if v > 0.5:
            print(f"  Domanda {k}: usa VNF {f} sul nodo {i}")

    print("\n--- Routing (x_ij^ks = 1) ---")
    for (k, i, j, s), v in ampl.get_variable("x").get_values().to_dict().items():
        if v > 0.5:
            print(f"  Domanda {k}, subpath {s}: arco ({i} -> {j})")

    print("\n--- Latenza per domanda ---")
    for k, v in ampl.get_variable("L").get_values().to_dict().items():
        print(f"  Domanda {k}: L = {v}")
