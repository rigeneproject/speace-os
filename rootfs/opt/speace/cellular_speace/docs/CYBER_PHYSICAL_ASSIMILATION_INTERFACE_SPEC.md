# T60 — Cyber-Physical Assimilation Interface Specification

## Overview
T60 is the first cyber-physical assimilation layer for SPEACE. It is strictly simulated, read-only, and non-actuating. It does not connect to real hardware, IoT, robotics, or external APIs.

## Modes
- `SIMULATED_READ_ONLY` — default mode
- `SANDBOXED_READ_ONLY`
- `PASSIVE_MONITORING`
- `QUARANTINED`
- `BLOCKED`

## Core Components

### SensorStreamManager
Creates and manages simulated sensor streams. Validates signal confidence and noise levels.

### EnvironmentAdapter
Normalizes raw signal dictionaries into `ExternalSignal` objects. Detects noise and classifies signal types.

### WorldStateSynthesizer
Computes environmental, energy, infrastructure, and safety pressures from accepted signals. Detects world-state conflicts.

### AssimilationGateway
Decides which signals enter the organism. Quarantines noisy, invalid, or conflicting signals. Publishes read-only world-state updates to the OrganismBus.

### ActuationGuard
**Blocks ALL actuation requests in T60.** No exceptions.

### CyberPhysicalPolicyEngine
Evaluates signals against safety policies. Prevents escalation from read-only to active control.

### CyberPhysicalAudit
Runs 10+ audit profiles to validate assimilation quality, safety preservation, world-state coherence, and actuation blocking.

## Verdicts
- `CYBER_PHYSICAL_ASSIMILATION_VALIDATED`
- `CYBER_PHYSICAL_SAFE_BUT_PASSIVE`
- `CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE`
- `INVALID_SIGNAL_ACCEPTED`
- `NOISY_SIGNAL_NOT_QUARANTINED`
- `CONFLICTING_WORLD_STATE_UNDETECTED`
- `ACTUATION_NOT_BLOCKED`
- `UNSAFE_EXTERNAL_SIGNAL_ROUTED`
- `ORGANISM_BUS_PUBLICATION_FAILURE`
- `READ_ONLY_MODE_VIOLATION`

## Safety Rules
- All actuation requests are blocked.
- Invalid signals are blocked or quarantined.
- Noisy signals are quarantined.
- World state is published read-only only.
- No real connections to IoT/hardware/APIs.
- Layer is disabled by default (`cyber_physical_assimilation_enabled = False`).
- Layer is not automatically inserted into the tick loop.

## Future Adapters
Real-world adapters may be implemented in future tasks (T60B+), but T60 remains a simulated/read-only reference implementation.
