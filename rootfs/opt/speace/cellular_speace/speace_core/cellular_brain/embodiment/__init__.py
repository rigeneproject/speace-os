"""Embodiment layer — the body senses and muscles of SPEACE."""

from speace_core.cellular_brain.embodiment.body_registry import BodyRegistry
from speace_core.cellular_brain.embodiment.body_router import BodyRouter
from speace_core.cellular_brain.embodiment.causal_learning_auditor import (
    CausalLearningAuditor,
)
from speace_core.cellular_brain.embodiment.cross_body_sensorimotor_coordinator import (
    CrossBodySensorimotorCoordinator,
)
from speace_core.cellular_brain.embodiment.passive_multisensory_observer import (
    PassiveMultisensoryObserver,
)
from speace_core.cellular_brain.embodiment.cyber_physical_sensor_array import (
    CyberPhysicalSensorArray,
)
from speace_core.cellular_brain.embodiment.digital_twin_model import DigitalTwinModel
from speace_core.cellular_brain.embodiment.distributed_organism_controller import (
    DistributedOrganismController,
)
from speace_core.cellular_brain.embodiment.embodied_action_actuator import (
    EmbodiedActionActuator,
)
from speace_core.cellular_brain.embodiment.embodiment_monitor import (
    EmbodimentMonitor,
)
from speace_core.cellular_brain.embodiment.physical_environment_model import (
    PhysicalEnvironmentModel,
)
from speace_core.cellular_brain.embodiment.micro_actuator_controller import (
    MicroActuatorController,
)
from speace_core.cellular_brain.embodiment.simulated_environment_engine import (
    SimulatedEnvironmentEngine,
)

__all__ = [
    "BodyRegistry",
    "BodyRouter",
    "CausalLearningAuditor",
    "CrossBodySensorimotorCoordinator",
    "CyberPhysicalSensorArray",
    "DigitalTwinModel",
    "DistributedOrganismController",
    "EmbodiedActionActuator",
    "MicroActuatorController",
    "PassiveMultisensoryObserver",
    "PhysicalEnvironmentModel",
    "EmbodimentMonitor",
    "SimulatedEnvironmentEngine",
]
