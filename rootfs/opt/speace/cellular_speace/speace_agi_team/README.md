# SPEACE AGI Team

**Sistema di agentic AI dedicato all'evoluzione di SPEACE verso l'AGI.**

## 1. Missione

Costruire, supervisionare e far evolvere il cervello digitale neurocellulare e l'organismo
distribuito di SPEACE tramite un team di agenti AI specializzati, coordinati da un
piano ingegneristico strategico iterativo.

Obiettivo finale: **raggiungere uno stato AGI** (auto-riprogettazione, auto-coscienza,
ragionamento astratto ricorsivo, apprendimento trasferibile).

## 2. Architettura del team

### 2.1 Livello strategico — Supervisor Agents (6)

| ID | Nome | Responsabilità |
| --- | --- | --- |
| `chief_architect` | Chief AGI Architect | Coordina i supervisor, definisce la roadmap, integra i piani |
| `brain_supervisor` | Brain Supervisor | Supervisiona neuroni, sinapsi, 8 regioni cerebrali, STDP, brainstem |
| `dna_supervisor` | DNA Supervisor | Genoma, epigenetica, mutazioni, differenziazione cellulare |
| `organism_supervisor` | Organism Supervisor | Metabolismo, immunità, embodiment, assimilazione |
| `memory_supervisor` | Memory Supervisor | Memoria morfologica, episodica, semantica, metacognizione |
| `selfimprovement_supervisor` | Self-Improvement Supervisor | Cicli evolutivi, multi-cycle runner, limitation detection |

### 2.2 Livello esecutivo — Technical Agents (10)

| ID | Nome | Dominio tecnico |
| --- | --- | --- |
| `neuron_tech` | Neuron Technician | Creazione/firing/apoptosi/neurogenesi dei neuroni |
| `synapse_tech` | Synapse Technician | Plasticità STDP, pruning, mielinizzazione |
| `region_tech` | Region Technician | 8 regioni cerebrali, routing inter-regionale |
| `genome_tech` | Genome Technician | DNA digitale, mutazioni, crossover, espressione |
| `runtime_tech` | Runtime Technician | ContinuousRuntimeEngine, ciclo circadiano, checkpoint |
| `defense_tech` | Defense Technician | CellularStress, Damage, Defense, Repair, Epigenetic |
| `memory_tech` | Memory Technician | Memoria morfologica, episodica, semantica |
| `evolution_tech` | Evolution Technician | SelfImprovementLoop, EDD-CVT kernel |
| `network_tech` | Network Technician | Ecosystem boundary, trust governor, adapter |
| `embodiment_tech` | Embodiment Technician | Sensori cyber-fisici, attuatori, modello ambientale |

### 2.3 Flusso di coordinamento

```
┌─────────────────────────────────────────────────────────────┐
│  ChiefArchitect (strategic coordinator)                     │
│  • Definisce e aggiorna la roadmap                          │
│  • Integra output dei supervisor                            │
│  • Identifica gap critici verso AGI                         │
└────────────────────┬────────────────────────────────────────┘
                     │ delega + raccoglie
       ┌─────────────┼──────────────┬──────────────┐
       ▼             ▼              ▼              ▼
  BrainSup.   DNASup.   OrganismSup.   MemorySup.   SelfImpSup.
       │             │              │              │
       │ (assegna task e raccoglie analisi)         │
       ▼             ▼              ▼              ▼
  [NeuronTech, SynapseTech, RegionTech]            │
  [GenomeTech]                                     │
  [RuntimeTech, DefenseTech, EmbodimentTech]      │
  [MemoryTech]                                     │
  [EvolutionTech, NetworkTech]                    ─┘
```

Il flusso è:
1. **Supervisor analizza** lo stato della propria area
2. **Supervisor assegna task** ai tecnici tramite EngineeringPlan
3. **Tecnici eseguono / analizzano / correggono** usando il LLM
4. **Risultati** vengono aggregati nel piano ingegneristico
5. **Chief Architect** rivaluta e aggiorna la roadmap

## 3. Componenti software

```
speace_agi_team/
├── __init__.py            # Entry point package
├── config.py              # Configurazione Ollama Cloud + AgentConfig
├── agent_base.py          # Classe base AgentBase (chat, analyze, tasks)
├── supervisor_agents.py   # 6 supervisor specializzati
├── technical_agents.py    # 10 tecnici specializzati
├── engineering_plan.py    # Piano ingegneristico con milestone M0-M8
├── web_server.py          # FastAPI: REST API + WebSocket + Dashboard
├── main.py                # CLI launcher
├── data/
│   └── engineering_plan.json  # Stato persistente del piano
└── static/                # Frontend Dashboard
    ├── index.html         # UI principale
    ├── style.css          # Stili
    └── app.js             # Logica client
```

