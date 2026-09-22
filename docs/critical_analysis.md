# Analisi Critica dei Risultati Computazionali

## 1. Scalabilità — Il modello NON scala

Il problema più evidente: **il modello diventa intrattabile rapidamente**.

| $|D|$ | Modello Max: ottimali | Modello Sum: ottimali | Gap medio (max) | Gap medio (sum) |
|-------|:-----:|:-----:|-----:|-----:|
| 12 | 24/30 (80%) | 15/30 (50%) | ~0.3% | ~36% |
| 24 | 0/11 (0%) | 0/11 (0%) | ~0.7% | ~0.8% |
| 48 | 0/9 (0%) | 0/9 (0%) | ~81% | ~7,400%+ |

> [!CAUTION]
> **Nessuna istanza con $|D| \geq 24$ è stata risolta all'ottimo** in nessuno dei due modelli, entro il time limit di 3600s. Questo limita gravemente l'applicabilità del modello a scenari reali con molti utenti.

**Cosa puoi dire**: Il modello è un MIP con un numero di variabili che cresce come $O(|D| \cdot |A^+| \cdot n)$ per le variabili $x$ e $O(|N|^2 \cdot |A^+| \cdot n)$ per le variabili $w$ di coupling. Questo rende il modello pratico solo per istanze piccole ($|D| \leq 12$). Per istanze più grandi serve un'euristica o una decomposizione.

---

## 2. Max vs Sum — Comportamento opposto per topologia

Questa è forse l'**evidenza più interessante**: i due modelli si comportano in modo **diametralmente opposto** a seconda della topologia.

### Su Mandala ($|D|=12$): **Sum vince nettamente**
| Istanza | Tempo Max | Tempo Sum | Rapporto |
|---------|--------:|--------:|--------:|
| mandala\_12\_inst1\_A | 3410 s | **117 s** | **29×** più lento |
| mandala\_12\_inst1\_D | 3605 s | **138 s** | **26×** più lento |
| mandala\_12\_inst1\_G | 3604 s | **138 s** | **26×** più lento |
| mandala\_12\_balanced\_A | 525 s | **145 s** | 3.6× più lento |

Il modello Sum su Mandala con 12 domande risolve **sempre all'ottimo** (10/10) in media **135 secondi**, mentre Max arriva all'ottimo solo 6/10 volte con tempi medi di **1600 secondi**.

### Su SNDLib (France, Norway, TA1) con $|D|=12$: **Max vince nettamente**
| Istanza | Tempo Max | Tempo Sum | Rapporto |
|---------|--------:|--------:|--------:|
| norway\_12\_1\_A | **739 s** | 3606 s | 5× più veloce |
| norway\_12\_4\_H | **661 s** | 3604 s | 5.5× più veloce |
| ta1\_12\_4\_G | **600 s** | 2686 s | 4.5× più veloce |
| france\_12\_B | **1492 s** | 3603 s | timeout vs ottimo |

Il modello Max sulle reti SNDLib con 12 domande risolve **18/20 istanze all'ottimo**, contro solo **5/20** per Sum.

> [!IMPORTANT]
> **Evidenza chiave**: La topologia gerarchica strutturata di Mandala (EN→CN→BN) favorisce il rilassamento LP del modello Sum, mentre le topologie SNDLib (più piatte, con tutti i nodi che possono eseguire F1/F2/F3) favoriscono il rilassamento LP del modello Max. Questa è una conclusione non banale che meriterebbe una spiegazione teorica.

**Ipotesi**: Su Mandala, la struttura gerarchica rigida con vincoli di compatibilità VNF differenziati ($\alpha$ diversi per livello) riduce lo spazio delle soluzioni in modo compatibile con la funzione obiettivo Sum. Su SNDLib, la maggiore simmetria della rete (quasi tutti i nodi eseguono le stesse VNF) causa degenerazione nel modello Sum, mentre Max rompe la simmetria più efficacemente.

---

## 3. Bilanciamento del Carico AIF — Il Sum **non bilancia**

Il coefficiente di variazione (CV) del carico sui 3 nodi AIF rivela un comportamento preoccupante:

| Rete | CV (Max) | CV (Sum) | Interpretazione |
|------|------:|------:|-----------------|
| Mandala-Bal | 0.50 | **1.12** | Sum molto sbilanciato |
| Mandala-Inst | 0.66 | **1.40** | Sum ancora peggio |
| France | 0.58 | **0.36** | Sum migliore! |
| Norway | 0.62 | **0.50** | Simile |
| TA1 | 0.47 | **0.35** | Sum migliore! |

> [!WARNING]
> **Su Mandala**, il modello Sum tende a **disattivare 1-2 nodi AIF** (in media 1.4 AIF con carico zero su Inst). Questo concentra tutto il traffico su 1-2 nodi BN, il che è **controintuitivo** per una funzione obiettivo che dovrebbe minimizzare la somma totale.
> 
> **Su SNDLib** accade il contrario: il Sum bilancia **meglio** del Max.

