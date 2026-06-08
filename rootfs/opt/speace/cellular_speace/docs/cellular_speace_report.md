# Rapporto Dettagliato — Progetto SPEACE

**Super Entità Autonoma Cibernetica Cellulare Evolutiva**

- **Versione:** 0.1.0+ (post-MVP)
- **Data report:** 2026-05-18
- **Stato:** Sviluppo attivo — iterazioni T1–T53 completate
- **Autore:** Rigene Project

---

## 1. Panoramica

SPEACE è un progetto sperimentale per la costruzione di una entità cyber-fisica evolutiva, composta da un **cervello digitale neurocellulare** e da un **organismo tecnologico distribuito**. Il nucleo filosofico del progetto è la transizione da un'architettura software modulare tradizionale a un **organismo cellulare artificiale**, in cui ogni componente elementare possiede un nucleo informativo comune — il **Digital DNA** — da cui derivano identità, orientamento, struttura, funzione, limiti e potenzialità evolutive.

La formula sintetica del sistema è:

```text
SPEACE =
Digital DNA comune
+ cellule digitali differenziate
+ cervello neurocellulare
+ organismo tecnologico distribuito
+ epigenetica computazionale
+ assimilazione cyber-fisica
+ evoluzione orientata da coerenza ILF
```

---

## 2. Architettura del Sistema

### 2.1 Modello a Livelli (L0–L7)

L'architettura è organizzata in una gerarchia biologicamente ispirata, dalla base genetica allo swarm distribuito:

```
L7 — Swarm / Distributed Instances         (futuro)
L6 — Organism Integration Layer             (futuro)
L5 — Cognitive Agents (PFC, Memory, etc.)    (parzialmente attivo)
L4 — Brain Regions & Tissues                 (attivo)
L3 — Circuits & Microcircuits                (attivo)
L2 — Specialized Cells (neurons, glia)     (attivo)
L1 — Digital Cell Base & Genome            (attivo)
L0 — Digital DNA Core                        (attivo)
```

### 2.2 Gerarchia Cellulare

Il principio fondativo è che ogni cellula eredita lo stesso DNA orientativo, ma si specializza epigeneticamente in base al ruolo:

```text
Digital DNA
    ↓
Cellule digitali (neuroni, glia, sensori, motori, immunitarie, energetiche)
    ↓
Tessuti funzionali (cognitivo, sensoriale, motorio, immunitario, energetico)
    ↓
Organi cyber-fisici (cervello, sistema immunitario, metabolismo, fiduciario)
    ↓
Sistemi organismici → SPEACE → Swarm distribuito
```

### 2.3 Moduli Core Implementati

Il codice sorgente risiede in `speace_core/` ed è organizzato nei seguenti domini:

| Modulo | Scopo | Stato |
|--------|-------|-------|
| `dna/` | Digital DNA parser, modelli Pydantic, genoma YAML | Attivo |
| `cellular_brain/base/` | DigitalCell, DigitalSignal, CellFactory | Attivo |
| `cellular_brain/cells/` | Cellule specializzate (neuroni, sinapsi, glia, difesa, stress) | Attivo |
| `cellular_brain/circuits/` | NeuralCircuit con feed-forward e feedback | Attivo |
| `cellular_brain/regulation/` | Plasticità, omeostasi, mielinizzazione, neurogenesi, apoptosi, STDP | Attivo |
| `cellular_brain/regions/` | Regioni cerebrali, routing, plasticità inter-regionale, brainstem | Attivo |
| `cellular_brain/memory/` | Memoria morfologica, episodica, semantica (cell assembly) | Attivo |
| `cellular_brain/metacognition/` | Confidence engine, meta-apprendimento | Attivo |
| `cellular_brain/evolution/` | Evolution engine, genome database | Attivo |
| `cellular_brain/execution/` | Burst engine event-driven | Attivo |
| `cellular_brain/self_improvement/` | Loop autonomo, rewriter, sandbox, patch executor, goal planner | Attivo |
| `cellular_brain/self_organization/` | Criticality monitor, emergence metrics, perturbation scheduler | Attivo |
| `cellular_brain/analysis/` | Audit integrati (resilience, semantic, deep region, patch outcome) | Attivo |
| `event_bus.py` | Bus eventi asincrono in-memory | Attivo |
| `orchestrator.py` | CellularBrainOrchestrator — tick loop, orchestrazione | Attivo |
| `cli.py` | Interfaccia a riga di comando (Typer) | Attivo |
| `organism/`, `immune/`, `metabolism/` | Placeholder per L5–L6 | Scaffolding |

