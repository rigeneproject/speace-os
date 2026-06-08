# Analisi NeuroEvolve / FEAGI per la Roadmap Evolutiva di SPEACE

## Documenti Analizzati

1. **NeuroEvolve: A Bio-Inspired Framework for Efficient AGI** (`NeuroEvolve A Bio-Inspired Framework.md`)
2. **NeuroEvolve: A Dynamic Brain Graph Deep Generative Model** (`104_NeuroEvolve_A_Dynamic_Brai.pdf`)
3. **A Brain-Inspired Framework for Evolutionary AGI** (FEAGI Dissertation, `A brain-inspired framework for.pdf`)
4. **NeuroEvolve: A Brain-Inspired Mutation Optimization Algorithm** (`NeuroEvolve--A-brain-inspired-mutation-optimiz_2026_International-Journal-of.pdf`)

---

## Sintesi dei Modelli Analizzati

| Documento | Dominio | Tecnica Chiave | Rilevanza per SPEACE |
|---|---|---|---|
| Bio-Inspired Framework (MD) | AGI generico | MAS, Fractal Memory, EDD, Meta-Learning LSTM | Alta: architettura multi-agente, ottimizzazione energetica, evoluzione genomica |
| Dynamic Brain Graph (PDF) | fMRI / Neuroimaging | VAE gerarchico, community embedding temporale, GRU | Media: modelli dinamici di connettività, comunità funzionali |
| FEAGI Dissertation (PDF) | Simulazione cervello artificiale | Genome/Connectome, Neuroembryogenesis, Burst Engine, STDP, GA | **Altissima**: è il framework più vicino all'architettura di SPEACE |
| BI-DE Optimization (PDF) | Medical data analysis | Differential Evolution con fattori di mutazione dinamici | Media-Bassa: ispirazione per operatori evolutivi adattivi |

---

## Insight 1 — Genotipo/Phenotipo e Indirect Encoding (da FEAGI)

**Cosa fa FEAGI:**
- Il **genome** è un documento JSON gerarchico che codifica *indirettamente* le proprietà anatomiche (geometria corticale, densità neuronale, morfologie, regole di crescita).
- Il **connectome** è il fenotipo costruito dal processo di neuroembriogenesi e memorizzato in un database orientato agli oggetti (MongoDB).
- La separazione consente l'evoluzione dell'architettura senza modificare il codice sorgente.

**Stato SPEACE:**
- Abbiamo `SharedGenome` (YAML) e `NeuralCircuit` (fenotipo in memoria).
- La separazione è presente ma meno strutturata: il circuito viene costruito dall'`Orchestrator` con parametri hard-coded (`n_inputs=10`, `n_hidden=60`, ecc.) anziché decodificati dal genoma.

**Azione Raccomandata:**
- Potenziare il genoma in modo che definisca completamente la morfologia iniziale (numero di neuroni per strato, densità sinaptica, regole di crescita spaziale).
- Considerare una separazione formale genoma / connectome dove il connectome è il risultato di un processo di `NeuroembryogenesisEngine` (costruzione fenotipo dal genotipo).

---

## Insight 2 — Neuroembryogenesis e Regole di Crescita (da FEAGI)

**Cosa fa FEAGI:**
- L'unità di neuroembriogenesis legge il genoma e costruisce il cervello in fasi sequenziali:
  1. Formazione aree corticali
  2. Neurogenesi (proliferazione, migrazione, differenziazione)
  3. Sinaptogenesis con **regole di crescita geometriche** (cilindro, cono, sfera) che definiscono in quali regioni spaziali un assone può cercare la destinazione.
- Le regole di crescita sono parametri evolvibili nel genoma (altezza, raggio, orientamento).

**Stato SPEACE:**
- Sinapsi create randomicamente senza vincoli spaziali o morfologici.
- Non esiste un concetto di "proliferazione" o "migrazione" — i neuroni vengono aggiunti direttamente a `hidden_neurons`.

**Azione Raccomandata:**
- Introdurre un `MorphologyEngine` che associa coordinate (x,y,z) ai neuroni e definisce "growth rules" per la sinaptogenesis.
- La neurogenesi di T8 dovrebbe posizionare i nuovi neuroni in uno spazio morfologico e connetterli solo a neuroni entro un certo raggio geometrico, non random.
- Questo rende l'evoluzione strutturale *spazialmente coerente* invece che caotica.

---

## Insight 3 — Burst Engine e Simulazione Event-Driven (da FEAGI)

**Cosa fa FEAGI:**
- Invece di "tickare" tutti i 100 miliardi di neuroni, usa un **burst engine**:
  - Mantiene una "Fire Candidate List" (FCL) di neuroni il cui potenziale di membrana ha superato la soglia.
  - Ogni burst attiva *solo* i neuroni nella FCL.
  - Complessità: O(n²) dove n è il numero di neuroni che sparano, non il numero totale.
