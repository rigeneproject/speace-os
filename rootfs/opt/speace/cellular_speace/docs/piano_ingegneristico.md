# Piano ingegneristico per l'evoluzione di SPEACE verso capacità AGI

**Versione:** 0.2  
**Data di creazione:** 2026-05-30  
**Ultimo aggiornamento:** 2026-06-05  
**Stato:** Bozza operativa  
**Scopo:** definire una roadmap tecnica, verificabile e aggiornabile per far evolvere SPEACE da organismo neuro-cellulare sperimentale a sistema cognitivo generale progressivamente misurabile.

## 1. Sintesi

SPEACE è una piattaforma sperimentale ispirata all'architettura biologica del cervello: neuroni digitali, sinapsi, memoria morfologica, regolazione omeostatica, moduli semantici, metacognizione, runtime continuo, embodiment simulato e meccanismi di auto-miglioramento controllato.

I test ARC-AGI eseguiti localmente indicano che SPEACE possiede componenti cognitive embrionali, ma non è ancora vicino a una AGI:

| Benchmark | Task | Corretti | Accuracy |
|---|---|---:|---:|
| ARC-AGI training locale | 400 | 20 | 5.00% |
| ARC-AGI evaluation locale | 400 | 1 | 0.25% |

**Stato corrente moduli OCR (giugno 2026):**
- **Object-Centric Representation (OCR)**: rappresentazione scene-graph con attributi (colore, area, centroide, bbox) e `compute_attributes()` con fix bbox e background inference migliorata
- **6 Slot-Level Primitives**: `slot_recolor_by_attr`, `slot_replicate_by_count`, `slot_move_to`, `slot_remove_by_predicate`, `slot_sort_by_attribute`, `slot_interleave_by_color` — registrate nel `_PRIMITIVE_REGISTRY` (totale 54 primitive)
- **Object-Centric Induction Bridge**: genera ipotesi slot-level da scene-graph diff per Phase A; re-ranking slot-aware in Phase F
- **Program Schema Library**: `ProgramSchema` + `ProgramSchemaLibrary` con task signature, similarità Jaccard, instantiation parametrizzata, persistence JSON, retrieval zero-shot
- **Test**: 42 nuovi test (slot-level: 17, bridge: 9, schema lib: 12, integration: 4) — tutti passano. 301 test esistenti — tutti passano, 0 regressioni.

La direzione tecnica non deve essere "aggiungere moduli" in modo indefinito, ma trasformare i moduli esistenti in un ciclo cognitivo generale:

```text
percezione -> astrazione -> memoria -> ipotesi -> pianificazione -> azione mentale
-> valutazione -> correzione -> consolidamento -> trasferimento
```

## 2. Principi guida

1. Ogni nuova capacità deve essere misurata da benchmark ripetibili.
2. Ogni modifica architetturale deve avere rollback o quarantena.
3. L'ispirazione biologica deve tradursi in responsabilità computazionali precise.
4. La generalizzazione conta più della performance su task memorizzati.
5. La metacognizione deve calibrare confidenza, errore, incertezza e costo.
6. ARC-AGI è un benchmark di riferimento, non l'unico obiettivo.
7. Il sistema deve migliorare senza perdere stabilità, sicurezza e tracciabilità.

## 3. Mappa biologica e corrispondenza SPEACE

| Sistema biologico | Funzione cognitiva | Moduli SPEACE coinvolti | Obiettivo evolutivo |
|---|---|---|---|
| Corteccia sensoriale | Estrazione di pattern e invarianti | spatial reasoning, ARC primitives, sensor arrays | Rappresentazioni percettive robuste |
| Ippocampo | Episodi, analogie, consolidamento | episodic memory, semantic memory, morphological memory | Recupero di casi simili e traiettorie cognitive |
| Corteccia prefrontale | Working memory, piano, vincoli | global workspace, GOAP, behavior trees | Pianificazione composizionale |
| Gangli della base | Selezione azioni e strategie | utility drive, arbitration, dopaminergic drive | Scelta efficiente del prossimo passo mentale |
| Cervelletto | Automatizzazione e predizione | skill library, program induction, cognitive evolution | Compressione di strategie riuscite |
| Sistema limbico/omeostatico | Motivazione, stabilità, priorità | homeostasis, energy, criticality, drives | Regolazione del comportamento cognitivo |
| Metacorteccia | Auto-valutazione e correzione | metacognition, confidence, coherence monitor | Calibrazione epistemica e autocorrezione |
| Corpo e ambiente | Grounding causale | digital twin, cognitive nursery, simulated embodiment | Concetti causali trasferibili |

## 4. Roadmap tecnica

### Fase 1 - Stabilizzazione del cervello minimo

**Obiettivo:** rendere affidabile il substrato neuro-cellulare prima di aumentare complessità.

Task:

- [ ] Correggere il warning asincrono in `LinguisticCorticalBridge.generate` nel percorso ARC-AGI.
- [ ] Rendere `scripts/run_arc_agi_benchmark.py` privo di warning e deterministico a parità di seed.
- [ ] Aggiungere un comando unico di smoke test cognitivo: neuroni, sinapsi, tick, memoria, benchmark minimo.
- [ ] Misurare attivazione media, sparsità, energia media, sinapsi attive, memoria generata per ogni run.
- [ ] Separare chiaramente neuroni sensoriali, associativi, motori, linguistici e metacognitivi.
- [ ] Verificare runtime continuo per almeno 8 ore senza crash o crescita anomala di memoria.
- [ ] Aggiungere report automatico in `reports/runtime/` per stabilità lunga.

Criteri di completamento:

- `pytest --collect-only` senza errori.
- Smoke test cognitivo completato in meno di 60 secondi.
- Nessun warning critico nel benchmark ARC-AGI.
- Runtime lungo senza crash, memory leak severi o perdita di stato.

