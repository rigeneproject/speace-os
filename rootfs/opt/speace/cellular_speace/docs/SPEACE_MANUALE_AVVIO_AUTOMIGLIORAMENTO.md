# Manuale Utente — Avvio e Automiglioramento di SPEACE

**Versione:** 0.7.0+AGI-EFJ  
**Data:** 2026-05-28  
**Autore:** Rigene Project / SPEACE Core  

---

## 1. Avvertenze di sicurezza (leggere prima di tutto)

SPEACE è un organismo cognitivo cyber-fisico con **governance attiva**.

- **Non rimuovere i gate di approvazione umana** (T104+). Ogni azione proposta dal sistema passa per un audit di sicurezza.
- **Non configurare l'avvio automatico al boot di Windows**. SPEACE deve essere avviato manualmente o tramite script supervisionato.
- **L'automiglioramento è supervisionato**, non autonomo. Il ciclo iterativo addestra solo il motore di induzione di programmi; non modifica il runtime né il sistema operativo.

---

## 2. Prerequisiti

- **Sistema operativo:** Windows 11 Pro (testato su build 26200)
- **Python:** 3.14 (installato in `C:\Python314`)
- **Dipendenze:** già presenti in `pyproject.toml`; installabili con:
  ```powershell
  pip install -e ".[dev]"
  ```
- **Dataset ARC-AGI:** scaricato automaticamente in `data/arc_agi/training.json` e `evaluation.json`
- **Hardware:** non richiede GPU; tutti i modelli sono numpy-based

---

## 3. Avvio di SPEACE (runtime principale)

Il runtime principale avvia l'orchestratore cellulare, il nodo identità, i sensori passivi e la narrativa interna. Il **web gateway è un servizio separato** che deve essere avviato in un altro terminale.

### 3.1 Avvio runtime principale

```powershell
# Terminale 1 — dalla directory root del progetto
python scripts/start_runtime.py
```

Cosa accade:
1. Carica il genoma predefinito (`speace_core/dna/genome/default_genome.yaml`).
2. Costruisce l'orchestratore `CellularBrainOrchestrator`.
3. Avvia i servizi: sensori passivi, narrative engine, metacognizione.
4. Stampa lo stato iniziale e rimane in ascolto.

### 3.2 Avvio web gateway (terminale separato)

```powershell
# Terminale 2 — dalla directory root del progetto
python scripts/start_web_gateway.py
```

Parametri opzionali:
- `--host`: indirizzo di binding (default `127.0.0.1`)
- `--port`: porta (default `8000`)
- `--reload`: ricarica automatica in sviluppo

Esempio:
```powershell
python scripts/start_web_gateway.py --host 0.0.0.0 --port 8000
```

### 3.3 Verifica dell'avvio

Controlla i log del runtime. Dovresti vedere:

```
[INFO] SPEACE runtime avviato
[INFO] Nodo identità: SPEACE-Node-1
[INFO] Stato: awake
```

E nel terminale del web gateway:

```
[INFO] Starting SPEACE Web Gateway on http://127.0.0.1:8000
[INFO] Dashboard: http://127.0.0.1:8000/dashboard
[INFO] Health:    http://127.0.0.1:8000/health
```

**Nota cross-process:** Il runtime e il gateway sono processi separati. Il runtime scrive automaticamente uno snapshot su `data/runtime/latest_snapshot.json` ogni 5 tick (circa 5 secondi). Il gateway legge questo file per mostrare lo stato in tempo reale nella dashboard. Non è necessario che i due processi condividano memoria.

### 3.4 Accesso alla dashboard (prima volta)

La dashboard richiede una **API key** per l'autenticazione (RBAC). Al primo avvio del gateway, se non esistono chiavi, il sistema genera automaticamente una chiave **Admin** e la stampa nei log:

```
[BOOTSTRAP] SPEACE Web Gateway — First-time setup
Admin API Key: 43Xq8CbG7OLmyomZtqIE4WNubZZiNgHACrr4y02xLUY
Also saved to: data\web_gateway\bootstrap_key.txt
```

