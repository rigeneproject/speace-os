# T165 — Utility AI Layer: Dynamic Drive System

## Objective
Create a biological-style dynamic utility drive system that arbitrates which cognitive processes receive priority, modeling motivational systems (exploration, stability, rest, social interaction, prediction-error reduction, energy conservation).

## Background
Current regulation is reactive (homeostasis engine). T165 adds proactive **drive-based arbitration**: a continuous vector of utilities that shifts resource allocation and workspace attention, analogous to biological motivational states.

## Architecture
Drive values are dynamic [0,1] scalars updated each tick based on homeostasis, narrative, curiosity, causal world model, and organism state. An arbitration engine uses these utilities to weight module scheduling and global workspace attention.

## Components

### `UtilityDriveSystem`
- **Location:** `speace_core/cellular_brain/regulation/utility_drive_system.py`
- Drives:
  - `exploration` — fueled by curiosity score, novelty, prediction error
  - `stability` — fueled by coherence, low noise, homeostatic balance
  - `rest` — fueled by low energy, circadian night phase, high load
  - `social_interaction` — fueled by dialogue recency, distributed node presence
  - `prediction_error_reduction` — fueled by high prediction error, causal model uncertainty
  - `energy_conservation` — fueled by high metabolism cost, low energy
- Update rule: leaky integration with inputs. `drive_new = leak * drive_old + (1-leak) * input_vector`. Clamped [0,1].
- Drive interactions: cross-inhibition (e.g. high `rest` suppresses `exploration`).

### `UtilityArbitrationEngine`
- **Location:** `speace_core/cellular_brain/regulation/utility_arbitration_engine.py`
- Reads drive vector and current `OrganismStateMachine` state.
- Outputs `module_priority_weights`: dict mapping module_id → weight [0,1].
- Example: if `stability > 0.7`, boost `HomeostasisEngine` and `CausalLearningAuditor` weights; if `exploration > 0.6`, boost `InfantCuriosityLayer` and `CyberPhysicalSensorArray` sampling rate.
- Feeds weights into `GlobalWorkspace` attention routing.

## Governance & Safety
- Utilities are **fully observable**: dashboard exposes real-time drive plots.
- Drive arbitration **cannot** disable safety modules (EmergencyHaltGate, CausalLearningAuditor) or reduce their weight below a floor.
- No drive can force autonomous action execution; drives only weight proposals and scheduling.

## Acceptance Criteria
1. Six drive variables evolve plausibly over a 100-tick simulation with varying inputs.
2. `UtilityArbitrationEngine` produces module weights that sum to 1.0 (normalized).
3. High `rest` drive demonstrably reduces `InfantCuriosityLayer` scheduling frequency.
4. All drive values and weights are exposed via dashboard endpoint `/api/utility_drives`.
5. Cross-inhibition prevents simultaneous maxing of `exploration` and `rest`.