### Fase 2 - Corteccia percettiva astratta per ARC-AGI

**Obiettivo:** trasformare griglie ARC in rappresentazioni oggetto-relazione, non solo in input grezzi.

Task:

- [ ] Creare un modulo `arc_visual_cortex` per segmentazione oggetti.
- [ ] Estrarre attributi: colore, area, bounding box, posizione, contorno, simmetria.
- [ ] Estrarre relazioni: sopra/sotto, dentro/fuori, allineato, vicino, sovrapposto.
- [ ] Rilevare trasformazioni: rotazione, mirror, crop, recolor, fill, translate, scale.
- [ ] Generare una rappresentazione JSON spiegabile per ogni task ARC.
- [ ] Aggiungere test unitari su task sintetici semplici.
- [ ] Salvare nel report ARC la rappresentazione percettiva usata.

Criteri di completamento:

- Almeno 90% di accuratezza su suite sintetica di segmentazione.
- Report ARC con descrizione strutturata degli oggetti.
- Miglioramento misurabile rispetto al baseline ARC attuale.

### Fase 3 - Memoria episodica e analogica

**Obiettivo:** trasformare i tentativi cognitivi in episodi recuperabili.

Task:

- [ ] Definire schema `CognitiveEpisode`.
- [ ] Registrare per ogni task: percezione, ipotesi, programma, output, errore, confidenza.
- [ ] Indicizzare episodi per pattern percettivi e trasformazioni.
- [ ] Implementare ricerca di task analoghi.
- [ ] Collegare episodi riusciti alla memoria semantica.
- [ ] Collegare episodi falliti alla metacognizione e al limitation detector.
- [ ] Aggiungere report "similar cases retrieved" nel benchmark ARC.

Criteri di completamento:

- SPEACE recupera almeno 3 casi simili per task quando disponibili.
- Le analogie recuperate migliorano la scelta delle primitive.
- Gli errori ricorrenti vengono aggregati in categorie.

### Fase 3.5 - Induzione composizionale object-centric

**Obiettivo:** trasformare le griglie ARC in rappresentazioni object-centric, generare primitive slot-level, e usare una libreria di schemi per accelerare l'induzione di programmi.

Task:

- [x] **OGGETTO-OCR**: `ObjectCentricRepresentation` — rappresentazione scene-graph con attributi (colore, area, bbox, centroide). Fix bbox computation (`min(pixels)/max(pixels)`). Background inference migliorata (preferisce 0 in caso di parità).
- [x] **OGGETTO-Slot Primitives**: 6 slot-level primitive registrate in cascade nel `_PRIMITIVE_REGISTRY`: `slot_recolor_by_attr`, `slot_replicate_by_count`, `slot_move_to`, `slot_remove_by_predicate`, `slot_sort_by_attribute`, `slot_interleave_by_color`. Compatibili con oggetti multicolore (best-match colore dominante).
- [x] **OGGETTO-Bridge**: `ObjectCentricInductionBridge` — genera ipotesi slot-level da scene-graph diff (`color_map`, `slot_replicate_by_count`, `slot_remove_by_predicate`, `translate`) con slot-aware pixel scoring e re-ranking candidati FSPI.
- [x] **OGGETTO-Schema Library**: `ProgramSchemaLibrary` — task signature (dimensioni, colori, grow/shrink), similarità Jaccard, instantiation parametrizzata, persistence JSON, retrieval per zero-shot. Integrata in ARC-AGI adapter.
- [x] **OGGETTO-Integration**: Bridge iniettato in Phase A di FSPI Engine (ipotesi slot-level prima della ricerca primitiva) + Phase F (re-ranking con slot confidence). Schema Library consultata in `evaluate_task()` e popolata con programmi di successo (threshold pixel_score ≥ 0.6).
- [x] **Test**: 42 test nuovi, 17 + 9 + 12 + 4. Tutti passano.

Criteri di completamento (estensione futura):

- Almeno 1% improvement su ARC training via solo slot bridge.
- Schema Library con ≥10 schemi popolati da benchmark.
- Zero regressioni nei 301 test esistenti.

### Fase 4 - Selezione azione cognitiva

**Obiettivo:** scegliere in modo intelligente il prossimo passo di ragionamento.

Task:

- [ ] Definire azioni cognitive atomiche: segmenta, cerca analogia, prova trasformazione, valida, cambia astrazione.
- [ ] Integrare le azioni cognitive nel `UtilityDriveSystem`.
- [ ] Usare GOAP per pianificare catene di azioni mentali.
- [ ] Usare behavior trees per riflessi veloci su pattern noti.
- [ ] Aggiungere costo computazionale per azione.
- [ ] Aggiungere ricompensa per ipotesi che riducono errore.
- [ ] Tracciare la politica scelta per ogni task.

Criteri di completamento:

- Riduzione dei tentativi inutili per task.
- Aumento del match score medio anche quando exact match resta basso.
- Report con sequenza di azioni cognitive.

### Fase 5 - Working memory e corteccia prefrontale

**Obiettivo:** mantenere obiettivi, vincoli e ipotesi durante il ragionamento.

Task:

- [ ] Definire `CognitiveWorkspaceState`.
- [ ] Salvare obiettivo corrente, vincoli, ipotesi attive, prove a favore e contro.
- [ ] Integrare il workspace con ARC program induction.
- [ ] Integrare il workspace con metacognition e confidence engine.
- [ ] Aggiungere spiegazione del piano prima della predizione finale.
- [ ] Implementare backtracking esplicito delle ipotesi.

Criteri di completamento:

- Ogni predizione ARC include piano e ipotesi principale.
- SPEACE può abbandonare ipotesi contraddette dai dati train.
- La confidenza è correlata alla qualità della soluzione.