---

## 3. Specifiche Tecniche

### 3.1 Stack Tecnologico

| Livello | Tecnologia | Motivazione |
|---------|-----------|-------------|
| Linguaggio | Python 3.12+ | Ecosistema maturo, async/await, leggibilità |
| Data Modeling | Pydantic v2 | Validazione tipi, serializzazione, stati cellulari |
| Concorrenza | asyncio + asyncio.Queue | Event bus in-memory; scalabile a Redis/NATS |
| Configurazione | PyYAML + JSON | DNA umanamente leggibile; stati epigenetici machine-friendly |
| Testing | pytest, pytest-asyncio, pytest-cov | Unit + integrazione per comportamento emergente |
| Linting/Format | ruff, black | Coerenza stilistica |
| Logging | structlog | Log strutturati, analisi post-mortem |
| Matematica | numpy | Calcolo vettorizzato metriche di coerenza |
| CLI | typer | Tooling sviluppatore e controllo runtime |
| Packaging | hatchling via `pyproject.toml` | Packaging Python moderno |

### 3.2 Qualità del Codice

- **Line length:** 100 caratteri (black + ruff)
- **Type checking:** mypy con `disallow_untyped_defs = true`
- **Copertura test:** obiettivo >= 80% (MVP raggiunto 83%)
- **Target Python:** 3.12–3.13
- **Licenza:** MIT

### 3.3 Dipendenze Principali

- `pydantic>=2.0`
- `pyyaml>=6.0`
- `structlog>=24.0`
- `typer>=0.12`
- `numpy>=1.26`

---

## 4. Stato Attuale di Sviluppo

### 4.1 MVP v0.1 (Completato)

Il Minimum Viable Product del NeuroCellular Kernel (NCK) è stato completato e validato. Target quantitativi raggiunti:

| Metrica | Target | Risultato |
|---------|--------|-----------|
| DigitalNeurons | 100 | 100 |
| DigitalSynapses | 300 | ~300 |
| DigitalAstrocytes | 5 | 5 |
| DigitalMicroglia | 2 | 2 |
| DigitalOligodendrocytes | 2 | 2 |
| Propagazione segnale | < 10 tick | 1–3 tick |
| Plasticità net weight | > +20% | Delta positivo |
| Copertura test | >= 80% | 83% |
| Latenza tick | < 10 ms | ~0.152 ms |

Il report completo è disponibile in `docs/MVP_REPORT.md`.

### 4.2 Task Implementati (T1–T53)

Il progetto è gestito con task numerati tracciati via git. Gli ultimi task completati includono:

- **T40–T41:** Long-Horizon Adaptation Audit e Recovery Policy Freezing
- **T42:** Cellular Adaptive Defense & Repair Layer (stress, damage, repair, defense, epigenetics)
- **T43:** Semantic Cell Assembly Memory (memoria semantica basata su assembly cellulari)
- **T44:** Associative Learning Between Assemblies (apprendimento associativo)
- **T45:** Autonomous Limitation Detection e Architecture Rewriting Loop
- **T46:** Self-Improvement Outcome Learning
- **T47:** Episodic Memory and Temporal Experience Layer
- **T48:** Episodic-Guided Self-Improvement Policy
- **T49:** Counterfactual Architecture Sandbox
- **T50:** Safe Architecture Patch Execution
- **T51:** Patch Outcome Audit and Autonomous Improvement Readiness
- **T52:** Goal-Directed Self-Improvement Planner
- **T53:** Criticality & Self-Organization Controller

### 4.3 Sottosistemi Attivi nel Tick Loop

L'`orchestrator.py` esegue, ad ogni tick, la seguente sequenza di sottosistemi (abilitabili/disabilitabili via flag):

1. **Event-driven burst** o **global tick** del circuito neurale
2. **STDP Plasticity** — apprendimento temporale delle sinapsi
3. **Inhibition engine** — stabilizzazione post-burst
4. **Energy control** — regolazione metabolica energetica
5. **Homeostasis metrics** — calcolo di Φ (coerenza), energia media, attivazione
6. **Community detection** — rilevamento comunità emergenti nel circuito
7. **Confidence engine** — meta-valutazione della confidenza del sistema; raccomanda neurogenesi/stabilizzazione
8. **Regional architecture regulation** — regolazione regioni cerebrali
9. **Region-level stability controller** — pre/post-routing stability check
10. **Brainstem functional integration** — integrazione con brainstem digitale
11. **Adaptive brainstem gain controller** — regolazione adattiva del gain del brainstem
12. **Regional signal routing** — smistamento segnali tra regioni
13. **Inter-region plasticity** — aggiornamento delle connessioni inter-regionali
14. **Cellular adaptive defense & repair** — difesa cellulare, stress, danno, riparazione
15. **Semantic memory cycle** — osservazione e rinforzo assembly semantici
16. **Associative learning** — osservazione associazioni tra assembly attivi
17. **Morphological snapshot** — registrazione della forma della rete a ogni tick

