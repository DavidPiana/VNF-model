# VNF-model

Modello di ottimizzazione per il **placement e l'instradamento di Virtual Network Functions (VNF)** su una rete, formulato in AMPL e risolto in Python tramite la libreria [`amplpy`](https://amplpy.ampl.com/).

## Struttura del progetto

```
.
├── vnf_model.mod      # Modello AMPL (Model Formulation 3)
├── solve_vnf.py        # Script Python che carica modello + dati e lancia la risoluzione
└── test/                # Dataset di test (.dat) per validare il modello
    ├── test_1.dat
    ├── test_2.dat
    └── test_3.dat
```

## Requisiti

- Python 3.10 o superiore
- [uv](https://docs.astral.sh/uv/) per la gestione dell'ambiente e delle dipendenze
- Una licenza AMPL (è disponibile una [Community Edition gratuita](https://ampl.com/ce/) sufficiente per modelli di piccole/medie dimensioni)
- Un solver MILP supportato da AMPL: di default lo script usa **Gurobi** (licenza commerciale/accademica richiesta); in alternativa è possibile usare **HiGHS**, open-source e installabile direttamente tramite `amplpy`

## Setup con uv

Dalla root del repository:

```bash
# Installa uv (se non già presente)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Crea pyproject.toml, ambiente virtuale e installa amplpy
uv add amplpy

# Installa il solver open-source HiGHS (facoltativo, se non si usa Gurobi)
uv run python -m amplpy.modules install highs

# (Solo la prima volta) Attiva la licenza AMPL Community/Trial
uv run python -m amplpy.modules activate <license-uuid>
```

## Esecuzione

```bash
uv run python solve_vnf.py
```

Lo script risolve di default il dataset `test/test_1.dat`. Per cambiare dataset, modifica la variabile `FILE_DATI` in `solve_vnf.py` decommentando uno dei percorsi alternativi (`test_2.dat`, `test_3.dat`).

Per usare il solver HiGHS al posto di Gurobi, in `solve_vnf.py` imposta:

```python
ampl.option["solver"] = "highs"
```

## Output

Lo script stampa a video:
- lo stato della soluzione (`solve_result`)
- il valore della latenza massima ottimizzata (`L_max`)
- le installazioni di VNF sui nodi
- le assegnazioni domanda → VNF
- l'instradamento (routing) calcolato per ciascuna domanda
- la latenza per ciascuna domanda


## Installazione e Avvio Rapido

Questo progetto utilizza `uv` per una gestione veloce e riproducibile delle dipendenze.

**1. Installa `uv` (se non l'hai già)**
*(Su Windows: apri PowerShell come amministratore o esegui questo comando)*:
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

**2. Installa le dipendenze**
```bash
uv sync

**3. Esegui lo script**
```bash
uv run python solve_vnf.py test/medium_8.dat --time-limit 120
```