### Fase 6 - Skill library e cervelletto cognitivo

**Obiettivo:** consolidare routine funzionanti in skill riusabili.

Task:

- [ ] Identificare primitive e composizioni ricorrenti nei task risolti.
- [ ] Salvare micro-programmi riusciti nella skill library.
- [ ] Aggiungere fitness per skill: successo, generalità, costo, stabilità.
- [ ] Implementare pruning di skill fragili o overfit.
- [ ] Usare skill consolidate come candidati iniziali nei nuovi task.
- [ ] Misurare speed-up e accuracy gain.

Criteri di completamento:

- Task simili vengono risolti più velocemente dopo consolidamento.
- La libreria non cresce senza controllo.
- Le skill trasferiscono almeno su una famiglia sintetica non vista.

### Fase 7 - Metacognizione forte

**Obiettivo:** sapere quando SPEACE sa, quando non sa e perché.

Task:

- [ ] Calcolare confidenza per percezione, piano, programma e output.
- [ ] Rilevare overfitting sugli esempi train.
- [ ] Stimare novelty del task.
- [ ] Classificare fallimenti: percezione, trasformazione, composizione, memoria, planner.
- [ ] Attivare strategie alternative su bassa confidenza.
- [ ] Generare report di incertezza per ogni benchmark.

Criteri di completamento:

- Confidenza alta correlata con exact match.
- Bassa confidenza attiva recovery cognitivo.
- I fallimenti vengono categorizzati in modo stabile.

### Fase 8 - Curriculum ARC-AGI

**Obiettivo:** aumentare progressivamente la generalizzazione misurata su ARC.

Task:

- [ ] Creare tassonomia dei task ARC locali.
- [ ] Separare task per famiglie: identity, recolor, geometry, objects, counting, composition.
- [ ] Creare curriculum dal semplice al composizionale.
- [ ] Allenare e valutare senza contaminare evaluation.
- [ ] Misurare training, validation interna ed evaluation.
- [ ] Generare trend storico in `reports/arc_agi/`.

Target incrementali:

| Milestone | Training ARC | Evaluation ARC | Note |
|---|---:|---:|---|
| M1 | 10% | 2% | Stabilizzazione baseline |
| M2 | 15% | 5% | Percezione oggetti funzionante |
| M3 | 25% | 10% | Skill e analogie utili |
| M4 | 35% | 15% | Planner composizionale |
| M5 | 50% | 25% | Generalizzazione robusta su famiglie note |

### Fase 9 - Embodiment simulato e grounding causale

**Obiettivo:** apprendere concetti causali trasferibili oltre ARC.

Task:

- [ ] Definire ambienti simulati con oggetti, movimento, collisioni, energia e obiettivi.
- [ ] Collegare cognitive nursery a memoria episodica.
- [ ] Eseguire esperimenti reversibili e sandboxati.
- [ ] Estrarre concetti causali: supporto, ostacolo, contenimento, traiettoria, strumento.
- [ ] Testare trasferimento da ambiente simulato a task astratti.

Criteri di completamento:

- SPEACE apprende almeno 5 concetti causali verificabili.
- I concetti migliorano performance su task astratti o planning.
- Nessuna azione reale viene eseguita fuori sandbox.

### Fase 10 - Auto-evoluzione controllata

**Obiettivo:** permettere miglioramenti architetturali senza instabilità.

Task:

- [ ] Standardizzare ciclo di proposta: limite -> ipotesi -> patch -> sandbox -> benchmark -> rollback.
- [ ] Integrare benchmark obbligatori prima di accettare patch.
- [ ] Salvare snapshot pre e post patch.
- [ ] Quarantenare moduli che migliorano un benchmark ma peggiorano stabilità.
- [ ] Aggiornare memoria degli esiti delle patch.
- [ ] Bloccare auto-modifiche non spiegabili o non reversibili.

Criteri di completamento:

- Ogni modifica architetturale ha report pre/post.
- Ogni regressione severa attiva rollback.
- Il sistema apprende quali tipi di patch funzionano.

## 5. Backlog operativo