**Cosa puoi dire**: Il modello Sum su Mandala preferisce concentrare il traffico per ridurre i costi fissi ($\sigma_f$), pagando il setup di F4 su meno nodi. Il Max invece è costretto a bilanciare perché altrimenti il nodo più carico dominerebbe l'obiettivo.

---

## 4. Istanze Problematiche — Norway è il caso critico

Le istanze con gap più alto sono quasi tutte di **Norway**:

| Istanza | Modello | Gap |
|---------|---------|----:|
| norway\_48\_10\_A | Sum | **∞** (nessun lower bound) |
| norway\_48\_5\_A | Sum | **66,697%** |
| norway\_12\_3\_F | Sum | **389%** |
| norway\_12\_1\_B | Sum | **351%** |
| norway\_12\_1\_A | Sum | **323%** |

Anche il Max su Mandala 48 ha gap molto alti (145-626%).

> [!CAUTION]
> Il gap **infinito** su `norway_48_10_A` (Sum) indica che il solver non è riuscito a trovare un lower bound significativo entro 3600s. Questo suggerisce un **rilassamento LP estremamente debole** per questa combinazione rete/modello/dimensione.

**Cosa puoi dire**: Le configurazioni di delay di Norway (config 1, 3, 5, 10) producono risultati molto eterogenei. Le config 2 e 3 si risolvono bene, mentre la config 1 è patologica. Questo suggerisce che la **struttura dei delay** influenza criticamente la qualità del rilassamento LP.

---

## 5. Mandala Balanced vs Inst — Poca differenza sostanziale

| $|D|$ | Modello | Balanced (opt/tot) | Inst (opt/tot) | Tempo medio Bal | Tempo medio Inst |
|-------|---------|:--:|:--:|------:|------:|
| 12 | Max | 2/2 | 4/8 | 485 s | 2657 s |
| 12 | Sum | 2/2 | 8/8 | 132 s | 138 s |
| 24 | Max | 0/1 | 0/4 | 3607 s | 3607 s |
| 48 | Max | 0/1 | 0/2 | 3614 s | 3614 s |

- Per **Sum con $|D|=12$**: balanced e inst si risolvono entrambi velocemente (~130s), nessuna differenza significativa.
- Per **Max con $|D|=12$**: balanced si risolve sempre (2/2) ma inst solo 4/8. La distribuzione random crea asimmetrie che rendono il Max più difficile.
- Per $|D| \geq 24$: nessuna differenza — entrambi sono al time limit.

**Cosa puoi dire**: La distribuzione bilanciata aiuta marginalmente il modello Max, ma l'effetto è trascurabile rispetto all'impatto della dimensione $|D|$.

---

## 6. Punti di Forza da Evidenziare

1. **Il modello è corretto e implementabile**: tutte le soluzioni ottimali trovate sono consistenti (gap = 0)
2. **$|D|=12$ è generalmente trattabile**: 39/60 istanze risolte all'ottimo tra i due modelli
3. **La scelta dell'obiettivo conta**: Max e Sum hanno performance complementari — si potrebbe proporre un approccio adattivo
4. **I big-M per-funzione funzionano**: i gap su France e TA1 con Sum restano sotto l'1% anche senza ottimalità

## 7. Debolezze e Criticità da Ammettere

1. **Non scala oltre 12 domande**: 0/22 istanze con $|D| \geq 24$ risolte all'ottimo
2. **Gap enormi su Norway**: fino a $\infty$, indicano un modello fondamentalmente inadeguato per certe topologie
3. **Il Sum su Mandala disattiva nodi AIF**: il bilanciamento del carico è pessimo, vanificando l'utilità pratica della funzione di Federated Learning distribuita
4. **Assenza di una euristica di confronto**: non c'è un benchmark con cui confrontare i risultati (euristica greedy, relaxation-based, etc.)
5. **Poche istanze $|D|=48$**: solo 9 per modello, insufficienti per conclusioni statistiche robuste
6. **Il vincolo MaxNodesF4 ≤ 3**: potrebbe essere troppo restrittivo e contribuire ai gap alti su 48 domande

## 8. Suggerimenti per la Tesi

- **Concentra le conclusioni su $|D|=12$** dove hai risultati significativi
- **Evidenzia il dualismo Max/Sum per topologia** come risultato principale
- **Proponi lavoro futuro**: rilassamento lagrangiano, column generation, o euristiche matheuristic per $|D| \geq 24$
- **Discuti il trade-off bilanciamento**: Max bilancia ma è più lento; Sum è veloce (su Mandala) ma concentra il carico
- **Sii onesto sui limiti**: il modello esatto è pratico solo per design-time con pochi utenti, non per planning operativo real-time