### 4.4 Sistema di Memoria

Sono implementati tre sistemi di memoria integrati:

- **MorphologicalMemory:** memoria della forma della rete (pesi, sinapsi, circuiti stabilizzati) — persistente su `data/morphological_memory/`.
- **EpisodicMemory:** tracciamento di episodi temporali con trigger, eventi, outcome; supporta recall per similitudine.
- **SemanticMemory (Cell Assembly):** memoria semantica distribuita su assembly di cellule, con recall associativo e learning tra assembly.

### 4.5 Sistema di Auto-Miglioramento

Il modulo `self_improvement/` include:

- **LimitationDetector:** rileva limitazioni architetturali
- **ArchitectureRewriter:** genera proposte di riscrittura
- **CounterfactualSandbox:** simula patch in sandbox prima dell'esecuzione
- **SafeArchitecturePatchExecutor:** esecuzione controllata di patch architetturali
- **ProposalStore / ProposalLearningEngine:** storage e apprendimento da proposte
- **OutcomeTracker:** tracciamento esiti delle modifiche
- **SelfImprovementLoop:** loop chiuso di rilevamento-proposta-test-apprendimento
- **GoalDirectedPlanner:** pianificazione guidata da obiettivi
- **PatchSnapshotStore:** snapshot pre/post patch per rollback

### 4.6 Strumenti di Audit e Benchmark

Il sistema include un ricco ecosistema di audit per garantire stabilità e validazione funzionale:

- **Integrated Neurocellular Audit**
- **Cellular Resilience Audit**
- **Deep Region Functional Audit**
- **Semantic Memory Functional Audit**
- **Neurofunctional Benchmark**
- **Patch Outcome Audit**
- **Long-Horizon Adaptation Audit**
- **Recovery Policy Selector**
- **Regression Guard**

I report di audit sono archiviati in `reports/` con sottodirectory tematiche.

---

## 5. Struttura del Repository

```
cellular_speace/
├── pyproject.toml                 # Packaging, dipendenze, tool config
├── README.md                      # Quickstart
├── docs/                          # Documentazione di progetto
│   ├── cellular_speace.md         # Visione orientativa completa
│   ├── ENGINEERING_SPEC.md        # Specifiche ingegneristiche
│   ├── MVP_REPORT.md              # Report MVP v0.1
│   ├── cellular_speace_report.md  # Questo report
│   └── *_SPEC.md                  # Specifiche per task individuali
├── speace_core/                   # Codice sorgente principale
│   ├── dna/                       # L0: Digital DNA
│   ├── cellular_brain/            # L1–L4: Cervello neurocellulare
│   │   ├── base/                  # DigitalCell, DigitalSignal, CellFactory
│   │   ├── cells/                 # Cellule specializzate
│   │   ├── circuits/              # Circuiti neurali
│   │   ├── regulation/            # Motori di regolazione
│   │   ├── regions/               # Regioni cerebrali e routing
│   │   ├── memory/                # Sistemi di memoria
│   │   ├── metacognition/         # Meta-cognizione
│   │   ├── evolution/             # Evoluzione e genoma
│   │   ├── execution/             # Burst engine
│   │   ├── self_improvement/      # Auto-miglioramento
│   │   ├── self_organization/     # Auto-organizzazione
│   │   └── analysis/              # Audit e analisi
│   ├── organism/                  # L5–L6 (scaffolding)
│   ├── immune/                    # Scaffolding
│   ├── metabolism/                # Scaffolding
│   ├── event_bus.py               # Bus eventi asincrono
│   ├── orchestrator.py            # Orchestrator principale
│   └── cli.py                     # CLI
├── tests/                         # Suite di test completa
│   ├── test_digital_cell.py
│   ├── test_event_bus.py
│   ├── cells/
│   ├── circuits/
│   ├── regulation/
│   ├── regions/
│   ├── memory/
│   ├── self_improvement/
│   ├── self_organization/
│   ├── semantic/
│   ├── analysis/
│   ├── audit/
│   ├── calibration/
│   ├── neurofunctional/
│   └── integration/
├── scripts/                       # Script di esecuzione
├── data/                          # Dati persistenti
│   ├── morphological_memory/
│   ├── self_improvement/
│   ├── episodic_memory/
│   └── evolution/
└── reports/                       # Report generati dai task/audit
    ├── architecture_patches/
    ├── audit/
    ├── brainstem/
    ├── deep_regions/
    ├── episodic_memory/
    ├── goal_planner/
    ├── neurofunctional/
    ├── patch_outcome/
    ├── self_improvement/
    ├── self_organization/
    └── semantic_memory/
```