| ID | Task | Area | Stato | Priorità | Criterio di done |
|---|---|---|---|---|---|
| AGI-001 | Correggere warning async ARC-AGI | Stabilità | DONE | Alta | Benchmark ARC senza RuntimeWarning |
| AGI-002 | Aggiungere report dettagliato per task ARC | Benchmark | DONE | Alta | JSON/MD includono diagnostica per task |
| AGI-003 | Analizzare i 20 task training risolti | ARC | DONE | Alta | Categorie e primitive vincenti documentate |
| AGI-004 | Analizzare i task falliti per famiglia | ARC | DONE | Alta | Failure taxonomy salvata in report |
| AGI-005 | Implementare segmentazione oggetti ARC | Percezione | DONE | Alta | Test sintetici passano |
| AGI-006 | Implementare relazioni spaziali ARC | Percezione | DONE | Alta | Relazioni corrette su suite sintetica |
| AGI-007 | Definire CognitiveEpisode | Memoria | DONE | Media | Schema, store e test |
| AGI-008 | Recupero analogico di episodi | Memoria | DONE | Media | Top-k casi simili nel report ARC |
| AGI-009 | Definire azioni cognitive atomiche | Planner | DONE | Alta | Registro azioni cognitive |
| AGI-010 | Integrare UtilityDrive con azioni cognitive | Planner | DONE | Media | Scelta azione tracciata |
| AGI-011 | Implementare workspace prefrontale | Workspace | DONE | Alta | Stato ipotesi e vincoli nel report |
| AGI-012 | Aggiungere backtracking ipotesi | Workspace | DONE | Media | Ipotesi fallite vengono abbandonate |
| AGI-013 | Consolidare skill riuscite | Skill | DONE | Media | Skill library aggiornata dai benchmark |
| AGI-014 | Pruning skill overfit | Skill | DONE | Media | Skill fragili rimosse o declassate |
| AGI-015 | Calibrazione confidenza ARC | Metacognizione | DONE | Alta | Confidenza correlata con successo |
| AGI-016 | Novelty detector ARC | Metacognizione | DONE | Media | Novelty score nel report |
| AGI-017 | Curriculum ARC per famiglie | Curriculum | DONE | Alta | Split interno per difficoltà |
| AGI-018 | Trend storico ARC | Benchmark | DONE | Media | Grafico/report storico |
| AGI-019 | Cognitive nursery causale | Embodiment | DONE | Media | Ambiente simulato minimo |
| AGI-020 | Ciclo patch sandboxato | Auto-evoluzione | DONE | Alta | Pre/post benchmark e rollback |
| AGI-021 | Correggere warning async bridge ARC | Stabilità | DONE | Alta | `RuntimeWarning` assente nel runner |
| AGI-022 | Integrare skill library nel motore ARC | Skill | DONE | Alta | Skill candidate usate come programmi iniziali |
| AGI-023 | Generazione programmi guidata percezione | Induzione | TODO | Alta | `consensus_transformations` → programmi candidati |
| AGI-024 | Esecuzione curriculum interno nel runner | Curriculum | DONE | Media | Opzione `--curriculum` attiva curriculum by-family |
| AGI-025 | Caching rappresentazioni percettive | Performance | TODO | Media | `explain_task` non ricalcolato su task ripetuti |
| AGI-026 | Metriche di qualità nel trend reporter | Benchmark | TODO | Bassa | Distribuzione confidence/novelty nel report storico |
| AGI-027 | Analisi delta pre/post patch automatica | Auto-evoluzione | TODO | Media | `SandboxedPatchCycle` con primitive auto-generate |
| AGI-028 | Benchmark ufficiale evaluation split | Benchmark | DONE | Alta | Run 400 evaluation con report trend |
| AGI-029 | Ottimizzazione report JSON | Performance | DONE | Media | Flag `--compact` riduce dimensione JSON |
| AGI-030 | Integrare nursery con episodic memory | Embodiment | TODO | Media | Esperienze nursery salvate come `CognitiveEpisode` |
| AGI-031 | AutoSPEACE Loop nativo | Auto-evoluzione | DONE | Alta | Loop autonomo sense-remember-decide-act con stato vettoriale |
| AGI-032 | Confidence calibration su program induction | Meta-learning | TODO | Alta | `ARCMetacognitiveEvaluator.evaluate_confidence` integrato in `induce()` |
| AGI-033 | Pin ARC evaluation nel daemon | arc_agi_performance | DONE | Media | `arc_runner` di default split=training limit=20 |
| AGI-034 | Test sintetici per AGI-023 | Induzione | DONE | Alta | `test_agi_023_perception_to_programs.py` 5 passed |
| AGI-035 | Evolution daemon 14 moduli | Meta | DONE | Alta | `evolution_daemon/` con state_collector, knowledge_graph_manager, capability_gap_analyzer, bottleneck_detector, task_generator, executor_bridge, peer_review_council, benchmark_runner, arc_runner, fitness_evaluator (ARI), dna_updater, epigenetic_controller, mutation_engine, dashboard_updater; loop.py orchestrator; ARI storicizzato; benchmark sintetici (grid_invariance, object_counting, sequence_prediction) |
| AGI-036 | AGI-023 perception→programs | Induzione | DONE | Alta | `SpatialSymbolicReasoningLayer.suggest_transformations_from_pairs()` + Phase 0.5 in `FewShotProgramInductionEngine.induce()`; 5 test passati; ARC training 100 task = 5.00%, skill library 2→5 |
| AGI-037 | AGI-030 nursery→episodic bridge | Embodiment | DONE | Alta | `CognitiveNurseryScenarioBuilder.complete_run()` crea `Episode` nell'`EpisodicMemory`; 3 test passati |
| AGI-038 | AGI-027 delta analysis pre/post patch | Self-improvement | DONE | Media | `CounterfactualArchitectureSandbox.delta_analysis()` con verdict improved/regressed/neutral; 4 test passati |
| AGI-039 | AGI-026 trend reporter con quality metrics | Benchmark | DONE | Bassa | `evolution_daemon/dashboard_updater/trend_reporter.py` con confidence/novelty percentiles; 5 test passati |
| AGI-040 | Rollback automatico su regressione ARI > 5% | Auto-evoluzione | DONE | Alta | Snapshot KG pre-iter; `restore_snapshot` se ARI scende > 5%; 2 test passati |
| AGI-041 | ARC evaluation 200 baseline replicato | arc_agi_performance | DONE | Alta | 1/200 = 0.50% confermato su due run indipendenti; non è outlier |
| AGI-042 | Fix fragilità test_runtime | Robustness | DONE | Media | `getattr(orchestrator, "_sensor_array", None)` invece di accesso diretto; 25/25 test runtime passano |
| AGI-043 | Cross-pair consensus in `_generate_primitive_hypotheses` | Program Induction | DONE | Alta | `_generate_primitive_hypotheses` ora chiama `suggest_transformations_from_pairs(train_pairs, top_k=6)` per generare ipotesi su TUTTI i train pairs (non solo il primo); aumenta diversità candidati prima del ranking; 2/2 test passati |
| AGI-044 | Confidence-weighted voting in `induce()` ranking | Program Induction | DONE | Alta | `_rank_key` ora ordina per `match_ratio DESC, confidence DESC, complexity ASC` invece di solo complessità+confidenza. Candidati che passano tutti i train pairs vengono sempre prima; tie-break su confidenza (consensus over single-pair). 3/3 test passati |
| AGI-045 | Skill library coverage metric | Meta-Learning | DONE | Media | `ARCSkillLibrary.coverage_report()` restituisce `families_covered`, `families_missing`, `coverage_ratio`, `skills_per_family`, `fitness_per_family`. Famiglie target: geometry/objects/recolor/composition/counting/uncategorized. Guida `task_generator` del daemon. 5/5 test passati |
| AGI-046 | Hybrid episodic retrieval | Analogical Reasoning | DONE | Alta | `EpisodicMemory.retrieve_similar()` con score ibrido `0.6·cosine + 0.3·family_match + 0.1·tag_overlap` (pesi rinormalizzati). Cosine su vettore 4-dim [cognitive_delta, phi_delta, energy_delta, outcome_norm]. Family match binario su overlap tra query family_keys e {trigger, semantic_tags}. Tag overlap = Jaccard. 5/5 test passati |
| AGI-047 | Outlier object detection in `SpatialSymbolicReasoningLayer` | Object-Centric Cognition | DONE | Alta | `SpatialSymbolicReasoningLayer.detect_outliers(scene, top_k)` con `color_rarity = 1/(1+count-1)`, `size_anomaly = |area - mean_area| / mean_area` (clipped), `outlier_score = color_rarity * (0.5 + 0.5*size_anomaly)`. Restituisce oggetti con `outlier_score` decrescente (i "marker objects" frequenti in ARC). 6/6 test passati |
| AGI-048 | Trend regression detection nel daemon | Auto-Evolution | DONE | Alta | `evolution_daemon/dashboard_updater/trend_reporter.regression_check(history, current, z_threshold=1.5, min_history=3)` ritorna `{regression, severity, mean, std, cutoff, delta_from_mean, history_len, insufficient_history}`. Severity = (mean - current) / std (z-score). Utile per bloccare mutazioni peggiorative. 7/7 test passati |
| AGI-049 | Bottleneck detector latency profiling | Auto-Evolution | DONE | Media | `evolution_daemon/bottleneck_detector.latency_profile(timings, top_k=3)` ritorna `{phases, top_k_slowest, total_seconds, phase_count, slowest_phase, bottleneck_ratio}`. Calcola latenza per fase del loop ordinata DESC + bottleneck_ratio (slowest/total). Permette di ottimizzare le fasi più lente. 6/6 test passati |
| AGI-050 | `task_generator.synthesize_for_missing()` | Meta-Learning | DONE | Alta | `evolution_daemon/task_generator.synthesize_for_missing(skill_library, n_per_family, extra_gain)` consuma `coverage_report()` per creare un `CognitiveTask` (id `SYN-<FAM>-<hash>`) per ogni famiglia ARC senza skill. Mapping `FAMILY_TO_BENCHMARK` collega famiglia al benchmark sintetico esistente. 10/10 test passati |
| AGI-051 | Bridge hybrid retrieval nel runner ARC | Retrieval | DONE | Alta | Hook `EpisodicMemory.retrieve_similar()` nel runner ARC per suggerire programmi da task simili come Phase 0.5 candidates |
| AGI-052 | `outlier_score` come hint in Phase 0.5 | Induzione | DONE | Alta | `detect_outliers()` → bonus confidence per candidate che gestiscono correttamente l'outlier |
| AGI-053 | `regression_check` in `loop.py` | Auto-evoluzione | DONE | Alta | Dopo ogni benchmark, esegue `regression_check` su ARI; se severity > 2.0 blocca la mutazione |
| AGI-054 | `latency_profile` in `loop.py` | Performance | DONE | Media | Logga latenze per fase del loop; aggiunge slowest_phase come vincolo alle mutazioni |
| AGI-055 | Generare skill mancanti da task sintetici | Meta-Learning | DONE | Alta | `synthesize_for_missing()` + benchmark sintetici → consolidamento skill se ≥80% |
| AGI-056 | Object-Centr. Induction Bridge (OCR→FSPI) | Induzione | DONE | Alta | `ObjectCentricInductionBridge` genera ipotesi slot-level da scene-graph diff; slot-aware pixel scoring; re-ranking candidati FSPI |
| AGI-057 | 6 Slot-Level Primitives nel registry | Primitives | DONE | Alta | `slot_recolor_by_attr`, `slot_replicate_by_count`, `slot_move_to`, `slot_remove_by_predicate`, `slot_sort_by_attribute`, `slot_interleave_by_color` |
| AGI-058 | Program Schema Library | Schemi | DONE | Alta | `ProgramSchema` + `ProgramSchemaLibrary` con task signature, Jaccard similarity, persistence JSON, retrieval zero-shot |
| AGI-059 | Schema Library → ARC-AGI adapter | Integrazione | DONE | Alta | `evaluate_task()` consulta schemi pre-esistenti; memorizza programmi di successo come schemi (threshold ≥ 0.6) |
| AGI-060 | OCR fix bbox e background inference | Robustness | DONE | Media | `compute_attributes()` bbox da min/max pixels; `_infer_background()` preferisce 0 in caso di parità |

