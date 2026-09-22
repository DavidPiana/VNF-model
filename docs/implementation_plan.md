# Creazione file dati intermedi per la rete France (SNDLIB)

## Contesto

Creare i file dati intermedi nella cartella `Data/France/` partendo da [SNDLIB_France](file:///c:/Users/annam/OneDrive/Desktop/universita/anno%203/2%20semestre/tesi/VNF-model/Data/France/SNDLIB_France), seguendo una struttura analoga a `DataMedium/` ma adattata a una rete **piatta** (nodo unico, arco unico). Successivamente creare un nuovo builder script che legga questi file intermedi e produca il `.dat` finale per il solver.

Esiste già [generate_france_dat.py](file:///c:/Users/annam/OneDrive/Desktop/universita/anno%203/2%20semestre/tesi/VNF-model/generate_france_dat.py) che genera il `.dat` direttamente senza file intermedi. Il nuovo approccio è **modulare**: file intermedi separati + builder dedicato.

## Decisioni di progetto confermate

| Decisione | Scelta |
|-----------|--------|
| Tipi di nodo | Un solo tipo (`V`), rete piatta |
| Gerarchia (`lv`) | `lv=1` → nodi normali (F1,F2,F3); `lv=2` → nodi speciali (F1,F2,F3,F4) |
| Mapping `c_inv_matr`/`q_inv_matr` | Stessi valori di DataMedium, `[3]` = dummy |
| Nodi speciali F4 | Pre-selezionati: **{N15, N19, N9}** (come nel generatore esistente), vincolo `MaxNodesF4 ≤ 3` resta nel modello |
| Delay | **0.0** per tutti i link (placeholder) |
| Tau (τ) | Invariato: connesso a tutti i nodi N (come nel modello attuale) |
| Domande (D) | Nodi fittizi `ds_*` collegati al nodo sorgente con arco a costo 0, come in DataMedium |
| `p1, p2, p3` | Non utilizzati dal modello, omessi |
| `functions_5G_Core.dat` | Già presente, identico a DataMedium |
| `parameters.dat` | Già presente, identico a DataMedium |

## Open Questions

> [!IMPORTANT]
> **Quali domande usare?** SNDLIB_France contiene **396 domande**. Creare 396 nodi DS fittizi produrrà un'istanza molto pesante per il solver. Come procedere?
> - **Opzione A**: Usare **tutte** le 396 domande (ma il builder supporterà `--num-demands N` per ridurle)
> - **Opzione B**: Filtrare le domande con sorgente = nodo AIF (come fa `generate_france_dat.py`), riducendole
> - **Opzione C**: Usare solo le domande **uniche per sorgente** (max 24, una per nodo non-AIF)
> - **Opzione D**: Altro criterio

> [!IMPORTANT]
> **Valore di `dem[k]`**: usare `tt = 1.65` (uniforme, come in DataMedium) oppure il `demand_value` reale da SNDLIB?

> [!NOTE]
> **Nodi speciali F4**: confermo {N15, N19, N9} come nel generatore esistente?

## Proposed Changes

### File intermedi in `Data/France/`

I file `functions_5G_Core.dat` e `parameters.dat` esistono già e sono identici a DataMedium. Non vanno toccati.

---

#### [MODIFY] [inside_topology_France](file:///c:/Users/annam/OneDrive/Desktop/universita/anno%203/2%20semestre/tesi/VNF-model/Data/France/inside_topology_France)

Attualmente contiene solo `set V`. Completarlo con:
- `set V` — 24 nodi (N1..N24), già presente
- `set A_links` — tutti gli archi dalla sezione LINKS di SNDLIB (coppie sorgente-destinazione)
- `set A_self` — self-loop (Ni, Ni) per ogni nodo (per coerenza col modello, usati da backhauling in DataMedium)
- `set AIF` — nodi speciali {N9, N15, N19}
- `param lv` — `lv=1` per nodi normali, `lv=2` per nodi AIF

---

#### [NEW] [delay_France.dat](file:///c:/Users/annam/OneDrive/Desktop/universita/anno%203/2%20semestre/tesi/VNF-model/Data/France/delay_France.dat)

File unico (niente separazione fronthaul/backhaul):
- `param delay_link` — delay per ogni arco in `A_links` + self-loop → tutto a `0.000` per ora

---

### Builder script

#### [NEW] [build_france_dataset.py](file:///c:/Users/annam/OneDrive/Desktop/universita/anno%203/2%20semestre/tesi/VNF-model/build_france_dataset.py)

Script Python che:
1. Legge `Data/France/inside_topology_France` (nodi, archi, lv, AIF)
2. Legge `Data/France/delay_France.dat` (delay per arco)
3. Legge `Data/France/functions_5G_Core.dat` (parametri F2)
4. Legge `Data/France/parameters.dat` (T_target, tt)
5. Legge `Data/France/SNDLIB_France` (domande)
6. Per ogni domanda selezionata:
   - Crea nodo fittizio `ds_Dx` 
   - Crea arco `(ds_Dx, source_node)` con delay = 0
7. Assembla il tutto in un `.dat` compatibile con `vnf_model.mod`
8. Alpha: `F1=F2=F3=1` per tutti i nodi V; `F4=1` solo per nodi AIF; `alpha=0` per tutti i nodi DS

**CLI**: `python build_france_dataset.py [--num-demands N] [--start-demand M] --out PATH`

## Verification Plan

### Automated Tests
```bash
python build_france_dataset.py --num-demands 10 --out test/france_10.dat
```
Verifica che il `.dat` generato sia caricabile dal solver (parse senza errori).

### Manual Verification
- Controllare che la matrice alpha corrisponda alle regole (F1/F2/F3 ovunque, F4 solo AIF)
- Verificare che i nodi DS siano correttamente collegati
- Verificare che tutti i delay siano 0