- Questo sfrutta la **sparsità** del firing biologico (tipicamente <5% dei neuroni attivi in un dato istante).

**Stato SPEACE:**
- `_tick()` itera su *tutti* i neuroni e chiama `tick()` su ognuno, indipendentemente dallo stato.
- A 1000 neuroni non è un problema, ma a scala umana (100M neuroni) diventa un collo di bottiglia.

**Azione Raccomandata:**
- Evolvere il loop principale verso un modello **event-driven / burst-centric**:
  - Separare l'aggiornamento del potenziale di membrana (energia/attivazione) dal firing.
  - Accodare i neuroni che superano la soglia in una `fire_queue`.
  - Processare solo la coda ad ogni burst.
- Questo abilita anche meccanismi più precisi di STDP (vedi Insight 4).

---

## Insight 4 — STDP, LTP/LTD e Finestra Temporale (da FEAGI)

**Cosa fa FEAGI:**
- Implementa una variante di **Spike-Timing-Dependent Plasticity (STDP)** semplificata:
  - Se neurone pre-sinaptico A spara al burst `n` e post-sinaptico B spara al burst `n+1` → **LTP** (potenziamento, `+C`).
  - Se A spara al burst `n` e B spara al burst `n-1` → **LTD** (depressione, `-C`).
  - Se |ΔB| > 1 → nessun effetto (finestra temporale stretta).
- La plasticità è quindi legata alla *differenza di burst* tra pre e post, non a gradienti backprop.

**Stato SPEACE:**
- `PlasticityEngine` è meno dettagliato; l'adattamento avviene a livello di soglia neurale (`threshold -= plasticity_rate * feedback`).
- Non c'è ancora un modello di potenziamento/depressione sinaptica basato su causalità temporale.

**Azione Raccomandata:**
- Potenziare `PlasticityEngine` per implementare STDP burst-aware:
  - Registrare il `burst_id` / `tick_id` dell'ultimo firing di ogni neurone.
  - Quando un neurone spara, per ogni sinapsi in uscita verso neuroni che hanno sparato al tick successivo/precedente, applicare LTP/LTD.
- Questo rende la plasticità *locala e causale*, biologicamente plausibile, senza bisogno di backpropagation globale.

---

## Insight 5 — Inibizione, Snooze e Periodo Refrattario (da FEAGI)

**Cosa fa FEAGI:**
- **Neurotrasmettitori eccitatori/inibitori**: i neuroni inibitori riducono il potenziale di membrana dei target.
- **Snooze flag**: se un neurone spara consecutivamente troppe volte entro una finestra di burst, viene "snoozed" (forzato a non sparare per N burst).
- **Periodo refrattario**: dopo il firing, un neurone è bloccato per un numero di burst definito nel genoma.
- Questi meccanismi prevengono loop infiniti di firing e stabilizzano la rete.

**Stato SPEACE:**
- `DigitalNeuron` ha `threshold` ed `energy`, ma manca un vero periodo refrattario post-firing.
- Non esistono neuroni inibitori; tutti i segnali sono eccitatori (aumentano l'attivazione).
- Il circuito puù potenzialmente entrare in oscillazioni o runaway activation.

**Azione Raccomandata:**
- Aggiungere campo `refractory_period: int` a `DigitalNeuron`.
- Aggiungere tipo `role="inhibitory_neuron"` che emetta segnali con `strength < 0` (o un flag `inhibitory: bool`).
- Implementare `snooze_counter` quando `consecutive_fires > threshold`.
- Questo migliora la stabilità di sistema e la coerenza Φ.

---

## Insight 6 — Memoria come Cell Assembly e Semantic Pointers (da FEAGI)

**Cosa fa FEAGI:**
- La memoria dichiarativa a lungo termine è costituita da **cell assemblies**: gruppi di neuroni che si attivano simultaneamente per rappresentare un oggetto.
- Quando due stimoli diversi arrivano in **prossimità temporale**, le loro cell assemblies vengono collegate tramite LTP (associative learning).
- I **semantic pointers** sono firme uniche generate alla fine di un percorso corticale che rappresentano lo stimolo.

**Stato SPEACE:**
- `MorphologicalMemory` (T7) traccia la *struttura* (eventi morfologici, snapshot di Φ), ma non memorizza *contenuti* o *pattern* di attivazione.
- Non esiste un modulo di memoria semantica o associative memory.

**Azione Raccomandata:**
- Introdurre un nuovo task futuro **T12 — SemanticMemory / CellAssemblyEngine**:
  - Rilevare pattern di co-attivazione neuronale durante i burst.
  - Formare "assemblies" quando un insieme di neuroni si attiva ripetutamente in tempi ravvicinati.
  - Collegare assemblies di regioni diverse (es. input visivo + output motorio) per associative learning.
- Questo è il prerequisito per il comportamento cognitivo vero e proprio.

---

## Insight 7 — Loop Evolutivo con Genome Database (da FEAGI)

**Cosa fa FEAGI:**
- Ogni istanza del cervello artificiale, al termine del ciclo di vita, salva:
  - Il **genoma** usato
  - Le **statistiche** di performance (fitness, accuracy, errori)
- Il database di genomi alimenta un **Genetic Algorithm** che:
  - **Selezione**: sceglie il migliore, il più recente, o un genoma random.
  - **Mutazione**: modifica geni casuali di ±30% (fase esplorativa), poi ±10% (fase fine-tuning) quando fitness > 0.5.
  - **Crossover**: scambia set di geni tra due genomi top-performing.
- L'evoluzione è quindi **strutturale** (muta il genoma che definisce l'anatomia) e **fisiologica** (muta i parametri delle funzioni).