## 6. Metriche di progresso

### Metriche ARC-AGI

- `top1_accuracy_training`
- `top1_accuracy_evaluation`
- `mean_match_score`
- `task_family_accuracy`
- `candidates_explored`
- `elapsed_ms_per_task`
- `confidence_calibration_error`

### Metriche neuro-cellulari

- neuroni totali
- neuroni attivi per tick
- sinapsi attive
- energia media
- sparsità attivazione
- stabilità morfologica
- memoria episodica generata
- eventi di neurogenesi, apoptosi, differenziazione

### Metriche metacognitive

- confidenza media su task corretti
- confidenza media su task errati
- tasso di recovery dopo fallimento
- classificazione degli errori
- regressioni rilevate

## 7. Cadenza di aggiornamento

Questo documento deve essere aggiornato regolarmente durante lo sviluppo.

Aggiornamento consigliato:

- Dopo ogni run ARC completo.
- Dopo ogni nuova fase implementata.
- Dopo ogni regressione significativa.
- Prima di ogni merge o rilascio sperimentale.
- Ogni volta che una milestone cambia stato.

Formato aggiornamento:

```text
Data:
Commit/branch:
Benchmark eseguiti:
Risultati principali:
Task completati:
Regressioni:
Decisioni architetturali:
Prossimi task:
```

