# SPEACE Evolution Daemon

The **Evolution Daemon** is a 14-task cyclic supervisor that runs alongside SPEACE,
emitting benchmarks, diagnostics, refactor proposals, knowledge-graph updates, and
an engineering plan for the path to AGI. It is *advisory*: it never mutates SPEACE
source code or runtime state without human approval (T104 governance).

## Quickstart

```bash
# Run one cycle and exit (smoke test)
python scripts/start_evolution_daemon.py --once

# Run forever
python scripts/start_evolution_daemon.py

# Skip launching the web dashboards
python scripts/start_evolution_daemon.py --no-dashboards
```

The daemon listens on two web dashboards:

| Service           | Default port | Auto-fallback             |
|-------------------|--------------|---------------------------|
| Main dashboard    | `5692`       | `5693 → 5694 → 5695`      |
| Neuron dashboard  | `5697`       | `5698 → 5699 → 5700`      |

If a port is busy, the daemon automatically picks the next free one. The actual
ports are logged and written to `data/daemon_state.json`.

## Endpoints

### Main dashboard (`http://127.0.0.1:5692/`)

| Route                | Description |
|----------------------|-------------|
| `GET /api/health`    | Liveness probe |
| `GET /api/state`     | Last daemon state + last cycle digest |
| `GET /api/agi`       | Current AGI % + components + weights |
| `GET /api/cognition` | Cognitive capabilities digest |
| `GET /api/diagnostics` | Per-compartment health |
| `GET /api/tasks`     | Recent task list |
| `GET /api/plan`      | Engineering plan toward AGI |
| `GET /api/knowledge` | Knowledge graph nodes + edges |
| `GET /api/cycles`    | Recent cycle digests |

### Neuron dashboard (`http://127.0.0.1:5697/`)

| Route                       | Description |
|-----------------------------|-------------|
| `GET /api/health`           | Liveness probe |
| `GET /api/neurons`          | Current neuron counts + history |
| `GET /api/synapses`         | Current synapse counts + history |
| `GET /api/activation_matrix`| Activation distribution per tick |

## The 14-task cycle

| # | Task                                      | Module(s)                                |
|---|-------------------------------------------|------------------------------------------|
| 1 | Start the brain + organism runtime        | `daemon._step_runtime`                  |
| 2 | Run benchmark → AGI %                     | `benchmark_runner`                       |
| 3 | Analyse cognition                         | `state_collector.analyze_cognition`      |
| 4 | Propose refactors                         | `mutation_engine`                        |
| 5 | Evaluate fitness / optimisation           | `fitness_evaluator`                      |
| 6 | Run ARC-AGI subset                        | `arc_runner`                             |
| 7 | Diagnose compartments                     | `state_collector.diagnose_compartment`   |
| 8 | Track neurons / synapses                  | `state_collector.neuron_synapse_stats`   |
| 9 | Detect errors → log + proposal            | `mutation_engine`                        |
| 10| Generate next-iteration tasks             | `task_generator`                         |
| 11| Update Knowledge Graph                    | `knowledge_graph`                        |
| 12| Regenerate Engineering Plan               | `engineering_plan`                       |
| 13| Review diffs for regressions              | `regression_reviewer`                    |
| 14| Loop                                      | `EvolutionDaemon.run_forever`            |

## AGI % formula

```text
AGI% = 100 × Σᵢ wᵢ · componentᵢ    with
       Σᵢ wᵢ = 1,  componentᵢ ∈ [0, 1]
```

| Component                    | Weight |
|------------------------------|--------|
| `adaptation_after_error`     | 0.20   |
| `arc_agi_subset`             | 0.25   |
| `useful_neurogenesis`        | 0.15   |
| `morphological_memory_trace` | 0.10   |
| `regulation_stability`       | 0.10   |
| `useful_apoptosis`           | 0.10   |
| `differentiation_consistency`| 0.10   |

## Persistent artefacts

All artefacts are written under `data/`:

| Path                                                | Description                       |
|-----------------------------------------------------|-----------------------------------|
| `data/daemon_state.json`                            | Daemon digest (last cycle)        |
| `data/daemon_tasks.jsonl`                           | Task log (per cycle)              |
| `data/engineering_plan.json`                        | AGI engineering plan              |
| `data/knowledge_graph.jsonl`                        | Knowledge graph nodes/edges       |
| `data/evolution_daemon/cycles.jsonl`                | Full cycle digests                |
| `data/evolution_daemon/benchmarks/latest.json`      | Latest AGI report                 |
| `data/evolution_daemon/arc/latest.json`             | Latest ARC pass report            |
| `data/evolution_daemon/epigenetic_state.json`       | Epigenetic marks                  |
| `data/self_improvement/proposals.jsonl`             | Refactor / DNA / error proposals  |

## Governance

The daemon **never** auto-applies code or DNA changes (T104+). Every proposal
is marked `auto_apply=false` and `status=pending_human_approval`. Review
proposals in `data/self_improvement/proposals.jsonl` and apply manually.

## Loop integration

The 14-task cycle is meant to be invoked every ~270 s (cache-friendly) from a
`/loop` scheduler:

```python
# In a /loop wake
1. Ensure the daemon subprocess is alive (or start it).
2. Curl the dashboards for the current AGI % and diagnostics.
3. Spawn a subagent to interpret the result and propose follow-up actions.
4. ScheduleWakeup(270s, prompt) to re-enter the loop.
```

## Tests

```bash
python -m pytest evolution_daemon/tests/ -v
```

The smoke tests verify the 14-step pipeline without booting the full SPEACE
runtime. They run in ~20 s.