**Stato SPEACE:**
- Il genoma è statico (letto da YAML all'avvio).
- Non esiste un database di genomi, né un loop evolutivo, né una funzione di fitness formalizzata.

**Azione Raccomandata:**
- Aggiungere **GenomeDatabase** e **EvolutionEngine** alla roadmap post-v0.2:
  - Persistere genomi + metriche in un database (anche JSONL locale inizialmente).
  - Definire una fitness function basata su coerenza Φ, errori, energia, longevità.
  - Implementare mutation operator che agisce sui parametri del genoma (es. `neuron_density`, `synapse_density`, `plasticity_constant`).
- Questo chiude il ciclo: genoma → fenotipo → esperienza → fitness → genoma evoluto.

---

## Insight 8 — Energia come Vincolo Attivo (da Bio-Inspired Framework)

**Cosa fa il Markdown NeuroEvolve:**
- Implementa **Adaptive Energy Optimization**:
  - Synaptic Pruning durante il training per ridurre il carico computazionale.
  - Dynamic Learning Rate Adjustment: rallenta quando il sistema si affida alla memoria per conservare risorse.
  - Simulazione del costo energetico: azioni basate su memoria costano 0.1, calcolo pieno costa 1.0.
- L'ottimizzazione energetica è un obiettivo primario, non solo un vincolo.

**Stato SPEACE:**
- L'energia è tracciata (`mean_energy` in `SystemMetrics`) e usata come condizione per la neurogenesi, ma non è un target di ottimizzazione attiva.
- Non esiste un EnergyControlAgent.

**Azione Raccomandata:**
- Introdurre un `EnergyBudget` e un `EnergyControlAgent` (cellula gliale evoluta o agente dedicato):
  - Se l'energia media scende sotto una soglia, attivare:
    - Aumento pruning (microglia più aggressiva)
    - Riduzione del learning rate
    - Soppressione della neurogenesi
    - Snooze di neuroni ad alta attività (come FEAGI)
- Questo rende SPEACE un sistema che *ottimizza* la sopravvivenza metabolica, non solo la performance.

---

## Insight 9 — Community Embeddings e Reti Funzionali (da Dynamic Brain Graph)

**Cosa fa il paper fMRI:**
- Il cervello biologico ha **Functional Connectivity Networks (FCN)**: comunità di nodi che corrispondono a reti anatomiche/funzionali (DMN, VIS, SMN, ecc.).
- NeuroEvolve (fMRI) le apprende automaticamente come distribuzioni latenti su community embeddings.
- Le comunità evolvono nel tempo e si sovrappongono a reti note della letteratura neuroscientifica.

**Stato SPEACE:**
- Il circuito ha strati (input, hidden, output) ma non comunità dinamiche o cluster funzionali emergenti.
- La Φ (coerenza) è una metrica globale, non risolta per comunità.

**Azione Raccomandata:**
- Aggiungere **CommunityDetectionEngine** alla roadmap futura:
  - Durante il runtime, raggruppare neuroni con pattern di attivazione correlati.
  - Assegnare "community embeddings" che evolvano nel tempo.
  - Usare le comunità per guidare la neurogenesi (aggiungere neuroni in comunità deboli) e l'apoptosi (rimuovere neuroni isolati).
- Questo introduce un livello di organizzazione *mesoscopico* tra neurone singolo e circuito globale.

---

## Insight 10 — Meta-Learning e Self-Reflection (da Bio-Inspired Framework)

**Cosa fa il Markdown NeuroEvolve:**
- Modulo di **Meta-Learning** basato su LSTM che:
  - Valuta la confidenza delle decisioni del sistema.
  - Modifica il reward signal in base alla confidenza (simula introspezione).
  - Usa il contesto temporale per migliorare le decisioni nel tempo.

**Stato SPEACE:**
- Il feedback è esterno (`feedback(score: float)`).
- Non esiste un meccanismo di self-evaluation o confidence scoring interno.

**Azione Raccomandata:**
- Aggiungere **ConfidenceEvaluator** alla roadmap futura:
  - Misurare la "decision confidence" come varianza dell'attivazione degli output neuron.
  - Bassa confidenza → trigger per neurogenesi (il sistema è incerto, ha bisogno di più capacità).
  - Alta confidenza + errore → trigger per pruning / riorganizzazione (sovradattamento).

---

## Mappatura sugli Task SPEACE Esistenti e Futuri

### Task v0.2 Correnti

| Task | Impatto dell'Analisi NeuroEvolve |
|---|---|
| **T7 — MorphologicalMemory** | Confermato. FEAGI usa InfluxDB/Grafana per time-series. SPEACE usa JSONL. Futuro: considerare time-series DB per scalabilità. |
| **T8 — NeurogenesisEngine** | Da potenziare con: growth rules spaziali, integrazione in comunità, vincolo energetico attivo, posizionamento morfologico. |
| **T9 — ApoptosisEngine** | Da implementare con: pruning basato su peso sinaptico (come FEAGI), rimozione di neuroni isolati, snooze come forma di "disattivazione temporanea". |
| **T10 — CellDifferentiationEngine** | Allineato con FEAGI: il genoma definisce densità e morfologie per strato. La differenziazione dovrebbe usare regole di crescita geometriche. |
| **T11 — NeuroFunctionalBenchmark** | Aggiungere metriche: tempo di comprensione (ms), footprint storage, efficienza energetica simulata, fitness evolutiva. |

### Nuovi Task Proposti per v0.3 / Roadmap Futura

| Codice | Task | Priorità | Motivazione |
|---|---|---|---|
| **T12** | **EventDrivenBurstEngine** | Alta | Sostituire tick globale con fire candidate list. Fondamentale per scalabilità e STDP. |
| **T13** | **STDPPlasticityEngine v2** | Alta | Plasticità causale basata su differenza di tick/burst tra pre e post. |
| **T14** | **InhibitoryNeuron & Snooze** | Alta | Stabilità di rete, prevenzione runaway, biologia plausibile. |
| **T15** | **GenomeDatabase & EvolutionEngine** | Media-Alta | Chiudere il loop evolutivo genotipo-fenotipo. |
| **T16** | **SemanticMemory / CellAssembly** | Media | Fondamento per cognizione e memoria associativa. |
| **T17** | **CommunityDetectionEngine** | Media | Organizzazione mesoscopica del circuito. |
| **T18** | **EnergyControlAgent** | Media | Ottimizzazione energetica attiva, pruning sotto stress metabolico. |
| **T19** | **MetaLearningConfidence** | Bassa | Introspezione e self-reflection. |

---

## Principi Guida Estratti

1. **"To be inspired by the brain but not to imitate it"** (FEAGI). SPEACE non deve replicare ogni dettaglio biologico, ma catturare i *principi* (plasticità, evoluzione, sparsità, energia).
2. **"Evolution over Engineering"**. La struttura ottimale non è progettata a tavolino, ma emergente attraverso mutazione, selezione e fitness.
3. **"Sparsity is Scalability"**. Simulare solo i neuroni attivi (burst engine) è la chiave per passare da 1000 a 100M neuroni.
4. **"Structure remembers"**. La memoria non è solo un database di eventi (T7), ma è impressa nella *struttura* del circuito attraverso LTP/LTD e cell assemblies.
5. **"Energy is a first-class citizen"**. Il metabolismo non è un effetto collaterale ma un vincolo attivo che modula neurogenesi, plasticità e pruning.

---

## Conclusione

L'analisi dei documenti NeuroEvolve/FEAGI conferma che SPEACE è sulla traiettoria corretta (genoma, neurogenesi, memoria morfologica, glia), ma evidenzia tre grandi direzioni di crescita:

1. **Scalabilità computazionale**: passare dal tick globale al burst engine event-driven.
2. **Plausibilità biologica**: aggiungere inibizione, STDP causale, periodo refrattario, snooze.
3. **Chiusura del loop evolutivo**: evolvere il genoma attraverso generazioni con fitness, mutation e crossover.

Il framework FEAGI è il più rilevante perché condivide l'architettura genoma-connectome e l'obiettivo di un sistema *crescente* piuttosto che *progettato*. Le tecniche di grafo dinamico (fMRI paper) e le meta-euristiche brain-inspired (BI-DE) offrono invece strumenti matematici per ottimizzazione e clustering da integrare in task futuri.

**Prossimo passo consigliato:** procedere con T9 (ApoptosisEngine) e T10 (CellDifferentiationEngine) arricchendoli con i principi di pruning energetico e regole di crescita spaziale, poi pianificare T12 (BurstEngine) come gateway verso la scalabilità v0.3.