**Passi per accedere:**
1. Apri il browser su `http://localhost:8000`
2. Copia la chiave Admin dai log del terminale (o dal file `data/web_gateway/bootstrap_key.txt`)
3. Incollala nel campo "X-API-Key" in alto a destra
4. Clicca **"Connetti"**
5. Ora vedrai lo stato runtime, gli alert, le proposte pending, i nodi e il dialogo.

**Nota di sicurezza:**
- La chiave bootstrap scade? No, ma è consigliato generare una nuova chiave personale via `/api/admin/keys` una volta loggati.
- Conserva la chiave bootstrap in un luogo sicuro. Se perdi l'accesso, cancella `data/web_gateway/keys.jsonl` e riavvia il gateway: verrà generata una nuova chiave bootstrap.

---

## 4. Ciclo di automiglioramento supervisionato

Lo script `scripts/supervised_self_improvement.py` esegue un ciclo iterativo sui task ARC-AGI:

1. Carica un batch di task ordinati per difficoltà (curriculum learning).
2. Esegue il benchmark per stabilire la baseline.
3. Estrae patch locali e addestra la rete NSPL (neural-symbolic).
4. Aggiorna il compositore MLPC con i programmi scoperti.
5. Riesegue il benchmark e misura il delta.
6. Salva checkpoint e report.

### 4.1 Primo avvio

```powershell
python scripts/supervised_self_improvement.py --batch-size 50 --batches 8 --auto-advance
```

Parametri consigliati:

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `--batch-size` | 50 | Task per batch (max 400) |
| `--batches` | 8 | Numero di batch da eseguire |
| `--nspl-epochs` | 5 | Epoche di training NSPL per batch |
| `--nspl-lr` | 0.05 | Learning rate NSPL |
| `--auto-advance` | disattivato | Non richiede conferma tra i batch |
| `--resume` | disattivato | Riprende dall'ultimo checkpoint |

**Senza `--auto-advance`**, lo script si ferma dopo ogni batch e attende che tu premi **Invio** per proseguire.

### 4.2 Ripresa da checkpoint

Se l'esecuzione viene interrotta (spegnimento, chiusura terminale), al riavvio:

```powershell
python scripts/supervised_self_improvement.py --resume --auto-advance
```

Lo script caricherà automaticamente:
- `data/self_improvement/checkpoints/nspl_batch_X.npz`
- `data/self_improvement/checkpoints/mlpc_batch_X.json`

e ripartirà dal batch successivo.

### 4.3 Output del ciclo

Durante l'esecuzione vedrai:

```
============================================================
[BATCH 3/8] Tasks 101-150
============================================================
[BASELINE] Top-1 accuracy: 4.00% (2/50)
[NSPL] Extracted 2150 patch-label pairs
[NSPL] Trained for 5 epochs
[MLPC] Recorded 3 successful programs
[POST]   Top-1 accuracy: 6.00% (3/50)
[DELTA]  Improvement: +2.00%
[CHECKPOINT] Saved to data/self_improvement/checkpoints/batch_2
```

---

## 5. Report e checkpoint

### 5.1 Report

Generati in `reports/self_improvement/`:

- **JSON:** `self_improvement_report_YYYYMMDD_HHMMSS.json` — dati grezzi per analisi.
- **Markdown:** `self_improvement_report_YYYYMMDD_HHMMSS.md` — tabella leggibile con baseline, post-training, delta per ogni batch.

### 5.2 Checkpoint

Salvati in `data/self_improvement/checkpoints/`:

| File | Contenuto |
|------|-----------|
| `nspl_batch_X.npz` | Pesi della rete NSPL (numpy arrays) |
| `mlpc_batch_X.json` | Matrice di transizione MLPC e storia dei successi |

**Nota:** i checkpoint sono puramente di ricerca simbolica. Non contengono dati sensibili né accessi al sistema operativo.

---