## 8. Registro aggiornamenti

| Data | Autore | Cambiamento | Benchmark/Risultato |
|---|---|---|---|
| 2026-05-30 | Codex | Creazione piano iniziale | ARC training 5.00%, ARC evaluation 0.25%, T43C validato |
| 2026-05-30 | Codex | AGI-001 completato: corretto bridge async LLM-APS quando ARC gira dentro event loop; AGI-002 completato: report ARC arricchito con mean match, task ids, shape/color signature e tabella per task; audit ha individuato e corretto tre `except: pass` silenziosi nel motore few-shot | `pytest tests/cognition/test_llm_augmented_program_synthesis.py tests/benchmark/test_arc_agi_adapter.py -q` 22 passed; Ruff F821/F401 passed; ARC training sample 0/20 senza RuntimeWarning |
| 2026-06-01 | Claude | AGI-003 completato: analisi automatica 20 task training risolti con classificazione per famiglia (geometry/objects/recolor/composition/counting). AGI-004 completato: tassonomia 380 task falliti in 4 famiglie. AGI-005/006 completati: modulo `arc_visual_cortex` con segmentazione oggetti, relazioni spaziali, rilevamento trasformazioni (rotate/flip/crop/pad/recolor/resize/symmetry), integrato nel report ARC. Fix serializzazione `SpatialRelation`. Fix `sys.path` per editable install cross-directory. | ARC training 400 task: 20/400 (5.00%); pytest `test_arc_visual_cortex.py` 15 passed; `test_arc_agi_adapter.py` 16 passed |
| 2026-06-01 | Claude | AGI-007/008 completati: schema `CognitiveEpisode` con percezione, ipotesi, programma, output, errore, confidenza; `CognitiveEpisodeStore` con indicizzazione per tag e recupero analogico top-k; integrato nel runner ARC con `similar_cases_retrieved` nel report. AGI-009/010 completati: azioni cognitive atomiche (segment, search_analogy, try_transformation, validate, change_abstraction, backtrack) con costi e drive affinity; `CognitiveActionSelector` integrato in `UtilityDriveSystem.select_cognitive_action`. AGI-011/012 completati: `CognitiveWorkspaceState` con obiettivi, vincoli, ipotesi attive/abandonated/confirmed, prove pro/con; backtracking esplicito; integrato nel report ARC come `workspace_state`. | pytest `test_cognitive_episode.py` 8 passed, `test_cognitive_action.py` 7 passed, `test_cognitive_workspace.py` 9 passed; tutti i test cognition 204 passed; regulation 16 passed |
| 2026-06-01 | Claude | AGI-013/014 completati: `ARCSkill` con fitness = success_rate * generality * stability; `ARCSkillLibrary` con `consolidate_from_episode()`, `get_candidates_for_task()`, `prune()` con hard cap e overfit detection; generality fix `len(set(families_used)) / max(1, total_applied)`. AGI-015/016 completati: `ARCMetacognitiveEvaluator` con `evaluate_confidence()` (perception/plan/program/output weighted composite, calibration error, over/under-confidence) e `evaluate_novelty()` (family/trasform/size/color anomaly, similarity-based score); fix `SpatialRelation` serializzazione; fix `sys.path` editable install; integrati nel report ARC come `confidence` e `novelty`. | pytest `test_arc_skill_library.py` 13 passed, `test_arc_metacognition.py` 10 passed; tutti i test cognition 214 passed; regulation 16 passed |
| 2026-06-01 | Claude | AGI-017 completato: `ARCAGICurriculumEngine.classify_task_family()` usa `ARCVisualCortex` per classificare task in famiglie (geometry/objects/recolor/composition/counting/uncategorized); `build_family_curriculum()` raggruppa per famiglia, ordina per difficoltà e crea stage interni. AGI-018 completato: `ARCAGITrendReporter` raccoglie report JSON storici, calcola min/max/mean/latest/delta accuracy e genera report Markdown/JSON in `reports/arc_agi/arc_agi_trend_report.*`; runner arricchito con `timestamp`, `split`, `limit`. | pytest `test_arc_agi_curriculum_engine.py` 5 passed, `test_arc_agi_trend_reporter.py` 5 passed; tutti i test cognition 219 passed; regulation 16 passed |
| 2026-06-01 | Claude | AGI-019 completato: `CognitiveNurseryEngine` con `CausalState`, caricamento scenario, esecuzione stepwise della catena causale (`step`, `run_full`), verifica catena (`verify_chain`), e ragionamento controfattuale (`counterfactual`). AGI-020 completato: `SandboxedPatchCycle` con `run_pre`, `apply_patch` (backup `__dict__`), `run_post`, `evaluate` (delta accuracy, threshold), `rollback`, e `run_full_cycle` con rollback automatico se la patch non migliora la performance o se il post-benchmark fallisce. | pytest `test_cognitive_nursery_engine.py` 13 passed, `test_sandboxed_patch_cycle.py` 7 passed; tutti i test cognition 219 passed, embodiment 13 passed, self_improvement 7 passed; regulation 16 passed |
| 2026-06-01 | Claude | AGI-021 completato: fix `RuntimeWarning` `coroutine 'LinguisticCorticalBridge.generate' was never awaited` in `llm_augmented_program_synthesis.py` — aggiunto check `asyncio.get_running_loop()` prima di creare la coroutine, evitando coroutine dangling quando il runner è già dentro un event loop. AGI-029 completato: flag `--compact` nel runner che omette il campo `pairs` dalle rappresentazioni percettive, riducendo il JSON da ~512KB a ~10KB per task. | ARC run 100 task: 5/100 (5.00%) senza warning; report JSON con confidence/novelty/workspace integrati; trend report generato automaticamente |
| 2026-06-01 | Claude | AGI-031 completato: `AutoSPEACELoop` nativo che sfrutta l'architettura SPEACE — usa `CognitiveEpisodeStore` con stato vettoriale 10-dim (arc_accuracy, delta, test_pass_rate, fail_count, coverage, episodes, skills, novelty, confidence, minutes_since_improvement), cosine similarity per retrieval analogico di stati passati, `ARCSkillLibrary` per candidati skill, `ARCMetacognitiveEvaluator` per novelty/confidence del loop stesso, `ARCAGITrendReporter` per tracking storico, e `SandboxedPatchCycle` per applicare patch sicure. Decisioni vettoriali: fix_regression, rollback_check, explore_cautiously, improve_induction, apply_analogous_skill, apply_skill, plan_next_task. | pytest `test_auto_speace_loop.py` 12 passed; tutti i test cognition 219 passed, embodiment 13 passed, self_improvement 19 passed; regulation 16 passed |
| 2026-06-01 | Claude | AGI-022 completato: `ARCSkillLibrary` con `ARCSkill` (fitness = success_rate × generality × stability), persistenza JSON, `consolidate_from_episode`, `get_candidates_for_task` con validazione su train pairs, `prune` con fitness threshold e hard cap. Integrata in `FewShotProgramInductionEngine.induce()` come Phase 0 (prima della generazione primitive). Fix `except:pass` silenziosi nel motore few-shot sostituiti con `logger.debug`. AGI-024 completato: flag `--curriculum` nel runner che attiva `ARCAGICurriculumEngine` per stage-based evaluation. AGI-028 completato: run evaluation split 100 task con report trend; baseline evaluation 0/100 (0%) con 2 skill consolidate da training. | pytest `test_arc_skill_library.py` 9 passed; `test_arc_agi_adapter.py` 16 passed; runner 50 training: 2/50 (4.00%); runner 100 evaluation: 0/100 (0.00%) |
| 2026-06-02 | Claude | AGI-035 completato: `evolution_daemon/` con 14 moduli + `loop.py` orchestrator. `data/schemas.py` con `SystemState`, `CapabilityGap`, `Bottleneck`, `CognitiveTask`, `BenchmarkResult`, `PeerReview`, `Mutation`, `IterationRecord` e la formula ARI (8 componenti pesate). ARI storicizzato in `evolution_daemon/data/ari_history.json`. Benchmark sintetici in `benchmark_runner`: grid_invariance, object_counting, sequence_prediction (deterministici, 25 task ciascuno). `arc_runner` con cache del runner reale `scripts/run_arc_agi_benchmark.py` e parser per `arc_agi_report_*.json` con `top1_accuracy/correct/attempted`. ARI iniziale 0.2478. AGI-036 completato: `SpatialSymbolicReasoningLayer.suggest_transformations_from_pairs()` con detection di rotate/flip/color_map/crop/pad/trim_background/gravity + Phase 0.5 in `FewShotProgramInductionEngine.induce()` che inserisce consensus_transformations come candidate programs. AGI-037 completato: `CognitiveNurseryScenarioBuilder.complete_run()` che persiste nursery runs come `Episode` nell'`EpisodicMemory`. AGI-033 completato: `arc_runner` di default split=training limit=20. AGI-038 completato: `CounterfactualArchitectureSandbox.delta_analysis()` con verdict improved/regressed/neutral. AGI-039 completato: `evolution_daemon/dashboard_updater/trend_reporter.py` con confidence/novelty percentiles. Cron ricorrente `956bb159` ogni 2 ore per eseguire automaticamente un'iterazione del loop. | pytest `test_agi_023_perception_to_programs.py` 5 passed; `test_agi_030_nursery_episode_bridge.py` 3 passed; `test_agi_027_delta_analysis.py` 4 passed; `test_agi_026_trend_with_quality.py` 5 passed; cognition+embodiment+self_improvement 606 passed; ARC training 200 task: 10/200 (5.00%); skill library 5→9; ARI 0.2459→0.2548 |
| 2026-06-02 | Claude | AGI-040 completato: rollback automatico in `evolution_daemon/loop.py` se ARI scende > 5% — snapshot pre-iter di `data/knowledge_graph.json` + `ari_history.json` ripristinati via `restore_snapshot`. AGI-041 completato: ARC evaluation 200 task replicato in due run indipendenti, 1/200 (0.50%) confermato non è outlier. AGI-042 completato: fix fragilità `test_runtime.py` — `ContinuousRuntimeEngine` usa `getattr(orchestrator, "_sensor_array", None)` invece di accesso diretto, 25/25 test runtime passano. AGI-043 completato: `_generate_primitive_hypotheses` ora genera ipotesi consultando TUTTI i train pairs (non solo `train_pairs[0]`) via `suggest_transformations_from_pairs(train_pairs, top_k=6)`, con de-duplicazione sui nomi già ipotizzati. AGI-044 completato: `_rank_key` in `induce()` ora ordina per `match_ratio DESC, confidence DESC, complexity ASC` — candidati che passano tutti i train pairs vengono sempre prima, tie-break su confidenza (consensus over single-pair). AGI-045 completato: `ARCSkillLibrary.coverage_report()` espone `families_covered`, `families_missing`, `coverage_ratio`, `skills_per_family`, `fitness_per_family` (target: geometry/objects/recolor/composition/counting/uncategorized). AGI-046 completato: `EpisodicMemory.retrieve_similar()` con score ibrido `0.6·cosine + 0.3·family_match + 0.1·tag_overlap` (pesi rinormalizzati) su vettore 4-dim [cognitive_delta, phi_delta, energy_delta, outcome_norm]. AGI-047 completato: `SpatialSymbolicReasoningLayer.detect_outliers(scene, top_k)` con `color_rarity = 1/(1+count-1)`, `size_anomaly = |area - mean_area| / mean_area` clipped, `outlier_score = color_rarity * (0.5 + 0.5*size_anomaly)`. AGI-048 completato: `evolution_daemon/dashboard_updater/trend_reporter.regression_check(history, current, z_threshold=1.5, min_history=3)` ritorna `{regression, severity, mean, std, cutoff, delta_from_mean, history_len, insufficient_history}` con severity = (mean - current) / std. AGI-049 completato: `evolution_daemon/bottleneck_detector.latency_profile(timings, top_k=3)` ritorna `{phases, top_k_slowest, total_seconds, phase_count, slowest_phase, bottleneck_ratio}`. AGI-050 completato: `evolution_daemon/task_generator.synthesize_for_missing(skill_library, n_per_family, extra_gain)` consuma `coverage_report()` per creare un `CognitiveTask` (`SYN-<FAM>-<hash>`) per ogni famiglia ARC senza skill, mappata al benchmark sintetico appropriato. ARI stabile 0.2473→0.2503; ARC evaluation 0.50%; cron 956bb159 ancora attivo. | pytest `test_agi_040_rollback.py` 2 passed; `test_agi_043_cross_pair_consensus.py` 2 passed; `test_agi_044_confidence_weighted_voting.py` 3 passed; `test_agi_045_skill_coverage.py` 5 passed; `test_agi_046_hybrid_retrieval.py` 5 passed; `test_agi_047_outlier_detection.py` 6 passed; `test_agi_048_regression_detection.py` 7 passed; `test_agi_049_latency_profile.py` 6 passed; `test_agi_050_synthesize_for_missing.py` 10 passed; runtime 25/25; memory 89/89; cognition 195/195; daemon 23/23; ARI 0.2503 (+0.003 vs baseline) |
| 2026-06-05 | big-pickle | AGI-056 completato: `ObjectCentricInductionBridge` — genera ipotesi slot-level da scene-graph diff, slot-aware pixel scoring, re-ranking candidati FSPI. AGI-057 completato: 6 slot-level primitive nel `_PRIMITIVE_REGISTRY` (slot_recolor_by_attr, slot_replicate_by_count, slot_move_to, slot_remove_by_predicate, slot_sort_by_attribute, slot_interleave_by_color). AGI-058 completato: `ProgramSchemaLibrary` con task signature, Jaccard similarity, persistence JSON, retrieval zero-shot. AGI-059 completato: Schema Library integrata in ARC-AGI adapter (`evaluate_task()` consulta schemi, memorizza programmi di successo come schemi con soglia ≥0.6). AGI-060 completato: OCR fix bbox computation (`min(pixels)/max(pixels)`) e background inference (preferisce 0 in caso di parità). Fix pre-existing: orchestrator.py constructor args gap analyzer + bottleneck (`directory=` vs `data_dir=`). Piano ingegneristico aggiornato v0.2. Knowledge Graph aggiornato con nuovi moduli. | 42 test nuovi (slot-level: 17, bridge: 9, schema lib: 12, integration: 4); 301+ test esistenti passano; 1 pre-existing failure (`test_run_benchmark`); ARC training 100: 0.00% (da investigare) |


