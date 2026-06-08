# T48 — Episodic-Guided Self-Improvement Policy

## Overview

T48 integra la memoria episodica (T47) nel ciclo di auto-miglioramento (T45/T46). Il `SelfImprovementLoop` non propone più task solo in base alla limitazione corrente, ma consulta episodi storici simili per guidare la selezione delle proposte architetturali.

## Design Principles

- **Historically situated**: Ogni decisione di auto-miglioramento è informata da episodi passati.
- **Non-destructive**: Le proposte originali non vengono modificate; viene aggiunto un layer di ranking.
- **Observable**: Tutte le fasi della policy vengono loggate in MorphologicalMemory.
- **Conservative**: Le penalità per episodi di regressione sono più forti dei bonus per recovery.

## Architecture

### Models

- `EpisodicPolicyContext` — Riassume il contesto episodico per un dato `limitation_type`:
  - count di episodi simili/recovery/regression/semantic/self-improvement
  - pattern di recovery e precursori di regressione
  - modificatori di confidenza e rischio

- `EpisodicProposalAdjustment` — Modifica applicata a una proposta:
  - `original_confidence` / `adjusted_confidence`
  - `episodic_bonus` / `episodic_penalty`
  - `reasons` (lista di stringhe descrittive)

### Engine

- `EpisodicSelfImprovementPolicy`
  - `build_context(limitation_type, current_metrics)` — recupera episodi simili e calcola statistiche
  - `adjust_proposals(proposals, context)` — applica bonus/penalty in base a:
    - linked recovery episodes (+0.10)
    - limitation_type già risolta (+0.05)
    - linked regression episodes (-0.10)
    - regression precursor non mitigato (-0.05)
    - semantic learning episode con net gain positivo (+0.05)
    - clamp finale in [0, 1]
  - `select_best_proposal(proposals, context)` — restituisce la proposta con `adjusted_confidence` massimo

### Integration with SelfImprovementLoop

Il `SelfImprovementLoop` è stato esteso con:

- `episodic_policy_enabled: bool = False`
- `episodic_policy: Optional[EpisodicSelfImprovementPolicy]`

Nel ciclo:
1. detect limitation
2. generate proposals
3. **T48** — if enabled: `build_context` → `adjust_proposals` → reorder proposals by adjusted confidence
4. simulate/evaluate
5. accept/reject
6. record outcome

Il risultato `SelfImprovementCycleResult` include ora:
- `episodic_context: Optional[Dict]`
- `episodic_adjustments: List[Dict]`

Il report Markdown include le sezioni:
- `## Episodic Policy Context`
- `## Episodic Proposal Adjustments`

### Orchestrator Integration

- `episodic_policy_enabled: bool = False`
- `get_self_improvement_loop()` crea l'`EpisodicSelfImprovementPolicy` con `get_episodic_recall()` quando il flag è attivo.

### Event Types

- `EPISODIC_POLICY_CONTEXT_BUILT`
- `EPISODIC_POLICY_PROPOSAL_ADJUSTED`
- `EPISODIC_POLICY_RECOVERY_BONUS_APPLIED`
- `EPISODIC_POLICY_REGRESSION_PENALTY_APPLIED`
- `EPISODIC_POLICY_PROPOSAL_SELECTED`

### Benchmark Metrics

- `episodic_policy_enabled`
- `episodic_context_episode_count`
- `episodic_recovery_context_count`
- `episodic_regression_context_count`
- `episodic_policy_bonus_mean`
- `episodic_policy_penalty_mean`
- `episodic_adjusted_confidence`
- `episodic_policy_selected_proposal_score`

## Acceptance Criteria

- Il loop usa la policy episodica quando `episodic_policy_enabled=True`.
- Le proposte vengono ricalibrate da episodi di recovery/regression.
- Il report di self-improvement mostra il contesto episodico usato.
- Nessuna proposta viene auto-applicata senza gating/simulation.
- Tutti i test esistenti restano verdi; nuovi test >= 22 passano.
- Coverage >= 85%.

## Version

v0.3.37-t48-episodic-guided-self-improvement-policy