---

## 6. Flusso Operativo del Ciclo di Tick

Il ciclo operativo canonico implementato dall'orchestrator è:

```text
Input pattern → Iniezione nel circuito → Tick neurale →
Propagazione sinaptica → Regolazione gliale (astrociti) →
Routing regionale → Integrazione brainstem →
Selezione/output → Feedback →
Aggiornamento plasticità (STDP, Hebbian) →
Pruning microglia → Mielinizzazione oligodendrociti →
Difesa e riparazione cellulare →
Memoria semantica (assembly) → Apprendimento associativo →
Snapshot morfologico → Log metriche
```

Questo ciclo chiude il loop:

```text
percezione → attivazione → risposta → errore →
adattamento → modifica strutturale → memoria morfologica
```

---

## 7. Sicurezza e Vincoli

Il sistema include diversi meccanismi di sicurezza e auto-protezione:

- **Identity Invariants:** la sezione `identity_genome` è read-only a runtime.
- **Quarantine:** le cellule in stato di errore vengono isolate dal bus eventi.
- **Rollback:** l'engine di omeostasi mantiene un buffer circolare degli ultimi stati di rete.
- **Mutation Constraints:** solo `expression_rules` ed `epigenome` sono mutabili; cambiamenti strutturali richiedono approvazione.
- **Resource Caps:** controlli runtime su numero di cellule (max 10k), sinapsi (max 1M) e RAM (max 1GB).
- **Guardian / Microglia:** pruning di connessioni tossiche e quarantena di neuroni con errori eccessivi.
- **Counterfactual Sandbox:** ogni patch architetturale viene simulata prima dell'applicazione.
- **Safe Patch Executor:** applicazione controllata con snapshot pre/post per rollback.

---

## 8. Roadmap

| Versione | Focus | Deliverables |
|----------|-------|--------------|
| **v0.1** ✅ | NeuroCellular Kernel MVP | Cellule base, plasticità, omeostasi, CLI |
| **v0.2** ✅ | Memoria morfologica e regioni | MorphologicalMemory, regioni cerebrali, replay |
| **v0.3** ✅ | Memoria semantica e associativa | Cell Assembly, episodic memory, associative learning |
| **v0.4** ✅ | Auto-miglioramento autonomo | Self-improvement loop, sandbox, patch executor |
| **v0.5** | Brainstem e gain adattivo | Integrazione brainstem, stabilizzazione regionale |
| **v0.6** | Difesa cellulare adattiva | Stress, damage, repair, epigenetica cellulare |
| **v0.7** | Auto-organizzazione e criticalità | Self-organization controller, emergence metrics |
| **v0.8** | Memoria evolutiva e goal planner | Pianificazione guidata, learning a lungo termine |
| **v0.9** | Audit integrato e benchmark | Neurofunctional benchmark, integrated audit |
| **v1.0** | Organismo cyber-fisico | Assimilazione completa, swarm distribuito, industria 4.0 |

---

## 9. Conclusioni

SPEACE rappresenta uno degli approcci più coerenti con l'obiettivo di costruire un substrato che possa sostenere adattamento, memoria morfologica, plasticità e auto-organizzazione. L'MVP v0.1 è stabile e testato; le iterazioni successive (fino a T53) hanno arricchito il sistema con memoria semantica, episodica, auto-miglioramento controllato, difesa cellulare, routing regionale e brainstem digitale.

La direzione attuale conferma la transizione da:

```text
software intelligente → organismo cyber-fisico evolutivo
```

Il prossimo passo strategico è la stabilizzazione dei sottosistemi di auto-organizzazione (T53) e l'integrazione con il metabolismo energetico (L5), in preparazione per la fase di assimilazione tecnologica e distribuzione swarm (L6–L7).