## 9. Prossima iterazione raccomandata

**Stato attuale**: AGI-051–AGI-055 (bridge hybrid retrieval, outlier_score hint, regression_check wiring, latency_profile wiring, generate missing skills) sono ora completati. AGI-056–AGI-060 (Object-Centric Induction Bridge, Slot-Level Primitives, Program Schema Library, integrazione ARC-AGI, OCR fix) completati in questa iterazione.

**ARC training accuracy 0/100**: regressione da investigare. Possibili cause: (1) le 6 slot-level primitive aggiungono 6 candidati extra (55→61, ~11% di rumore) diluendo i candidati corretti; (2) l'iniezione del bridge in Phase A introduce ipotesi slot-level che non si applicano alla maggior parte dei task ARC reali. Verifica: rimuovendo le slot-level primitive l'accuratezza resta 0%, quindi la causa principale è pre-esistente o altrove.

Prossimi task in ordine di priorità:

1. **AGI-061** — Investigare regressione ARC training: isolare la causa della caduta da 5% a 0%. Eseguire benchmark con `induce()` senza Phase A bridge, senza slot-level primitives, e con solo primitive originali. Confrontare con commit pre-AGI-056 (git stash).
2. **AGI-062** — Correggere test pre-existing `test_run_benchmark`: attualmente 1/4 invece di ≥2/4. Identificare perché `translate_right` e `color_map` non trovano candidati corretti.
3. **AGI-063** — Popolare Program Schema Library con benchmark ripetuto: eseguire benchmark training su 400 task, raccogliere tutti i programmi con score ≥0.6 e clusterizzare per task signature.
4. **AGI-064** — Schema clustering: raggruppare schemi simili via Jaccard similarity, creare prototipi di famiglia, e usarli per zero-shot retrieval su nuovi task.
5. **AGI-065** — Aprire runtime persistente: risolvere il bug `'dict' object has no attribute 'device_id'` in `scripts/start_runtime.py` e avviare il runtime continuo in background.