## 4. Piano ingegneristico — 9 Milestone

| ID | Titolo | Stato | Agenti coinvolti |
| --- | --- | --- | --- |
| M0 | Foundation: Runtime & Brain Active | in_progress (65%) | runtime, neuron, synapse |
| M1 | Regional Brain Architecture | in_progress (50%) | region, brain_sup |
| M2 | Genome & Evolution Pipeline | in_progress (40%) | genome, evolution, dna_sup |
| M3 | Memory Systems Integration | in_progress (35%) | memory, memory_sup |
| M4 | Self-Improvement Loop | planned (15%) | evolution, selfimp_sup |
| M5 | Organism Homeostasis & Immune | planned (20%) | defense, embodiment, organism_sup |
| M6 | Ecosystem & External Integration | planned (10%) | network, organism_sup |
| M7 | Cognitive Architecture & Workspace | planned (5%) | memory, brain_sup, chief |
| M8 | AGI Emergence | planned (0%) | chief_architect |

## 5. Configurazione LLM

Tutti gli agenti usano:
- **Modello**: `minimax-m3:cloud` (via Ollama Cloud)
- **Endpoint**: `https://ollama.com`
- **API key**: configurata in `config.py`
- **Temperature**: 0.3 (bassa per output deterministici)
- **Max tokens**: 4096

## 6. Avvio

### Server web (dashboard + chat)

```bash
cd speace_agi_team
python -m speace_agi_team.main --port 8686
```

Apri `http://127.0.0.1:8686` per accedere alla dashboard.

### Endpoint REST principali

- `GET  /api/status` — stato sistema
- `GET  /api/agents` — lista agenti
- `GET  /api/agents/{id}` — dettaglio agente
- `GET  /api/agents/{id}/conversation` — storico chat
- `POST /api/agents/{id}/chat` — chat con un agente
- `POST /api/agents/{id}/analyze` — analisi automatica del contesto SPEACE
- `POST /api/agents/{id}/clear` — pulisci conversazione
- `POST /api/broadcast` — broadcast a tutti gli agenti
- `GET  /api/speace/context` — stato live di SPEACE
- `GET  /api/plan` — stato del piano ingegneristico
- `POST /api/plan/task` — aggiungi task
- `POST /api/plan/task/{id}/complete` — completa task
- `POST /api/plan/milestone/{id}` — aggiorna milestone
- `WS   /ws` — WebSocket per notifiche real-time

## 7. Come interagire

1. Aprire la dashboard
2. Tab **Agents**: filtrare per tipo, lanciare broadcast o analisi automatica
3. Tab **Chat**: selezionare un supervisor e dargli istruzioni / domande
4. Tab **Plan**: aggiungere task, marcare come completati, vedere milestone
5. Tab **SPEACE Context**: vedere lo stato live di SPEACE (cervello, ambiente, genoma)

### Esempio di istruzione al Chief Architect via chat

> "Dai priorità al milestone M4 (Self-Improvement Loop) e crea 3 task
> per il supervisor selfimprovement_supervisor, mirati a verificare il
> limitation detector e attivare il kernel evolutivo."

## 8. Estensione

Per aggiungere un nuovo supervisore o tecnico:

1. Creare la classe in `supervisor_agents.py` o `technical_agents.py`
2. Aggiungerla alla lista in `register_supervisors()` / `register_technicians()`
3. Aggiungerla al dizionario in `web_server.py:_build_agents()`
4. Riavviare il server

Per aggiungere un nuovo milestone al piano:

1. Modificare la lista `MILESTONES` in `engineering_plan.py`
2. Oppure aggiornare tramite `POST /api/plan/milestone/{id}`

## 9. Note di sicurezza

- Ogni azione su SPEACE passa per il sistema di governance
  (`speace_core/cellular_brain/action_governance/`)
- Le mutazioni del genoma sono sempre valutate dal sandbox controfattuale
- I supervisor non possono modificare direttamente il codice di SPEACE;
  emettono task e raccomandazioni
- Il broadcast è usato per messaggi informativi; non sostituisce
  l'approvazione umana per azioni ad alto rischio
