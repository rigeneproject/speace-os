# T32 — Deep Region Functional Audit v0.3 — Specification

## Overview

T31 added 4 new deep regions (limbic, cerebellar, default_mode, brainstem_homeostatic) extending the architecture from 4 to 8 regions. T32 validates whether these new regions provide functional benefit, remain neutral, or cause regression.

## Objective

Compare at least three configurations:

- **A. 4-region baseline**: sensory → hippocampus → prefrontal → motor
- **B. Deep regions static**: new regions present but routing/plasticity/utility disabled — measures structural cost only
- **C. Deep regions full**: deep regions + routing + plasticity + utility learning — measures complete regional organism

## Key metrics

| Metric | Description |
|--------|-------------|
| cognitive_score_delta | Δ vs baseline |
| phi_delta | Δ vs baseline |
| energy_efficiency_delta | Δ vs baseline |
| functional_improvement_delta | Δ vs baseline |
| pathway_utility_delta | Δ vs baseline |
| deep_region_signal_flow | From DeepRegionSpecialization |
| region_role_alignment_score | From DeepRegionSpecialization |
| region_specialization_diversity | From DeepRegionSpecialization |
| limbic_salience_score | From DeepRegionSpecialization |
| cerebellar_error_correction_score | From DeepRegionSpecialization |
| default_mode_consolidation_score | From DeepRegionSpecialization |
| brainstem_homeostatic_stability_score | From DeepRegionSpecialization |
| deep_region_cost | routing_energy_cost + pathway_energy_cost |
| deep_region_benefit | regional_signal_flow_score + functional_improvement |
| deep_region_net_gain | Weighted composite (see formula) |

## Net gain formula

```
deep_region_net_gain =
  0.30 * cognitive_score_delta
+ 0.25 * phi_delta
+ 0.20 * functional_improvement_delta
+ 0.15 * pathway_utility_delta
+ 0.10 * energy_efficiency_delta
```

## Audit profiles

| ID | Name | deep_regions | routing | plasticity | Notes |
|----|------|--------------|---------|------------|-------|
| d0 | four_region_baseline | No | No | Yes | Baseline |
| d1 | deep_regions_static | Yes | No | No | Structural cost |
| d2 | deep_regions_routing_only | Yes | Yes | No | Routing only |
| d3 | deep_regions_routing_plasticity | Yes | Yes | Yes | Hybrid trigger |
| d4 | deep_regions_full_utility | Yes | Yes | Yes | + T29 tuning + T30 utility |
| d5 | deep_regions_energy_soft | Yes | Yes | Yes | Low energy cost |
| d6 | deep_regions_energy_medium | Yes | Yes | Yes | Medium energy cost |
| d7 | deep_regions_brainstem_priority | Yes | Yes | Yes | High energy modulation |
| d8 | deep_regions_default_mode_low_activity | Yes | Yes | Yes | Lower plasticity rates |
| d9 | deep_regions_limbic_soft_salience | Yes | Yes | Yes | Confidence modulation |

## Verdicts

- **DEEP_REGIONS_VALIDATED** — net gain > 0, no regression
- **DEEP_REGIONS_NEUTRAL** — no regression but no gain
- **DEEP_REGION_ENERGY_REGRESSION** — efficiency drops >20% with cost > 0.01
- **DEEP_REGION_PHI_REGRESSION** — Φ drops >20%
- **DEEP_REGION_COGNITIVE_REGRESSION** — cognitive score drops >20%
- **DEEP_REGION_NO_EFFECT** — signal flow > 0 but no functional delta
- **INSUFFICIENT_EVIDENCE** — all profiles failed or no deep region data

## Files

- `speace_core/cellular_brain/analysis/deep_region_audit.py` — core auditor
- `tests/analysis/test_deep_region_audit.py` — 18 tests
- `docs/DEEP_REGION_FUNCTIONAL_AUDIT_SPEC.md` — this document
- `reports/deep_regions/` — generated reports

## Acceptance criteria

- [x] `DeepRegionAuditor` exists and is importable
- [x] 10 default profiles defined including 4-region baseline
- [x] `run_profile` executes a single configuration
- [x] `run_audit_suite` compares baseline vs deep-region configs
- [x] Net gain computed with the specified formula
- [x] Verdict logic covers all 7 states
- [x] JSON and Markdown reports generated
- [x] Tests pass, coverage ≥ 85%
- [x] No regression on existing tests
- [x] Commit and tag created

## Post-T32 next step

Use the verdict to decide T33:

- `DEEP_REGIONS_VALIDATED` → T33 Deep Region Functional Enhancement
- `DEEP_REGIONS_NEUTRAL` → T33 Deep Region Routing Calibration
- `DEEP_REGION_ENERGY_REGRESSION` → T33 Brainstem Energy Arbitration
- `DEEP_REGION_PHI_REGRESSION` → T33 Region-Level Stability Controller
- `DEEP_REGION_COGNITIVE_REGRESSION` → T33 Deep Region Role Rebalancing
- `DEEP_REGION_NO_EFFECT` → T33 Deep Region Activation Redesign
- `INSUFFICIENT_EVIDENCE` → increase n_adaptive_cycles and re-run