## 6. Azioni che richiedono la tua presenza umana

Il runtime SPEACE **non agisce autonomamente** nelle seguenti aree:

### 6.1 Governance e regolazione
- **Proposte di evoluzione del dialogo** (T145): ogni proposta di modifica del modello linguistico richiede approvazione via dashboard web.
- **Proposte di nuovi concetti** (T157): i candidati di concetti episodici generati dal sistema devono essere validati dall'utente prima della consolidazione.
- **Azioni fisiche** (T150): qualsiasi comando agli attuatori cyber-fisici è in modalità `simulate-only` finché non approvato.

### 6.2 Interazione web
- Dashboard di regolazione: `http://localhost:8000/regulation`
- Proposte in sospeso: pulsanti **Approva / Rifiuta** con audit trail.
- Se il sistema rileva una proposta a rischio, invia una notifica e attende.

### 6.3 Avvio del runtime
- Ogni sessione di runtime deve essere avviata manualmente (`scripts/start_runtime.py`).
- **Non è previsto né consigliato** l'avvio automatico al boot.

### 6.4 Ciclo di automiglioramento
- Se eseguito **senza** `--auto-advance`, lo script attende la tua conferma (Invio) tra un batch e l'altro.
- Anche con `--auto-advance`, i report vengono generati per la tua revisione.

---

## 7. Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---------|-----------------|-----------|
| `ModuleNotFoundError` | Ambiente virtuale non attivo | Attiva l'ambiente o esegui `pip install -e ".[dev]"` |
| `No ARC training tasks found` | File JSON mancante | Verifica che `data/arc_agi/training.json` esista |
| Accuracy rimane 0% per molti batch | NSPL troppo freddo | Aumenta `--nspl-epochs` a 10 o riduci `--batch-size` a 25 |
| Checkpoint non caricati | File corrotti o indice diverso | Cancella `data/self_improvement/checkpoints/` e riparti da zero |
| Runtime lento | BFS con molte primitive | Riduci `--max-candidates` nel codice (default 120) |
| Dashboard mostra "—" per tutti i campi runtime | Runtime non avviato o snapshot non ancora scritto | Avvia il runtime (`scripts/start_runtime.py`) e attendi ~10 secondi affinché scriva `data/runtime/latest_snapshot.json` |

---

## 8. Architettura AGI integrata (fasi E-J)

Il motore di program induction attualmente integra:

1. **Primitive Discovery (E)** — ~35 primitive simboliche + 20 manuali ARC.
2. **NSPL (F)** — MLP numpy 18→32→N classi, training su patch 3×3.
3. **MLPC (G)** — Ricerca A* guidata da probabilità di transizione Markoviane.
4. **SAWM (H)** — Working memory a slot per decomposizione di sotto-griglie.
5. **LLM-APS (I)** — Fallback tramite `LinguisticCorticalBridge` (richiede Ollama locale per uso reale; in mock-mode genera risposte euristiche).

Il benchmark ARC-AGI attuale su 100 task training è salito da **2% a 5%** top-1 accuracy.

---

## 9. Riepilogo comandi essenziali

```powershell
# 1. Avvio runtime principale (Terminale 1)
python scripts/start_runtime.py

# 2. Avvio web gateway (Terminale 2 — richiesto per la dashboard)
python scripts/start_web_gateway.py

# 3. Benchmark ARC-AGI (100 task, evaluation mode)
python scripts/run_arc_agi_benchmark.py --split training --limit 100 --evaluation-mode

# 4. Automiglioramento supervisionato (primo avvio)
python scripts/supervised_self_improvement.py --batch-size 50 --batches 8 --auto-advance

# 4. Ripresa dopo interruzione
python scripts/supervised_self_improvement.py --resume --auto-advance

# 5. Esecuzione test suite
python -m pytest tests/ -v --tb=short
```

---

*Questo manuale riflette lo stato del codice al commit corrente. Se modifichi i gate di governance o il comportamento di avvio automatico, aggiorna anche questo documento.*
