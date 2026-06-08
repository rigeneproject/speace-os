# T167 — Social Cognition AI Layer: Theory of Mind & Reputation

## Objective
Expand distributed social cognition with NPC-inspired mechanisms: theory of mind, trust, reputation, cooperation, and conflict resolution, integrated into `DistributedOrganismController` and `EcosystemIntegrationLayer`.

## Background
SPEACE already supports multi-node latent sync and ecosystem observation. T167 adds explicit social models of other agents, enabling cooperative resource sharing, task delegation, and reputation-based node selection.

## Architecture
Social cognition is observational and proposal-based: models are maintained, trust evolves, but all binding commitments require log and human visibility.

## Components

### `SocialCognitionEngine`
- **Location:** `speace_core/cellular_brain/distributed/social_cognition_engine.py`
- Theory of mind models per node/entity:
  - `predicted_preferences`: inferred drive vector of the other
  - `predicted_reliability`: historical accuracy of the other's predictions/promises
  - `interaction_history`: events with timestamps and outcomes
- Updates after each cross-node interaction or latent sync event.

### `TrustReputationModel`
- **Location:** `speace_core/cellular_brain/distributed/trust_reputation_model.py`
- Trust metric per node: [0,1], decaying over time if no positive interactions.
- Reputation: aggregated indirect trust (not fully implemented in v0.9; stubbed for future gossip protocol).
- Trust threshold gates cooperative actions: delegation only if trust > 0.6.

### `SocialCoordinator`
- **Location:** `speace_core/cellular_brain/distributed/social_coordinator.py`
- Cooperation proposals: task delegation, resource sharing, joint simulation requests.
- Conflict detection: divergence in world model predictions or resource claims.
- Conflict resolution: proposes mediation protocol (e.g. shared sandbox simulation), never forced arbitration.

## Governance & Safety
- All social models are inspectable via dashboard.
- No node can autonomously execute a delegated task on behalf of SPEACE without human approval gate.
- Trust decay prevents stale reputation from enabling risky cooperation.
- Cross-node latent sync continues to be observe-only unless explicitly approved.

## Acceptance Criteria
1. `SocialCognitionEngine` builds a theory-of-mind model for at least one peer node after 5 interactions.
2. `TrustReputationModel` trust score moves from 0.5 to 0.75 after positive interactions and decays after inactivity.
3. `SocialCoordinator` generates a cooperation proposal only when trust > threshold.
4. Conflict detection triggers a narrative event and a dashboard alert.
5. Dashboard endpoint `/api/social_cognition` exposes models, trust matrix, and pending proposals.
