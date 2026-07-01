---
trigger: always_on
---

# Linee Guida per i Commit

Quando generi codice o ti viene richiesto di preparare un commit, devi rispettare rigorosamente le seguenti regole per garantire che la cronologia di Git rimanga pulita, leggibile e atomica.

## 1. Commit Piccoli e Regolari (Atomicità)
- **Una singola responsabilità:** Ogni commit deve riguardare una singola modifica logica (es. l'aggiunta di una funzione, la correzione di un bug o l'aggiornamento della documentazione).
- **Evita commit monolitici:** Non raggruppare modifiche non correlate in un unico grande commit. Se hai modificato più file per motivi diversi, suddividili in commit separati.
- **Frequenza:** Fai commit frequentemente man mano che procedi nello sviluppo per tracciare ogni piccolo passo funzionante.

## 2. Formato dei Messaggi di Commit (Conventional Commits)
Usa sempre il formato standard "Conventional Commits" per i messaggi. La struttura deve essere:
`<tipo>(<scope>): <descrizione breve>`

### Tipi consentiti:
* **feat**: Aggiunta di una nuova funzionalità (feature).
* **fix**: Risoluzione di un bug.
* **docs**: Modifiche esclusive alla documentazione.
* **style**: Modifiche che non alterano la logica del codice (spazi, formattazione, ecc.).
* **refactor**: Modifiche al codice che non correggono bug né aggiungono funzionalità (es. riscrittura per ottimizzazione).
* **test**: Aggiunta o correzione di test.
* **chore**: Aggiornamenti a task di build, configurazioni, dipendenze o strumenti.

### Regole per il corpo del messaggio:
- La `<descrizione breve>` deve essere all'imperativo (es. "add VNF descriptor", non "added VNF descriptor"), iniziare con la lettera minuscola e non terminare con il punto.
- (Opzionale) Aggiungi una riga vuota e poi una descrizione dettagliata se il commit richiede contesto aggiuntivo (perché hai fatto la modifica, cosa risolve).

**Esempi corretti:**
feat(parser): add TOSCA descriptor validation
fix(network): resolve timeout issue on VDU instantiation
docs: update README with deployment steps