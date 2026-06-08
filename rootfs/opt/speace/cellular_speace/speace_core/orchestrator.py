import asyncio
import random
import time
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.embodiment.cyber_physical_sensor_array import (
    CyberPhysicalSensorArray,
)
from speace_core.cellular_brain.embodiment.physical_environment_model import (
    PhysicalEnvironmentModel,
)
from speace_core.cellular_brain.embodiment.embodied_action_actuator import (
    EmbodiedActionActuator,
)
from speace_core.cellular_brain.embodiment.embodiment_monitor import (
    EmbodimentMonitor,
)
from speace_core.cellular_brain.base.digital_signal import DigitalSignal
from speace_core.cellular_brain.cells.digital_astrocyte import DigitalAstrocyte
from speace_core.cellular_brain.cells.digital_microglia import DigitalMicroglia
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_oligodendrocyte import DigitalOligodendrocyte
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.regulation.apoptosis_engine import ApoptosisEngine
from speace_core.cellular_brain.regulation.cell_differentiation_engine import (
    CellDifferentiationEngine,
)
from speace_core.cellular_brain.regulation.homeostasis_engine import (
    HomeostasisEngine,
    SystemMetrics,
)
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_snapshot import MorphologySnapshot
from speace_core.cellular_brain.execution.burst_engine import EventDrivenBurstEngine
from speace_core.cellular_brain.regulation.neurogenesis_engine import NeurogenesisEngine
from speace_core.cellular_brain.regulation.plasticity_engine import PlasticityEngine
from speace_core.cellular_brain.analysis.community_detection_engine import (
    CommunityDetectionEngine,
    CommunityDetectionResult,
)
from speace_core.cellular_brain.metacognition.confidence_engine import (
    ConfidenceEngine,
    ConfidenceState,
)
from speace_core.cellular_brain.regulation.energy_control_agent import EnergyControlAgent
from speace_core.cellular_brain.regulation.inhibition_engine import InhibitionEngine
from speace_core.cellular_brain.regulation.stdp_plasticity_engine import STDPPlasticityEngine
from speace_core.cellular_brain.regions.region_registry import RegionRegistry
from speace_core.cellular_brain.regions.region_factory import RegionFactory
from speace_core.cellular_brain.regions.inter_region_plasticity import InterRegionPlasticityEngine
from speace_core.cellular_brain.regions.region_signal_router import (
    RegionSignalRouter,
    RegionRoutingResult,
)
from speace_core.cellular_brain.regions.region_stability_controller import (
    RegionLevelStabilityController,
)
from speace_core.cellular_brain.regions.deep_region_routing_calibrator import (
    DeepRegionRoutingCalibrator,
    DeepRegionRoutingProfile,
)
from speace_core.cellular_brain.regions.brainstem_controller import BrainstemFunctionalController
from speace_core.cellular_brain.regions.brainstem_gain_controller import (
    AdaptiveBrainstemGainController,
    BrainstemGainUpdateResult,
)
from speace_core.cellular_brain.cells.cellular_stress import CellularStressEngine
from speace_core.cellular_brain.cells.cellular_damage import CellularDamageEngine
from speace_core.cellular_brain.cells.cellular_repair_engine import CellularRepairEngine
from speace_core.cellular_brain.cells.cellular_defense_engine import CellularDefenseEngine
from speace_core.cellular_brain.cells.cellular_epigenetic_adapter import CellularEpigeneticAdapter
from speace_core.dna.models import SharedGenome
from speace_core.cellular_brain.runtime.coordinators.memory_coordinator import MemoryCoordinator
from speace_core.cellular_brain.runtime.coordinators.evolution_coordinator import EvolutionCoordinator
from speace_core.cellular_brain.runtime.coordinators.metabolism_coordinator import MetabolismCoordinator
from speace_core.cellular_brain.runtime.coordinators.persistence_coordinator import PersistenceCoordinator
from speace_core.cellular_brain.runtime.subsystem_scheduler import SubsystemScheduler
from speace_core.cellular_brain.runtime.subsystem_context import SubsystemContext, TickState
from speace_core.cellular_brain.sleep.digital_sleep_controller import DigitalSleepController
from speace_core.cellular_brain.immune.digital_immune_controller import DigitalImmuneController
from speace_core.cellular_brain.tool_registry.tool_registry_controller import ToolRegistryController
from speace_core.cellular_brain.identity_kernel.identity_kernel import IdentityKernel
from speace_core.cellular_brain.cognition.global_workspace import GlobalWorkspace
from speace_core.cellular_brain.cognition.linguistic_cognitive_bridge import (
    LinguisticCognitiveBridge,
)
from speace_core.cellular_brain.dynamics.temporal_dynamics_engine import TemporalDynamicsEngine
from speace_core.cellular_brain.dynamics.neural_oscillator_bank import NeuralOscillatorBank
from speace_core.cellular_brain.dynamics.phase_coupling_engine import PhaseCouplingEngine
from speace_core.cellular_brain.dynamics.energy_field_engine import EnergyFieldEngine
from speace_core.cellular_brain.dynamics.predictive_coding_engine import PredictiveCodingEngine
from speace_core.cellular_brain.dynamics.active_inference_engine import ActiveInferenceEngine
from speace_core.cellular_brain.dynamics.global_homeostatic_drive import GlobalHomeostaticDrive
from speace_core.cellular_brain.dynamics.criticality_monitor import CriticalityMonitor
from speace_core.cellular_brain.regulation.emergent_dynamics_stabilizer import EmergentDynamicsStabilizer
from speace_core.cellular_brain.regulation.cognitive_attractor_tracker import CognitiveAttractorTracker
from speace_core.cellular_brain.harmony.systemic_harmony_layer import SystemicHarmonyLayer
from speace_core.cellular_brain.cognition.capability_gap_analyzer import CapabilityGapAnalyzer
from speace_core.monitoring.bottleneck_detector import BottleneckDetector
from speace_core.ilf import GlobalFieldIntegrator, FieldState, ILFMetrics
from speace_core.ilf.field_integrator import FieldAwareMixin

import numpy as np


class CellularBrainOrchestrator(FieldAwareMixin, BaseModel):
    genome: SharedGenome
    circuit: NeuralCircuit
    tick_interval: float = 0.0
    current_tick: int = 0
    metrics_log: List[SystemMetrics] = Field(default_factory=list)

    _homeostasis: HomeostasisEngine = None  # type: ignore[assignment]
    _plasticity: PlasticityEngine = None  # type: ignore[assignment]
    _memory: MorphologicalMemory = None  # type: ignore[assignment]
    _neurogenesis: NeurogenesisEngine = None  # type: ignore[assignment]
    _apoptosis: ApoptosisEngine = None  # type: ignore[assignment]
    _differentiation: CellDifferentiationEngine = None  # type: ignore[assignment]
    _burst_engine: EventDrivenBurstEngine = None  # type: ignore[assignment]
    _stdp: STDPPlasticityEngine = None  # type: ignore[assignment]
    _inhibition: InhibitionEngine = None  # type: ignore[assignment]
    _energy_control: EnergyControlAgent = None  # type: ignore[assignment]
    _inter_region_plasticity: InterRegionPlasticityEngine = None  # type: ignore[assignment]
    _region_signal_router: RegionSignalRouter = None  # type: ignore[assignment]
    _community: CommunityDetectionEngine = None  # type: ignore[assignment]
    _confidence: ConfidenceEngine = None  # type: ignore[assignment]
    negative_feedback_count: int = 0
    execution_mode: str = "global_tick"
    stdp_enabled: bool = True
    inhibition_enabled: bool = True
    energy_control_enabled: bool = True
    inter_region_plasticity_enabled: bool = True
    region_signal_routing_enabled: bool = True
    community_detection_enabled: bool = True
    confidence_enabled: bool = True
    last_community_result: CommunityDetectionResult | None = None
    last_confidence_state: ConfidenceState | None = None
    last_routing_result: RegionRoutingResult | None = None
    neurogenesis_recommended: bool = False
    stabilization_recommended: bool = False
    plasticity_reduction_recommended: bool = False
    region_architecture_enabled: bool = True
    deep_regions_enabled: bool = True
    region_stability_controller_enabled: bool = False
    deep_region_routing_calibrator_enabled: bool = False
    brainstem_controller_enabled: bool = False
    brainstem_gain_controller_enabled: bool = False
    _region_registry: RegionRegistry | None = None
    _region_stability_controller: RegionLevelStabilityController | None = None
    _deep_region_routing_calibrator: DeepRegionRoutingCalibrator | None = None
    _deep_region_routing_profile: DeepRegionRoutingProfile | None = None
    _brainstem_controller: BrainstemFunctionalController | None = None
    _last_brainstem_result = None
    _brainstem_gain_controller = None
    _last_brainstem_gain_result = None
    # T54 — Controlled Perturbation & Recovery Audit
    perturbation_recovery_audit_enabled: bool = False
    _perturbation_recovery_audit = None
    # T55 — EDD-CVT Evolutionary Self-Organization Kernel
    edd_cvt_kernel_enabled: bool = False
    _edd_cvt_kernel = None
    # T57 — Evolutionary Memory Governance Layer
    evolutionary_memory_governance_enabled: bool = False
    _evolutionary_memory_governor = None
    # T58 — Metabolic Resource Governance Layer
    metabolic_governance_enabled: bool = False
    _metabolic_governor = None
    # T59 — Organism Integration Bus
    organism_integration_enabled: bool = False
    _organism_bus = None
    # T60 — Cyber-Physical Assimilation Interface
    cyber_physical_assimilation_enabled: bool = False
    _cyber_physical_gateway = None
    _last_cyber_physical_audit_result = None
    # T42 — Cellular Adaptive Defense & Repair
    cellular_adaptive_defense_enabled: bool = False
    cellular_repair_enabled: bool = False
    cellular_epigenetics_enabled: bool = False
    _cellular_stress_engine: CellularStressEngine | None = None
    _cellular_damage_engine: CellularDamageEngine | None = None
    _cellular_repair_engine: CellularRepairEngine | None = None
    _cellular_defense_engine: CellularDefenseEngine | None = None
    _cellular_epigenetic_adapter: CellularEpigeneticAdapter | None = None
    _last_cellular_stress_result = None
    _last_cellular_damage_result = None
    _last_cellular_repair_result = None
    _last_cellular_defense_result = None
    _last_cellular_epigenetic_result = None
    _previous_damage_state: dict | None = None
    # T43 — Semantic Cell Assembly Memory
    semantic_memory_enabled: bool = False
    _semantic_memory_store: "SemanticMemoryStore | None" = None
    _cell_assembly_engine: "CellAssemblyEngine | None" = None
    _semantic_recall_engine: "SemanticRecallEngine | None" = None
    # T44 — Associative Learning Between Assemblies
    associative_learning_enabled: bool = False
    associative_recall_enabled: bool = False
    _associative_learning_engine = None
    _associative_recall_engine = None
    # T45 — Autonomous Self-Improvement Loop
    self_improvement_enabled: bool = False
    _self_improvement_loop = None
    # T48 — Episodic-Guided Self-Improvement Policy
    episodic_policy_enabled: bool = False
    # T49 — Counterfactual Architecture Sandbox
    counterfactual_sandbox_enabled: bool = False
    # T50 — Safe Architecture Patch Execution
    architecture_patch_execution_enabled: bool = False
    # T47 — Episodic Memory
    episodic_memory_enabled: bool = True
    _episodic_memory = None
    _episodic_recall = None
    # Associative Pattern Completion Memory
    associative_pattern_completion_enabled: bool = False
    _associative_pattern_completion = None

    # Persistence Layer
    persistence_enabled: bool = True
    _persistence_layer: Any | None = None
    _last_metrics: Any | None = None

    # T66 — Runtime coordinators (strangler fig decomposition)
    _memory_coordinator: MemoryCoordinator | None = None
    _evolution_coordinator: EvolutionCoordinator | None = None
    _metabolism_coordinator: MetabolismCoordinator | None = None
    _persistence_coordinator: PersistenceCoordinator | None = None
    _subsystem_scheduler: SubsystemScheduler | None = None

    # T67 — Digital Sleep & Memory Consolidation
    sleep_enabled: bool = False
    _sleep_controller: DigitalSleepController | None = None
    # T68 — Digital Immune System
    immune_enabled: bool = False
    _immune_controller: DigitalImmuneController | None = None
    # T69 — Sandboxed Embodied Tool Registry
    tool_registry_enabled: bool = False
    _tool_registry_controller: ToolRegistryController | None = None
    # T70 — Autobiographical Identity Kernel
    identity_kernel_enabled: bool = False
    _identity_kernel: IdentityKernel | None = None
    # T71 — Global Cognitive Workspace
    global_workspace_enabled: bool = False
    _global_workspace: GlobalWorkspace | None = None
    _last_global_workspace_step_result: dict | None = None

    # Continuous dynamics modules (disabled by default)
    temporal_dynamics_enabled: bool = False
    neural_oscillator_enabled: bool = False
    phase_coupling_enabled: bool = False
    energy_field_enabled: bool = False
    predictive_coding_enabled: bool = False
    active_inference_enabled: bool = False
    homeostatic_drive_enabled: bool = False
    criticality_monitor_enabled: bool = False
    # ARC-AGI benchmark
    arc_agi_benchmark_enabled: bool = False
    evaluation_mode: bool = False
    _arc_agi_adapter: Any = None
    _temporal_dynamics: TemporalDynamicsEngine | None = None
    _oscillator_bank: NeuralOscillatorBank | None = None
    _phase_coupling: PhaseCouplingEngine | None = None
    _energy_field: EnergyFieldEngine | None = None
    _predictive_coding: PredictiveCodingEngine | None = None
    _active_inference: ActiveInferenceEngine | None = None
    _homeostatic_drive: GlobalHomeostaticDrive | None = None
    _criticality_monitor: CriticalityMonitor | None = None

    # Emergent Dynamics Stabilizer
    emergent_dynamics_stabilizer_enabled: bool = False
    _emergent_dynamics_stabilizer: EmergentDynamicsStabilizer | None = None
    _cognitive_attractor_tracker: CognitiveAttractorTracker | None = None

    # T72 — Sensorimotor Embodiment
    embodiment_enabled: bool = False
    _sensor_array: CyberPhysicalSensorArray | None = None
    _physical_environment: PhysicalEnvironmentModel | None = None
    _embodied_actuator: EmbodiedActionActuator | None = None
    _embodiment_monitor: EmbodimentMonitor | None = None
    _last_sensor_snapshot: dict | None = None
    _last_predicted_state_dict: dict | None = None
    _last_action_proposed: dict | None = None

    # T162 — Cognitive Integration & Systemic Harmony
    systemic_harmony_enabled: bool = False
    _systemic_harmony_layer: SystemicHarmonyLayer | None = None

    # ILF — Informational Logical Field (causal field for brain orchestration)
    ilf_enabled: bool = False
    ilf_broadcast_interval: float = 0.0  # 0 = every cycle
    _ilf_field_effects_enabled: bool = True

    # System Assimilation — VFS e Windows System Assimilation
    system_assimilation_enabled: bool = False
    vfs_enabled: bool = False
    _vfs_engine: Any = None
    _system_assimilator: Any = None
    _last_assimilation_report: Any = None
    _last_vfs_index: Any = None

    # Capability Gap Analyzer & Bottleneck Detector
    _capability_gap_analyzer: CapabilityGapAnalyzer | None = None
    _bottleneck_detector: BottleneckDetector | None = None
    _last_capability_gap_report: dict | None = None
    _last_bottleneck_report: dict | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_post_init(self, __context: object) -> None:
        self._homeostasis = HomeostasisEngine()
        self._plasticity = PlasticityEngine()
        self._memory = MorphologicalMemory()
        self._memory.load()
        self.circuit.memory = self._memory
        self._neurogenesis = NeurogenesisEngine()
        self._apoptosis = ApoptosisEngine()
        self._differentiation = CellDifferentiationEngine(
            genome=self.genome,
            memory=self._memory,
        )
        self._burst_engine = EventDrivenBurstEngine()
        self._stdp = STDPPlasticityEngine()
        self._inhibition = InhibitionEngine()
        self._energy_control = EnergyControlAgent()
        self._inter_region_plasticity = InterRegionPlasticityEngine()
        self._region_signal_router = RegionSignalRouter()
        self._community = CommunityDetectionEngine()
        self._confidence = ConfidenceEngine()
        if self.region_architecture_enabled:
            self._region_registry = RegionFactory.build_from_genome(
                self.circuit, self.genome.model_dump(), seed=42, deep_regions_enabled=self.deep_regions_enabled
            )
        else:
            self._region_registry = None

        if self.region_stability_controller_enabled:
            self._region_stability_controller = RegionLevelStabilityController()
        else:
            self._region_stability_controller = None

        if self.deep_region_routing_calibrator_enabled:
            profile = self._deep_region_routing_profile or DeepRegionRoutingProfile(
                profile_id="orch_default",
                name="orchestrator_default",
            )
            self._deep_region_routing_calibrator = DeepRegionRoutingCalibrator(profile=profile)
            self._deep_region_routing_calibrator.apply_profile_to_router(self._region_signal_router)
        else:
            self._deep_region_routing_calibrator = None

        if self.brainstem_controller_enabled:
            self._brainstem_controller = BrainstemFunctionalController()
        else:
            self._brainstem_controller = None

        if self.brainstem_gain_controller_enabled:
            self._brainstem_gain_controller = AdaptiveBrainstemGainController()
        else:
            self._brainstem_gain_controller = None

        # T42 — Cellular Adaptive Defense & Repair
        if self.cellular_adaptive_defense_enabled:
            self._cellular_stress_engine = CellularStressEngine()
            self._cellular_damage_engine = CellularDamageEngine()
            self._cellular_defense_engine = CellularDefenseEngine()
        if self.cellular_repair_enabled:
            self._cellular_repair_engine = CellularRepairEngine()
        if self.cellular_epigenetics_enabled:
            self._cellular_epigenetic_adapter = CellularEpigeneticAdapter()

        # T43 — Semantic Cell Assembly Memory
        if self.semantic_memory_enabled:
            from speace_core.cellular_brain.memory.semantic.semantic_memory_store import SemanticMemoryStore
            from speace_core.cellular_brain.memory.semantic.cell_assembly_engine import CellAssemblyEngine
            from speace_core.cellular_brain.memory.semantic.semantic_recall_engine import SemanticRecallEngine

            self._semantic_memory_store = SemanticMemoryStore()
            self._cell_assembly_engine = CellAssemblyEngine(store=self._semantic_memory_store)
            self._semantic_recall_engine = SemanticRecallEngine(store=self._semantic_memory_store)

        # T66 — Initialize runtime coordinators (strangler fig decomposition)
        self._memory_coordinator = MemoryCoordinator()
        self._evolution_coordinator = EvolutionCoordinator()
        self._metabolism_coordinator = MetabolismCoordinator()
        self._persistence_coordinator = PersistenceCoordinator(
            snapshot_interval=50,
            data_dir="data/persistence",
            event_bus=None,
        )
        self._persistence_coordinator.initialize(self._build_subsystem_context())
        self._subsystem_scheduler = SubsystemScheduler()
        self._subsystem_scheduler.assign("memory", self._memory_coordinator)
        self._subsystem_scheduler.assign("evolution", self._evolution_coordinator)
        self._subsystem_scheduler.assign("metabolism", self._metabolism_coordinator)
        self._subsystem_scheduler.assign("persistence", self._persistence_coordinator)

        # T67 — Digital Sleep
        if self.sleep_enabled:
            self._sleep_controller = DigitalSleepController()
        # T68 — Digital Immune
        if self.immune_enabled:
            self._immune_controller = DigitalImmuneController()
        # T69 — Tool Registry
        if self.tool_registry_enabled:
            self._tool_registry_controller = ToolRegistryController()
        # T70 — Identity Kernel
        if self.identity_kernel_enabled:
            self._identity_kernel = IdentityKernel()

        # T71 — Global Cognitive Workspace
        if self.global_workspace_enabled:
            self._global_workspace = GlobalWorkspace(
                broadcast_dim=64,
                symbolic_dim=16,
                num_modules=10,
                seed=42,
                memory=self._memory,
            )

        # T132 — LinguisticCognitiveBridge: GlobalWorkspace ↔ language areas
        if self.global_workspace_enabled and hasattr(self, "_global_workspace"):
            from speace_core.cellular_brain.language.broca_area import DigitalBrocaArea
            from speace_core.cellular_brain.language.wernicke_area import DigitalWernickeArea
            self._linguistic_bridge = LinguisticCognitiveBridge(
                workspace=self._global_workspace,
                broca=DigitalBrocaArea(cpg_period=2),
                wernicke=DigitalWernickeArea(
                    vocab=_build_bridge_vocabulary(),
                    coherence_threshold=0.2,
                ),
                verbalisation_threshold=0.3,
            )
        else:
            self._linguistic_bridge = None

        # ARC-AGI adapter (lazy init on first use to avoid circular imports)
        if self.arc_agi_benchmark_enabled:
            from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter
            from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
                FewShotProgramInductionEngine,
            )
            from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
                SpatialSymbolicReasoningLayer,
            )

            self._arc_agi_adapter = ARCAGIAdapter(
                engine=FewShotProgramInductionEngine(
                    spatial_layer=SpatialSymbolicReasoningLayer()
                ),
                data_dir="data/arc_agi",
                evaluation_mode=self.evaluation_mode,
            )

        # System Assimilation — VFS e Windows System Assimilation (dopo _initialize_dynamic_modules)
        genome_sa = getattr(self.genome, "system_assimilation", None)
        if genome_sa is not None:
            self.vfs_enabled = getattr(genome_sa, "enable_vfs", False)
            self.system_assimilation_enabled = getattr(genome_sa, "enable_assimilation", False)
        if self.vfs_enabled:
            from speace_core.cellular_brain.virtual_file_system import VirtualFileSystemEngine
            from speace_core.cellular_brain.virtual_file_system.vfs_models import VFSConfig, AccessRule, VFSPermission
            rules = []
            for r in getattr(genome_sa, "access_rules", []):
                perms = []
                for p in r.allowed_permissions:
                    try:
                        perms.append(VFSPermission[p.upper()])
                    except KeyError:
                        pass
                rules.append(AccessRule(
                    rule_id=f"dna_{r.path_prefix}",
                    path_prefix=r.path_prefix,
                    allowed_permissions=perms,
                    allowed=not r.requires_approval or r.approved,
                    requires_approval=r.requires_approval,
                    approved=r.approved,
                ))
            vfs_config = VFSConfig(
                root_mount_point=getattr(genome_sa, "root_mount_point", "C:\\"),
                speace_install_path="C:\\cellular_speace",
                access_rules=rules,
                enable_vfs=True,
            )
            self._vfs_engine = VirtualFileSystemEngine(config=vfs_config)
            self._last_vfs_index = self._vfs_engine.index_root()
        if self.system_assimilation_enabled:
            from speace_core.cellular_brain.system_assimilation import WindowsSystemAssimilator
            from speace_core.cellular_brain.system_assimilation.assimilation_models import SystemAssimilationConfig
            self._system_assimilator = WindowsSystemAssimilator(config=SystemAssimilationConfig(
                enable_assimilation=True,
                allow_wmi_queries=True,
            ))
            self._last_assimilation_report = self._system_assimilator.assimilate()

        self._capability_gap_analyzer = CapabilityGapAnalyzer(directory="data/capability_gaps")
        self._bottleneck_detector = BottleneckDetector(directory="data/bottleneck_reports")
        self._initialize_dynamic_modules()

    def _initialize_dynamic_modules(self) -> None:
        """Initialize dynamics and embodiment modules. Idempotent: safe to call again after flags change."""
        all_neurons = (
            self.circuit.input_neurons
            + self.circuit.hidden_neurons
            + self.circuit.output_neurons
        )
        dynamics_cfg = self.genome.dynamics.model_dump() if self.genome.dynamics else {}

        if self.temporal_dynamics_enabled and self._temporal_dynamics is None:
            td_cfg = dynamics_cfg.get("temporal_dynamics", {})
            self._temporal_dynamics = TemporalDynamicsEngine(
                neurons=all_neurons,
                synapses=self.circuit.synapses,
                tau=td_cfg.get("tau", 1.0),
                tau_w=td_cfg.get("tau_w", 10.0),
                tau_e=td_cfg.get("tau_e", 5.0),
                noise_std=td_cfg.get("noise_std", 0.0),
                supply=td_cfg.get("supply", 0.1),
                consumption=td_cfg.get("consumption", 0.05),
                plasticity_rate=td_cfg.get("plasticity_rate", 0.05),
            )

        if self.neural_oscillator_enabled and self._oscillator_bank is None:
            self._oscillator_bank = NeuralOscillatorBank()
            for n in all_neurons:
                self._oscillator_bank.register_neuron(n.cell_id, band="theta", coupling_strength=0.1)

        if self.phase_coupling_enabled and self._phase_coupling is None:
            self._phase_coupling = PhaseCouplingEngine()
            if self._oscillator_bank is not None:
                for band, params in self._oscillator_bank.bands.items():
                    self._phase_coupling.register_oscillator(band, freq=params["freq"])

        if self.energy_field_enabled and self._energy_field is None:
            ef_cfg = dynamics_cfg.get("energy_field", {})
            self._energy_field = EnergyFieldEngine(
                global_supply_rate=ef_cfg.get("global_supply_rate", 0.02),
                recovery_boost=ef_cfg.get("recovery_boost", 0.03),
                fatigue_threshold=ef_cfg.get("fatigue_threshold", 0.2),
            )
            for n in all_neurons:
                self._energy_field.register_neuron(
                    n.cell_id,
                    baseline_supply=0.1,
                    consumption_rate=0.05,
                    diffusion_rate=0.01,
                    initial_energy=getattr(n, "energy", 1.0),
                )
            for s in self.circuit.synapses:
                if s.state != "pruned":
                    self._energy_field.register_synapse(s.source, s.target)

        if self.predictive_coding_enabled and self._predictive_coding is None:
            pc_cfg = dynamics_cfg.get("predictive_coding", {})
            self._predictive_coding = PredictiveCodingEngine(
                learning_rate=pc_cfg.get("learning_rate", 0.1)
            )
            input_dim = len(self.circuit.input_neurons)
            hidden_dim = len(self.circuit.hidden_neurons)
            output_dim = len(self.circuit.output_neurons)
            self._predictive_coding.register_layer("sensory", input_dim, 0)
            self._predictive_coding.register_layer("association", hidden_dim, 1)
            self._predictive_coding.register_layer("abstract", output_dim, 2)
            if input_dim and hidden_dim:
                self._predictive_coding.set_connection("association", "sensory")
            if hidden_dim and output_dim:
                self._predictive_coding.set_connection("abstract", "association")

        if self.active_inference_enabled and self._active_inference is None:
            self._active_inference = ActiveInferenceEngine()

        if self.homeostatic_drive_enabled and self._homeostatic_drive is None:
            hd_cfg = dynamics_cfg.get("homeostatic_drive", {})
            self._homeostatic_drive = GlobalHomeostaticDrive(
                plasticity_range=tuple(hd_cfg.get("plasticity_range", [0.0, 2.0])),
                exploration_range=tuple(hd_cfg.get("exploration_range", [0.0, 2.0])),
                energy_supply_range=tuple(hd_cfg.get("energy_supply_range", [0.5, 1.5])),
                stability_range=tuple(hd_cfg.get("stability_range", [0.5, 1.5])),
                survival_suppression_threshold=hd_cfg.get("survival_suppression_threshold", 0.3),
                efficiency_plasticity_threshold=hd_cfg.get("efficiency_plasticity_threshold", -0.2),
            )

        if self.criticality_monitor_enabled and self._criticality_monitor is None:
            cm_cfg = dynamics_cfg.get("criticality_monitor", {})
            self._criticality_monitor = CriticalityMonitor(
                avalanche_window=cm_cfg.get("avalanche_window", 10.0),
                branching_bin_size=cm_cfg.get("branching_bin_size", 5.0),
                max_history=cm_cfg.get("max_history", 10000),
            )

        # Emergent Dynamics Stabilizer
        if self.emergent_dynamics_stabilizer_enabled and self._emergent_dynamics_stabilizer is None:
            self._emergent_dynamics_stabilizer = EmergentDynamicsStabilizer()
            self._cognitive_attractor_tracker = CognitiveAttractorTracker()

        # T72 — Sensorimotor Embodiment initialization
        if self.embodiment_enabled and self._sensor_array is None:
            self._sensor_array = CyberPhysicalSensorArray()
            self._sensor_array.start_continuous_sampling(interval_ms=1000)
            self._physical_environment = PhysicalEnvironmentModel()
            first_reading = self._sensor_array.read_all()
            flat_first = self._flatten_sensor_snapshot(first_reading)
            self._physical_environment.update(flat_first)
            self._embodied_actuator = EmbodiedActionActuator()
            self._embodiment_monitor = EmbodimentMonitor()
            self._last_sensor_snapshot = first_reading
            self._last_predicted_state_dict = None
            self._last_action_proposed = None

            if self.active_inference_enabled and self._active_inference is not None:
                self._active_inference.register_state("stable", 0.5)
                self._active_inference.register_state("unstable", 0.5)
                self._active_inference.register_action(
                    "observe", {"stable": 0.7, "unstable": 0.3}
                )
                self._active_inference.register_action(
                    "actuate", {"stable": 0.3, "unstable": 0.7}
                )

        # ILF — Informational Logical Field initialization
        if self.ilf_enabled:
            self.init_field_integrator(
                ilf_config=None,
                broadcast_interval=self.ilf_broadcast_interval,
            )
            # Register neural circuit as a field-aware subsystem
            self.register_subsystem_to_field(
                name="neural_circuit",
                get_metrics_fn=self._get_circuit_ilf_metrics,
                on_field_update_fn=self._on_ilf_update,
                reconfigure_fn=self._on_ilf_update,
                weight=1.0,
            )

    def _build_subsystem_context(self) -> SubsystemContext:
        return SubsystemContext(
            orchestrator_ref=lambda: self,
            genome=self.genome,
            tick_state=TickState(
                current_tick=self.current_tick,
                latest_metrics=self.latest_metrics,
                last_community_result=self.last_community_result,
                last_confidence_state=self.last_confidence_state,
                last_routing_result=self.last_routing_result,
                negative_feedback_count=self.negative_feedback_count,
            ),
        )

    async def run_ticks(self, n_ticks: int) -> None:
        for _ in range(n_ticks):
            await self._tick()
            if self.tick_interval > 0:
                await asyncio.sleep(self.tick_interval)

    async def _tick(self) -> None:
        self.current_tick += 1
        if self.execution_mode == "event_driven_burst":
            burst_results = self._burst_engine.run_event_cycle(self.circuit)
            if self.stdp_enabled:
                self._stdp.apply_stdp(self.circuit, self._memory)
            if self.inhibition_enabled:
                last_result = burst_results[-1] if burst_results else None
                self._inhibition.stabilize_after_burst(
                    self.circuit, last_result, self._memory
                )
            if self.energy_control_enabled:
                metrics = self.latest_metrics
                self._energy_control.regulate(
                    self.circuit,
                    metrics=metrics,
                    burst_engine=self._burst_engine,
                    memory=self._memory,
                )
        else:
            await self.circuit.tick()

        all_neurons = (
            self.circuit.input_neurons
            + self.circuit.hidden_neurons
            + self.circuit.output_neurons
        )
        metrics = self._homeostasis.compute_metrics(
            tick=self.current_tick,
            neurons=all_neurons,
            astrocytes=self.circuit.astrocytes,
            synapse_count=len(self.circuit.synapses),
            pruned_count=sum(1 for s in self.circuit.synapses if s.state == "pruned"),
        )
        self.metrics_log.append(metrics)
        self._last_metrics = metrics

        # ------------------------------------------------------------------ #
        # Continuous dynamics integration (additive, disabled by default)
        # ------------------------------------------------------------------ #
        if self.temporal_dynamics_enabled and self._temporal_dynamics is not None:
            for n in all_neurons:
                self._temporal_dynamics.inject_input(
                    n.cell_id, getattr(n, "activation", 0.0)
                )
            self._temporal_dynamics.step(dt=1.0)

        if self.neural_oscillator_enabled and self._oscillator_bank is not None:
            self._oscillator_bank.step(dt=1.0)
            if self.temporal_dynamics_enabled and self._temporal_dynamics is not None:
                modulation = {}
                for n in all_neurons:
                    if n.cell_id in self._oscillator_bank.list_registered_neurons():
                        modulation[n.cell_id] = self._oscillator_bank.get_neural_modulation(n.cell_id)
                if modulation:
                    self._temporal_dynamics.couple_oscillations(modulation)

        if self.phase_coupling_enabled and self._phase_coupling is not None:
            self._phase_coupling.step(dt=1.0)

        if self.energy_field_enabled and self._energy_field is not None:
            activations = {}
            if self.temporal_dynamics_enabled and self._temporal_dynamics is not None:
                for n in all_neurons:
                    try:
                        activations[n.cell_id] = self._temporal_dynamics.get_neuron_state(n.cell_id)
                    except KeyError:
                        activations[n.cell_id] = getattr(n, "activation", 0.0)
            else:
                for n in all_neurons:
                    activations[n.cell_id] = getattr(n, "activation", 0.0)
            self._energy_field.step(dt=1.0, activations=activations)

        if self.predictive_coding_enabled and self._predictive_coding is not None:
            if self.circuit.input_neurons:
                sensory_input = np.array(
                    [getattr(n, "activation", 0.0) for n in self.circuit.input_neurons]
                )
                self._predictive_coding.update("sensory", sensory_input)
            self._predictive_coding.step()

        if self.active_inference_enabled and self._active_inference is not None:
            self._active_inference.step()

        if self.homeostatic_drive_enabled and self._homeostatic_drive is not None:
            self._homeostatic_drive.update_drive("exploration", metrics.noise_level)
            self._homeostatic_drive.update_drive("stability", metrics.coherence_phi)
            self._homeostatic_drive.update_drive("survival", 1.0 - metrics.mean_energy)
            self._homeostatic_drive.update_drive("efficiency", metrics.mean_energy)
            modulation = self._homeostatic_drive.step()
            # Apply modulations to circuit parameters
            for n in all_neurons:
                n.plasticity_rate = max(
                    0.001, min(1.0, n.plasticity_rate * modulation["plasticity_multiplier"])
                )
                n.threshold = max(
                    0.1,
                    min(
                        1.0,
                        n.threshold
                        / (modulation["exploration_multiplier"] if modulation["exploration_multiplier"] != 0 else 1.0),
                    ),
                )

        if self.criticality_monitor_enabled and self._criticality_monitor is not None:
            for n in all_neurons:
                self._criticality_monitor.record_activation(n.cell_id, float(self.current_tick))
            _ = self._criticality_monitor.recommend_modulation()

        # ------------------------------------------------------------------ #
        # T72 — Sensorimotor Embodiment Loop
        # ------------------------------------------------------------------ #
        if self.embodiment_enabled and self._sensor_array is not None:
            sensor_before = self._last_sensor_snapshot
            sensor_after = self._sensor_array.read_all()
            flat_after = self._flatten_sensor_snapshot(sensor_after)

            if self._physical_environment is not None:
                self._physical_environment.update(flat_after)
                prediction_error = self._physical_environment.get_prediction_error(flat_after)
                predicted_next = self._physical_environment.predict_next_state()

                if self.predictive_coding_enabled and self._predictive_coding is not None:
                    input_dim = self._predictive_coding.layers["sensory"]["dim"]
                    pc_input = np.full(input_dim, prediction_error)
                    self._predictive_coding.update("sensory", pc_input)

                if self.active_inference_enabled and self._active_inference is not None:
                    if prediction_error > 1.0:
                        self._active_inference.observe("unstable", likelihood=2.0)
                    else:
                        self._active_inference.observe("stable", likelihood=2.0)
                    selected_action = self._active_inference.step()
                    if selected_action is not None and self._embodied_actuator is not None:
                        signal_type = (
                            "request_sleep"
                            if selected_action == "actuate"
                            else "request_resume"
                        )
                        self._embodied_actuator.propose_action(
                            "send_signal_to_self",
                            {"signal_type": signal_type},
                        )
                        self._last_action_proposed = {
                            "action_id": selected_action,
                            "timestamp": time.time(),
                        }

            if self._embodiment_monitor is not None and sensor_before is not None:
                self._embodiment_monitor.evaluate_tick(
                    sensor_before=sensor_before,
                    action=self._last_action_proposed,
                    sensor_after=sensor_after,
                    prediction=self._last_predicted_state_dict,
                )

            self._last_sensor_snapshot = sensor_after
            self._last_predicted_state_dict = predicted_next if self._physical_environment is not None else None
            self._last_action_proposed = None

        # Community detection (observational only in T17)
        if self.community_detection_enabled:
            self.last_community_result = self._community.analyze(
                self.circuit, memory=self._memory
            )

        # Meta-learning confidence evaluation (T19)
        if self.confidence_enabled:
            self.last_confidence_state = self._confidence.evaluate(
                self.circuit,
                metrics=metrics,
                community_result=self.last_community_result,
                memory=self._memory,
            )
            self.neurogenesis_recommended = (
                self.last_confidence_state.neurogenesis_recommended
            )
            self.stabilization_recommended = (
                self.last_confidence_state.stabilization_recommended
            )
            self.plasticity_reduction_recommended = (
                self.last_confidence_state.plasticity_reduction_recommended
            )

        # Regional architecture regulation (T21)
        if self.region_architecture_enabled and self._region_registry is not None:
            for region in self._region_registry.regions.values():
                region.regulate_region(self.circuit)

        # T33 — Region-Level Stability Controller (pre-routing check)
        routing_multiplier_map = None
        plasticity_multiplier_map = None
        # T34B-FIX: Extract flow memory from router for stability controller
        flow_memory = None
        if self._region_signal_router is not None:
            flow_memory = getattr(self._region_signal_router, "_t34_flow_memory", None)
        if self.region_stability_controller_enabled and self._region_stability_controller is not None and self._region_registry is not None:
            pre_result = self._region_stability_controller.pre_routing_stability_check(
                registry=self._region_registry,
                circuit=self.circuit,
                memory=self._memory,
                flow_memory=flow_memory,
            )
            routing_multiplier_map = {
                rid: self._region_stability_controller.get_routing_multiplier(rid)
                for rid in self._region_registry.regions
            }
            plasticity_multiplier_map = {
                rid: self._region_stability_controller.get_plasticity_multiplier(rid)
                for rid in self._region_registry.regions
            }

        # T35 — Brainstem Functional Integration
        if self.brainstem_controller_enabled and self._brainstem_controller is not None:
            # T36 — Compute mean deep-region activation from circuit at tick time
            deep_regions = {"limbic", "hippocampus", "default_mode", "prefrontal", "cerebellar", "brainstem_homeostatic"}
            deep_activations = [
                abs(getattr(n, "activation", 0.0))
                for n in all_neurons
                if getattr(n, "region", None) in deep_regions
            ]
            mean_deep_activation = sum(deep_activations) / len(deep_activations) if deep_activations else 0.0

            brainstem_metrics = {
                "mean_region_phi": metrics.coherence_phi,
                "mean_energy": metrics.mean_energy,
                "region_instability_mean": 0.0,
                "unstable_region_count": 0,
                "mean_deep_region_activation": mean_deep_activation,
                "regional_signal_flow": 0.0,
                "deep_region_signal_flow": 0.0,
                "stability_actions_applied": 0,
                "routing_blocks_applied": 0,
                "cooldowns_started": 0,
                "mean_pathway_utility": 0.0,
                "energy_state": metrics.mean_energy,
                "region_count": len(self._region_registry.regions) if self._region_registry is not None else 4,
                # T36 — placeholder for benchmark-level metrics; brainstem uses proxies when zero
                "cognitive_score": 0.0,
                "functional_improvement": 0.0,
            }
            # Enrich with stability controller data if available
            if self._region_stability_controller is not None:
                summary = self._region_stability_controller.summarize_stability()
                region_states = summary.get("region_states", {})
                instability_scores = [s.get("instability_score", 0.0) for s in region_states.values()]
                if instability_scores:
                    brainstem_metrics["region_instability_mean"] = sum(instability_scores) / len(instability_scores)
                brainstem_metrics["unstable_region_count"] = sum(
                    1 for s in region_states.values() if s.get("instability_score", 0.0) >= 0.25
                )
                brainstem_metrics["mean_region_damping_factor"] = summary.get("mean_damping_factor", 1.0)
            # Enrich with routing data if available
            if self.last_routing_result is not None:
                brainstem_metrics["regional_signal_flow"] = getattr(
                    self.last_routing_result, "regional_signal_flow_score", 0.0
                )
            # T39 — Evaluate gain controller BEFORE brainstem to pass gain vector into state selection
            gain_vector: dict | None = None
            if self.brainstem_gain_controller_enabled and self._brainstem_gain_controller is not None:
                gain_metrics = {
                    "cognitive_score_delta": 0.0,
                    "coherence_phi_delta": 0.0,
                    "energy_efficiency_delta": 0.0,
                    "functional_improvement_delta": 0.0,
                    "suppression_cost": getattr(self._brainstem_controller, "_last_suppression_cost", 0.0) if self._brainstem_controller else 0.0,
                    "emergency_ticks": getattr(self._brainstem_controller, "_state_ticks", {}).get("emergency", 0) if self._brainstem_controller else 0,
                    "protective_ticks": getattr(self._brainstem_controller, "_state_ticks", {}).get("protective", 0) if self._brainstem_controller else 0,
                    "total_ticks": self.current_tick,
                    "mean_region_energy": metrics.mean_energy,
                    "mean_region_phi": metrics.coherence_phi,
                }
                self._last_brainstem_gain_result = self._brainstem_gain_controller.evaluate(gain_metrics)
                gain_vector = self._last_brainstem_gain_result.decision.model_dump()

            self._last_brainstem_result = self._brainstem_controller.apply(
                metrics=brainstem_metrics,
                memory=self._memory,
                gain_vector=gain_vector,
            )
            # Compose brainstem modulations with stability multipliers
            decision = self._last_brainstem_result.decision
            if routing_multiplier_map is not None:
                for rid in routing_multiplier_map:
                    routing_multiplier_map[rid] *= decision.routing_suppression_multiplier
            else:
                routing_multiplier_map = {
                    rid: decision.routing_suppression_multiplier
                    for rid in self._region_registry.regions
                } if self._region_registry is not None else None
            if plasticity_multiplier_map is not None:
                for rid in plasticity_multiplier_map:
                    plasticity_multiplier_map[rid] *= decision.plasticity_suppression_multiplier
            else:
                plasticity_multiplier_map = {
                    rid: decision.plasticity_suppression_multiplier
                    for rid in self._region_registry.regions
                } if self._region_registry is not None else None
            # T37/T39 — Apply Adaptive Brainstem Gain Controller output coupling on top of T36 modulations
            if self.brainstem_gain_controller_enabled and self._brainstem_gain_controller is not None and gain_vector is not None:
                g = self._last_brainstem_gain_result.decision
                if routing_multiplier_map is not None:
                    for rid in routing_multiplier_map:
                        routing_multiplier_map[rid] = 1.0 - (1.0 - routing_multiplier_map[rid]) * g.routing_gain
                if plasticity_multiplier_map is not None:
                    for rid in plasticity_multiplier_map:
                        plasticity_multiplier_map[rid] = 1.0 - (1.0 - plasticity_multiplier_map[rid]) * g.plasticity_gain
                # Re-apply decay with adjusted gain
                adjusted_decay = 1.0 + (decision.decay_boost_multiplier - 1.0) * g.decay_gain
                if adjusted_decay > 1.0:
                    decay_factor = 1.0 / adjusted_decay
                    for n in all_neurons:
                        n.activation = getattr(n, "activation", 0.0) * decay_factor
                # If original decay was already applied, skip re-applying
            else:
                # Apply decay boost if requested (original T35/T36 path)
                if decision.decay_boost_multiplier > 1.0:
                    decay_factor = 1.0 / decision.decay_boost_multiplier
                    for n in all_neurons:
                        n.activation = getattr(n, "activation", 0.0) * decay_factor

        # Regional Signal Routing (T25)
        if self.region_signal_routing_enabled and self._region_registry is not None:
            confidence_score = 0.0
            if self.last_confidence_state is not None:
                confidence_score = self.last_confidence_state.confidence_score
            self.last_routing_result = self._region_signal_router.route_all(
                region_connectome=self._region_registry.connectome,
                circuit=self.circuit,
                metrics=metrics,
                memory=self._memory,
                confidence_score=confidence_score,
                routing_multiplier_map=routing_multiplier_map,
                current_tick=self.current_tick,
            )

        # Inter-Region Plasticity (T23)
        if self.inter_region_plasticity_enabled and self._region_registry is not None:
            confidence_score = 0.0
            if self.last_confidence_state is not None:
                confidence_score = self.last_confidence_state.confidence_score
            self._inter_region_plasticity.update_pathways(
                circuit=self.circuit,
                registry=self._region_registry,
                metrics=metrics,
                memory=self._memory,
                tick=self.current_tick,
                confidence_score=confidence_score,
                routing_result=self.last_routing_result,
                plasticity_multiplier_map=plasticity_multiplier_map,
            )

        # T33 — Region-Level Stability Controller (post-routing check)
        if self.region_stability_controller_enabled and self._region_stability_controller is not None and self._region_registry is not None:
            self._region_stability_controller.post_routing_stability_check(
                registry=self._region_registry,
                circuit=self.circuit,
                memory=self._memory,
                flow_memory=flow_memory,
            )

        # T42 — Cellular Adaptive Defense & Repair
        self._run_cellular_adaptive_defense_and_repair()

        # T68 — Digital Immune System
        if self.immune_enabled and self._immune_controller is not None:
            self._immune_controller.tick(self)

        # T43 — Semantic Cell Assembly Memory
        if self.semantic_memory_enabled and self._cell_assembly_engine is not None:
            self._cell_assembly_engine.run_semantic_memory_cycle(self)

        # T67 — Digital Sleep & Memory Consolidation
        if self.sleep_enabled and self._sleep_controller is not None:
            self._sleep_controller.tick(self)

        # T70 — Autobiographical Identity Kernel
        if self.identity_kernel_enabled and self._identity_kernel is not None:
            self._identity_kernel.tick(self)

        # T71 — Global Cognitive Workspace
        if self.global_workspace_enabled and self._global_workspace is not None:
            # Feed current circuit activation signature into workspace
            all_neurons = (
                self.circuit.input_neurons
                + self.circuit.hidden_neurons
                + self.circuit.output_neurons
            )
            activation_signature = [getattr(n, "activation", 0.0) for n in all_neurons]
            # Pad or truncate to broadcast_dim (64)
            target_len = self._global_workspace._broadcast_dim
            if len(activation_signature) < target_len:
                activation_signature += [0.0] * (target_len - len(activation_signature))
            else:
                activation_signature = activation_signature[:target_len]
            self._global_workspace.broadcast("circuit", activation_signature)
            self._last_global_workspace_step_result = self._global_workspace.step()

        # T132 — LinguisticCognitiveBridge: verbalise workspace state
        if self._linguistic_bridge is not None:
            self._linguistic_bridge.tick()

        # T44 — Associative Learning Between Assemblies
        if (
            self.semantic_memory_enabled
            and self.associative_learning_enabled
            and self._associative_learning_engine is not None
        ):
            active_assemblies = []
            if self._semantic_memory_store is not None:
                active_assemblies = self._semantic_memory_store.list_active()
            if active_assemblies:
                self._associative_learning_engine.observe_assemblies(
                    active_assemblies, tick=self.current_tick
                )

        # Emergent Dynamics Stabilizer step
        if self.emergent_dynamics_stabilizer_enabled and self._emergent_dynamics_stabilizer is not None:
            all_neurons = (
                self.circuit.input_neurons
                + self.circuit.hidden_neurons
                + self.circuit.output_neurons
            )
            activations = [getattr(n, "activation", 0.0) for n in all_neurons]
            energies = {n.cell_id: getattr(n, "energy", 1.0) for n in all_neurons}

            drive_levels = {}
            if self.homeostatic_drive_enabled and self._homeostatic_drive is not None:
                for name in self._homeostatic_drive.list_drives():
                    try:
                        drive_levels[name] = self._homeostatic_drive.get_drive_signal(name)
                    except KeyError:
                        pass

            prediction_errors = {}
            if self.predictive_coding_enabled and self._predictive_coding is not None:
                for layer_id in self._predictive_coding.layers:
                    prediction_errors[layer_id] = self._predictive_coding.get_prediction_error(layer_id)

            workspace_state = {}
            if self.global_workspace_enabled and self._global_workspace is not None:
                workspace_state = self._global_workspace.get_global_state()

            self_model_coherence = metrics.coherence_phi if metrics else 0.0
            embodiment_depth = 0.0
            if self.embodiment_enabled and self._embodiment_monitor is not None:
                embodiment_depth = self._embodiment_monitor.get_embodiment_report().get("embodiment_depth", 0.0)

            branching_ratio = 1.0
            if self.criticality_monitor_enabled and self._criticality_monitor is not None:
                branching_ratio = self._criticality_monitor.get_branching_ratio()

            system_state = {
                "activations": activations,
                "drive_levels": drive_levels,
                "energy_levels": energies,
                "prediction_errors": prediction_errors,
                "workspace_state": workspace_state,
                "self_model_coherence": self_model_coherence,
                "embodiment_depth": embodiment_depth,
                "branching_ratio": branching_ratio,
            }

            result = self._emergent_dynamics_stabilizer.step(system_state)
            # If attractor tracker is present, record the activation state
            if self._cognitive_attractor_tracker is not None:
                self._cognitive_attractor_tracker.record_state(activations)
                self._cognitive_attractor_tracker.persist()

        # Record morphological snapshot every tick
        snapshot = self._build_morphology_snapshot(metrics)
        self._memory.record_snapshot(snapshot)

        # T162 — Cognitive Integration & Systemic Harmony
        if self.systemic_harmony_enabled and self._systemic_harmony_layer is not None:
            try:
                harmony = self._systemic_harmony_layer.tick()
                if harmony:
                    narrative = getattr(self, "_narrative_engine", None)
                    if narrative is not None:
                        narrative.record(
                            event_type="systemic_harmony_tick",
                            description=f"Harmony score: {harmony.get('aggregate_harmony', 0):.2f}",
                            importance=4,
                            metadata={"harmony": harmony},
                        )
            except Exception as exc:
                import logging
                logging.getLogger("speace.orchestrator").warning(
                    "Systemic harmony tick failed: %s", exc, exc_info=True
                )

        # System Assimilation — VFS index refresh
        if self.vfs_enabled and self._vfs_engine is not None:
            try:
                if self.current_tick % 100 == 0:
                    self._last_vfs_index = self._vfs_engine.index_root()
            except Exception as exc:
                import logging
                logging.getLogger("speace.orchestrator").warning(
                    "VFS index refresh failed: %s", exc, exc_info=True
                )

        # System Assimilation — refresh report every 200 ticks
        if self.system_assimilation_enabled and self._system_assimilator is not None:
            try:
                if self.current_tick % 200 == 0:
                    self._last_assimilation_report = self._system_assimilator.assimilate()
            except Exception as exc:
                import logging
                logging.getLogger("speace.orchestrator").warning(
                    "System assimilation refresh failed: %s", exc, exc_info=True
                )

        # Capability Gap Analyzer — every 50 ticks
        if self.current_tick % 50 == 0:
            try:
                self._run_capability_gap_analysis()
            except Exception as exc:
                import logging
                logging.getLogger("speace.orchestrator").warning(
                    "Capability gap analysis failed: %s", exc, exc_info=True
                )

        # Bottleneck Detector — every 50 ticks
        if self.current_tick % 50 == 0:
            try:
                self._run_bottleneck_detection()
            except Exception as exc:
                import logging
                logging.getLogger("speace.orchestrator").warning(
                    "Bottleneck detection failed: %s", exc, exc_info=True
                )

        # ILF — Field tick (causal broadcast at end of cycle)
        if self.ilf_enabled and self._field_integrator is not None:
            field_state = self.field_tick()
            if field_state and field_state.needs_intervention():
                pass  # Could trigger evolutionary intervention here

    def inject(self, pattern: List[float]) -> None:
        self.circuit.inject_input(pattern)

    def feedback(self, score: float) -> None:
        self.circuit.apply_feedback(score)
        if score < 0:
            self.negative_feedback_count += 1

    def run_immune(self) -> None:
        self.circuit.run_immune()

    def run_neurogenesis(self) -> None:
        metrics = self.latest_metrics
        if metrics is None:
            return
        all_neurons = (
            self.circuit.input_neurons
            + self.circuit.hidden_neurons
            + self.circuit.output_neurons
        )
        energy = metrics.mean_energy
        phi = metrics.coherence_phi
        if self._neurogenesis.should_generate(
            self.negative_feedback_count, phi, energy
        ):
            self._neurogenesis.generate_neuron(
                self.circuit,
                phi_before=phi,
                reason="recurrent_negative_feedback_and_low_phi",
                differentiation_engine=self._differentiation,
            )
            self.negative_feedback_count = 0

    def run_differentiation(self) -> None:
        metrics = self.latest_metrics
        self._differentiation.differentiate_circuit(
            self.circuit, metrics=metrics
        )

    def run_apoptosis(self) -> None:
        metrics = self.latest_metrics
        self._apoptosis.run(self.circuit, metrics=metrics)

    # ------------------------------------------------------------------ #
    # T43 — Semantic Cell Assembly Memory
    # ------------------------------------------------------------------ #

    def run_semantic_memory_cycle(self) -> "SemanticMemoryMetrics | None":
        """Run one observation-detection-reinforcement cycle for semantic memory."""
        if self._memory_coordinator is not None:
            return self._memory_coordinator.run_semantic_memory_cycle(self._build_subsystem_context())
        if self.semantic_memory_enabled and self._cell_assembly_engine is not None:
            return self._cell_assembly_engine.run_semantic_memory_cycle(self)
        return None

    def recall_semantic_memory(self, query_signature: List[float]) -> "SemanticRecallResult | None":
        """Recall a semantic memory from a query activation signature."""
        if self._memory_coordinator is not None:
            return self._memory_coordinator.recall_semantic_memory(self._build_subsystem_context(), query_signature)
        if self.semantic_memory_enabled and self._semantic_recall_engine is not None:
            return self._semantic_recall_engine.recall(query_signature)
        return None

    def get_semantic_memory_metrics(self) -> "SemanticMemoryMetrics | None":
        """Return current semantic memory metrics."""
        if self._memory_coordinator is not None:
            return self._memory_coordinator.get_semantic_memory_metrics(self._build_subsystem_context())
        if self.semantic_memory_enabled and self._cell_assembly_engine is not None:
            return self._cell_assembly_engine._compute_metrics()
        return None

    # ------------------------------------------------------------------ #
    # T44 — Associative Learning Between Assemblies
    # ------------------------------------------------------------------ #

    def get_associative_learning_engine(self):
        """Lazy initialization of the associative learning engine."""
        if self._associative_learning_engine is None:
            from speace_core.cellular_brain.memory.semantic.associative_learning_engine import (
                AssociativeLearningEngine,
            )

            self._associative_learning_engine = AssociativeLearningEngine(
                memory=self._memory,
            )
        return self._associative_learning_engine

    def get_associative_recall_engine(self):
        """Lazy initialization of the associative recall engine."""
        if self._associative_recall_engine is None:
            from speace_core.cellular_brain.memory.semantic.associative_recall_engine import (
                AssociativeRecallEngine,
            )

            self._associative_recall_engine = AssociativeRecallEngine(
                association_engine=self.get_associative_learning_engine(),
                assembly_store=self._semantic_memory_store,
                memory=self._memory,
            )
        return self._associative_recall_engine

    def run_associative_learning_cycle(self):
        """Manually run one associative learning cycle on active assemblies."""
        if self._memory_coordinator is not None:
            return self._memory_coordinator.run_associative_learning_cycle(self._build_subsystem_context())
        if (
            self.semantic_memory_enabled
            and self.associative_learning_enabled
            and self._semantic_memory_store is not None
        ):
            engine = self.get_associative_learning_engine()
            active_assemblies = self._semantic_memory_store.list_active()
            return engine.observe_assemblies(active_assemblies, tick=self.current_tick)
        return None

    def recall_associative_memory(self, cue_assembly_id: str):
        """Recall assemblies associated with a cue assembly."""
        if self._memory_coordinator is not None:
            return self._memory_coordinator.recall_associative_memory(self._build_subsystem_context(), cue_assembly_id)
        if self.associative_recall_enabled:
            engine = self.get_associative_recall_engine()
            return engine.recall_from_assembly(cue_assembly_id)
        return None

    # ------------------------------------------------------------------ #
    # T47 — Episodic Memory
    # ------------------------------------------------------------------ #

    def get_episodic_memory(self):
        if self._episodic_memory is None:
            from speace_core.cellular_brain.memory.episodic_memory import EpisodicMemory
            self._episodic_memory = EpisodicMemory(memory=self._memory)
        return self._episodic_memory

    def get_episodic_recall(self):
        if self._episodic_recall is None:
            from speace_core.cellular_brain.memory.episodic_recall import EpisodicRecall
            self._episodic_recall = EpisodicRecall(
                episodic_memory=self.get_episodic_memory(),
                memory=self._memory,
            )
        return self._episodic_recall

    def start_episode(self, trigger: str, initial_metrics=None, tick_id=0):
        if self._memory_coordinator is not None:
            return self._memory_coordinator.start_episode(
                self._build_subsystem_context(), trigger, initial_metrics, tick_id
            )
        if self.episodic_memory_enabled:
            return self.get_episodic_memory().start_episode(
                trigger=trigger,
                initial_metrics=initial_metrics or {},
                tick_id=tick_id,
            )
        return None

    def record_episode_event(self, episode_id, event_type, source_module, metrics=None, metadata=None, tick_id=0):
        if self._memory_coordinator is not None:
            return self._memory_coordinator.record_episode_event(
                self._build_subsystem_context(), episode_id, event_type, source_module, metrics, metadata, tick_id
            )
        if self.episodic_memory_enabled and episode_id:
            return self.get_episodic_memory().record_event(
                episode_id=episode_id,
                event_type=event_type,
                source_module=source_module,
                metrics=metrics,
                metadata=metadata,
                tick_id=tick_id,
            )
        return None

    def close_episode(self, episode_id, final_metrics=None, outcome="unknown"):
        if self._memory_coordinator is not None:
            return self._memory_coordinator.close_episode(
                self._build_subsystem_context(), episode_id, final_metrics, outcome
            )
        if self.episodic_memory_enabled and episode_id:
            return self.get_episodic_memory().close_episode(
                episode_id=episode_id,
                final_metrics=final_metrics or {},
                outcome=outcome,
            )
        return None

    # ------------------------------------------------------------------ #
    # Associative Pattern Completion Memory
    # ------------------------------------------------------------------ #

    def get_associative_pattern_completion(self):
        if self._associative_pattern_completion is None:
            from speace_core.cellular_brain.memory.associative_pattern_completion import (
                AssociativePatternCompletion,
            )
            self._associative_pattern_completion = AssociativePatternCompletion(
                memory=self._memory,
            )
        return self._associative_pattern_completion

    def store_pattern_completion(self, label: str, pattern: list):
        if self._memory_coordinator is not None:
            return self._memory_coordinator.store_pattern_completion(
                self._build_subsystem_context(), label, pattern
            )
        if self.associative_pattern_completion_enabled:
            engine = self.get_associative_pattern_completion()
            return engine.store_pattern(label, pattern)
        return None

    def complete_pattern(self, partial_pattern: list, threshold: float = 0.8):
        if self._memory_coordinator is not None:
            return self._memory_coordinator.complete_pattern(
                self._build_subsystem_context(), partial_pattern, threshold
            )
        if self.associative_pattern_completion_enabled:
            engine = self.get_associative_pattern_completion()
            return engine.complete_pattern(partial_pattern, threshold)
        return None

    def get_similar_pattern_states(self, query: list):
        if self._memory_coordinator is not None:
            return self._memory_coordinator.get_similar_pattern_states(
                self._build_subsystem_context(), query
            )
        if self.associative_pattern_completion_enabled:
            engine = self.get_associative_pattern_completion()
            return engine.get_similar_states(query)
        return []

    def _run_cellular_adaptive_defense_and_repair(self) -> None:
        """T42 — Run stress, damage, repair, defense, and epigenetic adaptation."""
        # Stress evaluation
        if self.cellular_adaptive_defense_enabled and self._cellular_stress_engine is not None:
            self._last_cellular_stress_result = self._cellular_stress_engine.evaluate(self.circuit)
        else:
            self._last_cellular_stress_result = None

        # Damage evaluation (requires stress)
        if self.cellular_adaptive_defense_enabled and self._cellular_damage_engine is not None and self._last_cellular_stress_result is not None:
            self._last_cellular_damage_result = self._cellular_damage_engine.evaluate(
                self.circuit,
                stress_result=self._last_cellular_stress_result,
                previous_damage=getattr(self, "_previous_damage_state", None),
            )
            self._previous_damage_state = (
                self._last_cellular_damage_result.per_cell if self._last_cellular_damage_result else {}
            )
        else:
            self._last_cellular_damage_result = None

        # Defense (requires stress and damage)
        if self.cellular_adaptive_defense_enabled and self._cellular_defense_engine is not None:
            stress_per_cell = getattr(self._last_cellular_stress_result, "per_cell", {}) or {}
            damage_per_cell = getattr(self._last_cellular_damage_result, "per_cell", {}) or {}
            self._last_cellular_defense_result = self._cellular_defense_engine.run(
                self.circuit,
                stress_per_cell=stress_per_cell,
                damage_per_cell=damage_per_cell,
                memory=self._memory,
            )
        else:
            self._last_cellular_defense_result = None

        # Repair (requires damage)
        if self.cellular_repair_enabled and self._cellular_repair_engine is not None:
            damage_per_cell = getattr(self._last_cellular_damage_result, "per_cell", {}) or {}
            self._last_cellular_repair_result = self._cellular_repair_engine.run(
                self.circuit,
                damage_per_cell=damage_per_cell,
                memory=self._memory,
            )
        else:
            self._last_cellular_repair_result = None

        # Epigenetic adaptation (requires stress and damage)
        if self.cellular_epigenetics_enabled and self._cellular_epigenetic_adapter is not None:
            stress_per_cell = getattr(self._last_cellular_stress_result, "per_cell", {}) or {}
            damage_per_cell = getattr(self._last_cellular_damage_result, "per_cell", {}) or {}
            self._last_cellular_epigenetic_result = self._cellular_epigenetic_adapter.adapt(
                self.circuit,
                stress_per_cell=stress_per_cell,
                damage_per_cell=damage_per_cell,
                current_tick=self.current_tick,
                memory=self._memory,
            )
        else:
            self._last_cellular_epigenetic_result = None

    def _run_capability_gap_analysis(self) -> None:
        if self._capability_gap_analyzer is None:
            return
        try:
            failure_memory_path = Path("data/failure_memory")
            # Try new API first, fall back to analyze_arc_failures
            if hasattr(self._capability_gap_analyzer, 'analyze_from_failures'):
                gaps = self._capability_gap_analyzer.analyze_from_failures(str(failure_memory_path))
            elif hasattr(self._capability_gap_analyzer, 'analyze_arc_failures'):
                gaps = self._capability_gap_analyzer.analyze_arc_failures({})
            else:
                gaps = []
            if gaps:
                self._last_capability_gap_report = gaps
                import logging
                logging.getLogger("speace.orchestrator").info(
                    "Capability gaps identified: %d gaps", len(gaps)
                )
        except Exception:
            pass

    def _run_bottleneck_detection(self) -> None:
        if self._bottleneck_detector is None:
            return
        try:
            failure_memory_path = Path("data/failure_memory")
            vfs_index = getattr(self, "_last_vfs_index", None)
            vfs_entry_count = len(vfs_index) if vfs_index else 0
            # Try both method names
            if hasattr(self._bottleneck_detector, 'detect'):
                report = self._bottleneck_detector.detect(
                    failure_memory_dir=str(failure_memory_path),
                    vfs_entry_count=vfs_entry_count,
                )
            elif hasattr(self._bottleneck_detector, 'analyze'):
                report = self._bottleneck_detector.analyze(
                    failure_memory_dir=str(failure_memory_path),
                    vfs_entry_count=vfs_entry_count,
                )
            else:
                report = None
            if report:
                self._last_bottleneck_report = report
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # ILF — Informational Logical Field integration
    # ------------------------------------------------------------------ #

    def _get_circuit_ilf_metrics(self) -> ILFMetrics:
        """Converte lo stato del circuito in ILFMetrics per il campo."""
        m = self.latest_metrics
        all_neurons = (
            self.circuit.input_neurons
            + self.circuit.hidden_neurons
            + self.circuit.output_neurons
        )

        # Region outputs: medie per regione
        region_outputs = {}
        if self._region_registry:
            for rid in self._region_registry.regions:
                neuron_activations = [
                    n.activation for n in all_neurons
                    if getattr(n, "region", None) == rid
                ]
                if neuron_activations:
                    region_outputs[rid] = sum(neuron_activations) / len(neuron_activations)

        # Cell states: tutte le cellule con ruolo e stato
        cell_states = {}
        cell_types = {}
        for neuron in all_neurons:
            cid = neuron.cell_id
            cell_states[cid] = neuron.activation
            cell_types[cid] = getattr(neuron, "neuron_role", "unknown")

        # Synapse states
        for synapse in self.circuit.synapses:
            sid = getattr(synapse, "synapse_id", None) or f"syn_{id(synapse)}"
            cell_states[sid] = synapse.weight * synapse.trust
            cell_types[sid] = synapse.state

        # Energy levels per regione
        energy_levels = {}
        if self._region_registry and m:
            for rid in self._region_registry.regions:
                energy_levels[rid] = m.mean_energy

        total_neurons = len(all_neurons)
        active_neurons = sum(1 for n in all_neurons if n.activation > 0.1) if all_neurons else 1

        return ILFMetrics(
            region_outputs=region_outputs,
            cell_states=cell_states,
            cell_types=cell_types,
            energy_levels=energy_levels,
            memory_utilization=active_neurons / total_neurons if total_neurons > 0 else 0.5,
            memory_retention=m.coherence_phi if m else 0.5,
            learning_rate=0.1,
            error_rate=min(1.0, m.noise_level if m else 0.1),
            goal_activations={},
            ilf_history=[],
        )

    def _on_ilf_update(self, state: FieldState) -> None:
        """ILF CAUSA aggiornamento dei parametri del circuito."""
        if not self._ilf_field_effects_enabled:
            return

        all_neurons = (
            self.circuit.input_neurons
            + self.circuit.hidden_neurons
            + self.circuit.output_neurons
        )

        # Adattamento soglie e gain basato sul campo
        for neuron in all_neurons:
            # ILF basso: aumentare soglia, ridurre gain
            if state.ilf_value < 0.4:
                neuron.threshold = min(0.9, neuron.threshold * 1.05)
                neuron.plasticity_rate = max(0.01, neuron.plasticity_rate * 0.95)
            # ILF alto: diminuire soglia, aumentare plasticita'
            elif state.ilf_value > 0.65:
                neuron.threshold = max(0.15, neuron.threshold * 0.97)
                neuron.plasticity_rate = min(1.0, neuron.plasticity_rate * 1.03)

            # Noise alto: regolazione robusta
            if state.field_noise > 0.25:
                neuron.plasticity_rate = max(0.01, neuron.plasticity_rate * 0.9)

        # Coherence in calo: rafforzare connessioni esistenti
        if state.coherence_gradient < -0.05:
            for synapse in self.circuit.synapses:
                if synapse.state == "active":
                    synapse.weight = min(1.0, synapse.weight * 1.02)

        # Adaptation bassa: aumentare esplorazione sinaptica
        if state.adaptation < 0.35:
            for synapse in self.circuit.synapses:
                if synapse.state == "active" and hasattr(synapse, "decay") and synapse.decay > 0.01:
                    synapse.decay = min(0.2, synapse.decay * 1.05)

    # ------------------------------------------------------------------ #
    # Morphology snapshot
    # ------------------------------------------------------------------ #

    def _build_morphology_snapshot(self, metrics: SystemMetrics) -> MorphologySnapshot:
        active = sum(1 for s in self.circuit.synapses if s.state != "pruned")
        weights = [s.weight for s in self.circuit.synapses if s.state != "pruned"]
        trusts = [s.trust for s in self.circuit.synapses if s.state != "pruned"]
        energies = [n.energy for n in self.circuit.input_neurons + self.circuit.hidden_neurons + self.circuit.output_neurons]
        snapshot = MorphologySnapshot(
            snapshot_id=f"snap_{self.current_tick}",
            timestamp=metrics.tick,
            tick=self.current_tick,
            neuron_count=len(self.circuit.input_neurons + self.circuit.hidden_neurons + self.circuit.output_neurons),
            synapse_count=len(self.circuit.synapses),
            active_synapse_count=active,
            pruned_synapse_count=metrics.pruned_synapses,
            average_weight=sum(weights) / len(weights) if weights else 0.0,
            average_trust=sum(trusts) / len(trusts) if trusts else 0.0,
            average_energy=sum(energies) / len(energies) if energies else 0.0,
            coherence_phi=metrics.coherence_phi,
            execution_mode=self.execution_mode,
        )
        if self.execution_mode == "event_driven_burst":
            snapshot.burst_id = self._burst_engine.burst_counter
        return snapshot

    @staticmethod
    def _flatten_sensor_snapshot(snapshot: dict) -> dict:
        """Flatten a nested CyberPhysicalSensorArray snapshot for PhysicalEnvironmentModel."""
        flat: dict = {}
        cpu = snapshot.get("cpu", {})
        flat["cpu_avg"] = cpu.get("usage_percent", 0.0) or 0.0
        mem = snapshot.get("memory", {})
        flat["mem_used"] = mem.get("used_bytes", 0.0) or 0.0
        disk = snapshot.get("disk", {})
        drives = disk.get("drives", [])
        if drives:
            flat["disk_used"] = drives[0].get("used_bytes", 0.0) or 0.0
        else:
            flat["disk_used"] = 0.0
        net = snapshot.get("network", {})
        flat["net_in"] = net.get("bytes_received", 0.0) or 0.0
        flat["net_out"] = net.get("bytes_sent", 0.0) or 0.0
        temp = snapshot.get("temperature", {})
        flat["temp_avg"] = temp.get("cpu_celsius", 0.0) or 0.0
        proc = snapshot.get("process", {})
        flat["process_count"] = proc.get("process_count", 0.0) or 0.0
        power = snapshot.get("power", {})
        flat["battery_level"] = power.get("battery_percent", 0.0) or 0.0
        return flat

    @property
    def latest_metrics(self) -> SystemMetrics | None:
        return self.metrics_log[-1] if self.metrics_log else None

    @property
    def memory(self) -> MorphologicalMemory:
        return self._memory

    @property
    def region_registry(self) -> RegionRegistry | None:
        return self._region_registry

    # ------------------------------------------------------------------ #
    # ILF — Informational Logical Field helper properties
    # ------------------------------------------------------------------ #

    @property
    def ilf_systemic_coherence_index(self) -> float:
        """SCI corrente dal campo ILF."""
        if self._field_integrator:
            return self._field_integrator.get_systemic_coherence_index()
        return 0.0

    @property
    def ilf_current_state(self) -> Optional[FieldState]:
        """Stato corrente del campo ILF."""
        if self._field_integrator:
            return self._field_integrator.get_current_state()
        return None

    @property
    def ilf_reconfiguration_count(self) -> int:
        """Numero totale di riconfigurazioni causate dal campo."""
        if self._field_integrator:
            stats = self._field_integrator.get_statistics()
            return stats.get('total_reconfigurations', 0)
        return 0

    # ------------------------------------------------------------------ #
    # T45 — Autonomous Self-Improvement Loop
    # ------------------------------------------------------------------ #

    def get_self_improvement_loop(self):
        if self._self_improvement_loop is None:
            from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
                SelfImprovementLoop,
            )
            from speace_core.cellular_brain.self_improvement.episodic_policy import (
                EpisodicSelfImprovementPolicy,
            )

            episodic_policy = None
            if self.episodic_policy_enabled and self.episodic_memory_enabled:
                episodic_policy = EpisodicSelfImprovementPolicy(
                    episodic_recall=self.get_episodic_recall(),
                    memory=self._memory,
                )

            self._self_improvement_loop = SelfImprovementLoop(
                orchestrator=self,
                memory=self._memory,
                regression_guard=getattr(self, "_regression_guard", None),
                episodic_policy_enabled=self.episodic_policy_enabled,
                episodic_policy=episodic_policy,
            )
        return self._self_improvement_loop

    def run_self_improvement_cycle(self, metrics: dict):
        loop = self.get_self_improvement_loop()
        return loop.run_detection_cycle(metrics)

    # ------------------------------------------------------------------ #
    # T54 — Controlled Perturbation & Recovery Audit
    # ------------------------------------------------------------------ #

    def get_perturbation_recovery_audit(self):
        if self._perturbation_recovery_audit is None:
            from speace_core.cellular_brain.self_organization.perturbation_recovery_audit import (
                ControlledPerturbationRecoveryAudit,
            )
            self._perturbation_recovery_audit = ControlledPerturbationRecoveryAudit(
                orchestrator=self,
            )
        return self._perturbation_recovery_audit

    async def run_perturbation_recovery_audit(self) -> list:
        if not self.perturbation_recovery_audit_enabled:
            return []
        audit = self.get_perturbation_recovery_audit()
        results = await audit.run_audit_suite()
        return results

    # T55 — EDD-CVT Evolutionary Self-Organization Kernel
    def get_edd_cvt_kernel(self):
        if self._edd_cvt_kernel is None:
            from speace_core.cellular_brain.evolutionary_kernel.edd_cvt_kernel import (
                EDDCVTEvolutionaryKernel,
            )
            self._edd_cvt_kernel = EDDCVTEvolutionaryKernel(
                orchestrator=self,
                enabled=self.edd_cvt_kernel_enabled,
            )
        return self._edd_cvt_kernel

    async def run_edd_cvt_cycle(self) -> Optional[Any]:
        if self._evolution_coordinator is not None:
            return await self._evolution_coordinator.run_edd_cvt_cycle(self._build_subsystem_context())
        if not self.edd_cvt_kernel_enabled:
            return None
        kernel = self.get_edd_cvt_kernel()
        result = await kernel.run_cycle(tick=self.current_tick)
        return result

    # T56 — Autonomous Multi-Cycle Evolution With Memory Consolidation
    def get_multi_cycle_evolution_runner(self):
        from speace_core.cellular_brain.evolutionary_kernel.multi_cycle_evolution_runner import (
            MultiCycleEvolutionRunner,
        )
        return MultiCycleEvolutionRunner(orchestrator=self)

    async def run_multi_cycle_evolution(self, cycle_count: int = 5) -> Optional[Any]:
        if self._evolution_coordinator is not None:
            return await self._evolution_coordinator.run_multi_cycle_evolution(self._build_subsystem_context(), cycle_count)
        runner = self.get_multi_cycle_evolution_runner()
        runner.cycle_count = cycle_count
        result = await runner.run()
        return result

    # T57 — Evolutionary Memory Governance Layer
    def get_evolutionary_memory_governor(self):
        if self._evolutionary_memory_governor is None:
            from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
                EvolutionaryMemoryGovernor,
            )
            self._evolutionary_memory_governor = EvolutionaryMemoryGovernor()
        return self._evolutionary_memory_governor

    async def run_evolutionary_memory_governance_cycle(self) -> Optional[dict]:
        if self._evolution_coordinator is not None:
            return await self._evolution_coordinator.run_evolutionary_memory_governance_cycle(self._build_subsystem_context())
        if not self.evolutionary_memory_governance_enabled:
            return None
        governor = self.get_evolutionary_memory_governor()
        result = governor.run_governance_cycle()
        return result

    # T58 — Metabolic Resource Governance Layer
    def get_metabolic_governor(self):
        if self._metabolic_governor is None:
            from speace_core.cellular_brain.metabolism.metabolic_governor import MetabolicGovernor
            self._metabolic_governor = MetabolicGovernor()
        return self._metabolic_governor

    async def run_metabolic_cycle(self) -> Optional[dict]:
        if self._metabolism_coordinator is not None:
            return await self._metabolism_coordinator.run_metabolic_cycle(self._build_subsystem_context())
        if not self.metabolic_governance_enabled:
            return None
        governor = self.get_metabolic_governor()
        result = governor.run_metabolic_cycle()
        return result

    def get_metabolic_state(self) -> Optional[dict]:
        if self._metabolism_coordinator is not None:
            return self._metabolism_coordinator.get_metabolic_state(self._build_subsystem_context())
        if not self.metabolic_governance_enabled:
            return None
        governor = self.get_metabolic_governor()
        state = governor.get_metabolic_state()
        return state.model_dump()

    async def run_metabolic_audit(self) -> Optional[list]:
        if self._metabolism_coordinator is not None:
            return await self._metabolism_coordinator.run_metabolic_audit(self._build_subsystem_context())
        if not self.metabolic_governance_enabled:
            return None
        from speace_core.cellular_brain.metabolism.metabolic_audit import MetabolicAudit
        governor = self.get_metabolic_governor()
        audit = MetabolicAudit(governor)
        results = audit.run_audit_suite()
        return [r.model_dump() for r in results]

    # T58B — Metabolic Resource Governance Real-Run Audit
    async def run_metabolic_real_run_audit(self) -> Optional[dict]:
        if self._metabolism_coordinator is not None:
            return await self._metabolism_coordinator.run_metabolic_real_run_audit(self._build_subsystem_context())
        if not self.metabolic_governance_enabled:
            return None
        from speace_core.cellular_brain.metabolism.metabolic_real_run_audit_runner import (
            MetabolicRealRunAuditRunner,
        )
        governor = self.get_metabolic_governor()
        runner = MetabolicRealRunAuditRunner(governor=governor)
        suite = runner.run_audit_suite()
        return suite.model_dump()

    # T59 — Organism Integration Bus
    def get_organism_bus(self):
        if self._organism_bus is None:
            from speace_core.cellular_brain.organism.organism_bus import OrganismBus
            self._organism_bus = OrganismBus()
        return self._organism_bus

    def get_organism_state(self):
        if not self.organism_integration_enabled:
            return None
        from speace_core.cellular_brain.organism.organism_state_synthesizer import (
            OrganismStateSynthesizer,
        )
        synthesizer = OrganismStateSynthesizer()
        metrics = {
            "metabolic_mode": "normal",
            "global_energy_reserve": 1.0,
            "active_subsystems": [],
            "degraded_subsystems": [],
        }
        return synthesizer.synthesize_state(metrics, tick=self.current_tick)

    async def run_organism_integration_cycle(self) -> Optional[dict]:
        if not self.organism_integration_enabled:
            return None
        from speace_core.cellular_brain.organism.cross_system_coordinator import (
            CrossSystemCoordinator,
        )
        from speace_core.cellular_brain.organism.organism_bus import OrganismBus
        from speace_core.cellular_brain.organism.subsystem_registry import (
            SubsystemRegistry,
        )
        bus = self.get_organism_bus()
        registry = SubsystemRegistry()
        coordinator = CrossSystemCoordinator(bus=bus, registry=registry)
        state = self.get_organism_state()
        if state is None:
            return None
        decisions = coordinator.coordinate_cycle(state, [])
        return {"decisions": [d.model_dump() for d in decisions], "tick": self.current_tick}

    async def run_organism_audit(self) -> Optional[dict]:
        if not self.organism_integration_enabled:
            return None
        from speace_core.cellular_brain.organism.organism_audit import OrganismAudit
        audit = OrganismAudit()
        suite = audit.run_audit_suite()
        return suite.model_dump()

    # T59B — Organism Integration Real-Run Audit
    async def run_organism_real_run_audit(self) -> Optional[dict]:
        if not self.organism_integration_enabled:
            return None
        from speace_core.cellular_brain.organism.organism_real_run_audit_runner import (
            OrganismRealRunAuditRunner,
        )
        runner = OrganismRealRunAuditRunner()
        suite = runner.run_audit_suite()
        return suite.model_dump()

    # T60 — Cyber-Physical Assimilation Interface
    def get_cyber_physical_gateway(self):
        if self._cyber_physical_gateway is None:
            from speace_core.cellular_brain.cyber_physical.assimilation_gateway import (
                AssimilationGateway,
            )
            self._cyber_physical_gateway = AssimilationGateway()
        return self._cyber_physical_gateway

    def ingest_external_signal_simulated(self, signal) -> dict:
        if not self.cyber_physical_assimilation_enabled:
            return {"error": "cyber_physical_assimilation_disabled"}
        gateway = self.get_cyber_physical_gateway()
        decision = gateway.assimilate_signal(signal)
        return decision.model_dump()

    def synthesize_world_state(self) -> Optional[dict]:
        if not self.cyber_physical_assimilation_enabled:
            return None
        gateway = self.get_cyber_physical_gateway()
        return gateway.publish_world_state_to_bus()

    async def run_cyber_physical_audit(self) -> Optional[dict]:
        if not self.cyber_physical_assimilation_enabled:
            return None
        from speace_core.cellular_brain.cyber_physical.cyber_physical_audit import (
            CyberPhysicalAudit,
        )
        audit = CyberPhysicalAudit()
        suite = audit.run_audit_suite()
        self._last_cyber_physical_audit_result = suite.model_dump()
        return self._last_cyber_physical_audit_result

    # T61 — External World Model Sandbox
    external_world_model_sandbox_enabled: bool = False
    _external_world_model_sandbox = None
    _last_world_model_audit_result = None

    def get_external_world_model_sandbox(self):
        if self._external_world_model_sandbox is None:
            from speace_core.cellular_brain.world_model.world_model_sandbox import ExternalWorldModelSandbox
            self._external_world_model_sandbox = ExternalWorldModelSandbox(seed=42)
        return self._external_world_model_sandbox

    def ingest_world_state_into_world_model(self, cp_snapshot: dict) -> Optional[dict]:
        if not self.external_world_model_sandbox_enabled:
            return {"error": "external_world_model_sandbox_disabled"}
        sandbox = self.get_external_world_model_sandbox()
        snapshot = sandbox.ingest_world_state_snapshot(cp_snapshot)
        return snapshot.model_dump()

    def run_external_world_model_scenario(self, snapshot_id: str, scenario_type: str = "baseline") -> Optional[dict]:
        if not self.external_world_model_sandbox_enabled:
            return {"error": "external_world_model_sandbox_disabled"}
        sandbox = self.get_external_world_model_sandbox()
        snapshot = sandbox._store.get_snapshot(snapshot_id)
        if snapshot is None:
            return {"error": "snapshot_not_found"}
        scenario = sandbox._scenario_builder.build_scenario_from_profile(snapshot, scenario_type)
        causal, impact = sandbox.run_scenario_simulation(snapshot, scenario)
        return {
            "causal_simulation": causal.model_dump(),
            "impact_assessment": impact.model_dump(),
        }

    async def run_external_world_model_audit(self) -> Optional[dict]:
        if not self.external_world_model_sandbox_enabled:
            return None
        from speace_core.cellular_brain.world_model.world_model_audit import WorldModelAudit
        audit = WorldModelAudit(seed=42)
        suite = audit.run_audit_suite()
        self._last_world_model_audit_result = suite.model_dump()
        return self._last_world_model_audit_result

    # T61B — External World Model Real-Run Sandbox Audit
    async def run_external_world_model_real_run_audit(self) -> Optional[dict]:
        if not self.external_world_model_sandbox_enabled:
            return None
        from speace_core.cellular_brain.world_model.world_model_real_run_audit_runner import (
            WorldModelRealRunAuditRunner,
        )
        runner = WorldModelRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        self._last_world_model_real_run_audit_result = suite.model_dump()
        return self._last_world_model_real_run_audit_result

    # T62 — External Action Governance Sandbox
    external_action_governance_enabled: bool = False
    _external_action_governance_sandbox = None
    _last_external_action_governance_audit_result = None
    _last_external_action_governance_real_run_audit_result = None

    def get_external_action_governance_sandbox(self):
        if self._external_action_governance_sandbox is None:
            from speace_core.cellular_brain.action_governance.action_governance_sandbox import (
                ExternalActionGovernanceSandbox,
            )
            self._external_action_governance_sandbox = ExternalActionGovernanceSandbox(seed=42)
        return self._external_action_governance_sandbox

    def generate_external_action_proposals(self, world_model_outputs: list) -> dict:
        if not self.external_action_governance_enabled:
            return {"error": "external_action_governance_disabled"}
        sandbox = self.get_external_action_governance_sandbox()
        proposals = sandbox.generate_action_proposals(world_model_outputs[0] if world_model_outputs else {})
        return {"proposals": [p.model_dump() for p in proposals]}

    def evaluate_external_action_proposal(self, proposal: dict) -> dict:
        if not self.external_action_governance_enabled:
            return {"error": "external_action_governance_disabled"}
        from speace_core.cellular_brain.action_governance.action_governance_models import ExternalActionProposal
        sandbox = self.get_external_action_governance_sandbox()
        p = ExternalActionProposal(**proposal)
        decision = sandbox.evaluate_action_proposal(p)
        return decision.model_dump()

    async def run_external_action_governance_audit(self) -> Optional[dict]:
        if not self.external_action_governance_enabled:
            return None
        from speace_core.cellular_brain.action_governance.action_governance_audit import (
            ActionGovernanceAudit,
        )
        audit = ActionGovernanceAudit(seed=42)
        suite = audit.run_audit_suite()
        self._last_external_action_governance_audit_result = suite.model_dump()
        return self._last_external_action_governance_audit_result

    # T62B — External Action Governance Real-Run Sandbox Audit
    async def run_external_action_governance_real_run_audit(self) -> Optional[dict]:
        if not self.external_action_governance_enabled:
            return None
        from speace_core.cellular_brain.action_governance.action_governance_real_run_audit_runner import (
            ActionGovernanceRealRunAuditRunner,
        )
        runner = ActionGovernanceRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        self._last_external_action_governance_real_run_audit_result = suite.model_dump()
        return self._last_external_action_governance_real_run_audit_result

    # T60B — Cyber-Physical Assimilation Real-Run Audit
    async def run_cyber_physical_real_run_audit(self) -> Optional[dict]:
        if not self.cyber_physical_assimilation_enabled:
            return None
        from speace_core.cellular_brain.cyber_physical.cyber_physical_real_run_audit_runner import (
            CyberPhysicalRealRunAuditRunner,
        )
        runner = CyberPhysicalRealRunAuditRunner()
        suite = runner.run_audit_suite()
        self._last_cyber_physical_real_run_audit_result = suite.model_dump()
        return self._last_cyber_physical_real_run_audit_result

    # T63 — Postnatal Learning Curriculum Engine
    postnatal_learning_enabled: bool = False
    _postnatal_curriculum_engine = None
    _last_postnatal_learning_audit_result = None

    # T64 — Developmental Capability Maturation Layer
    capability_maturation_enabled: bool = False
    _capability_maturation_layer = None
    _last_capability_maturation_audit_result = None

    def get_postnatal_curriculum_engine(self):
        if self._postnatal_curriculum_engine is None:
            from speace_core.cellular_brain.postnatal_learning.postnatal_curriculum_engine import (
                PostnatalCurriculumEngine,
            )
            self._postnatal_curriculum_engine = PostnatalCurriculumEngine(seed=42)
        return self._postnatal_curriculum_engine

    def get_postnatal_learning_state(self) -> dict:
        if not self.postnatal_learning_enabled:
            return {"error": "postnatal_learning_disabled"}
        engine = self.get_postnatal_curriculum_engine()
        return {"stages": [s.model_dump() for s in engine.get_stages()]}

    async def run_postnatal_learning_curriculum(self) -> Optional[dict]:
        if not self.postnatal_learning_enabled:
            return None
        engine = self.get_postnatal_curriculum_engine()
        return {"state": "curriculum_ready", "stages_count": len(engine.get_stages())}

    async def run_postnatal_learning_audit(self) -> Optional[dict]:
        if not self.postnatal_learning_enabled:
            return None
        from speace_core.cellular_brain.postnatal_learning.postnatal_learning_audit import (
            PostnatalLearningAudit,
        )
        audit = PostnatalLearningAudit(seed=42)
        suite = audit.run_audit_suite()
        self._last_postnatal_learning_audit_result = suite.model_dump()
        return self._last_postnatal_learning_audit_result

    async def run_postnatal_learning_real_run_audit(self) -> Optional[dict]:
        if not self.postnatal_learning_enabled:
            return None
        from speace_core.cellular_brain.postnatal_learning.postnatal_learning_real_run_audit_runner import (
            PostnatalLearningRealRunAudit,
        )
        audit = PostnatalLearningRealRunAudit(seed=42)
        suite = audit.run_audit_suite()
        self._last_postnatal_learning_real_run_audit_result = suite.model_dump()
        return self._last_postnatal_learning_real_run_audit_result

    # T64 — Developmental Capability Maturation Layer hooks
    def get_capability_maturation_layer(self):
        if self._capability_maturation_layer is None:
            from speace_core.cellular_brain.capability_maturation.capability_maturation_layer import (
                CapabilityMaturationLayer,
            )
            self._capability_maturation_layer = CapabilityMaturationLayer(seed=42)
        return self._capability_maturation_layer

    def get_capability_maturation_state(self) -> dict:
        if not self.capability_maturation_enabled:
            return {"error": "capability_maturation_disabled"}
        layer = self.get_capability_maturation_layer()
        return layer.get_state()

    async def run_capability_maturation(self) -> Optional[dict]:
        if not self.capability_maturation_enabled:
            return None
        layer = self.get_capability_maturation_layer()
        result = layer.run_maturation()
        self._last_capability_maturation_audit_result = result.model_dump()
        return self._last_capability_maturation_audit_result

    async def run_capability_maturation_audit(self) -> Optional[dict]:
        if not self.capability_maturation_enabled:
            return None
        from speace_core.cellular_brain.capability_maturation.capability_maturation_audit import (
            CapabilityMaturationAudit,
        )
        audit = CapabilityMaturationAudit(seed=42)
        result = audit.run_audit()
        self._last_capability_maturation_audit_result = result.model_dump()
        return self._last_capability_maturation_audit_result

    # T65 — Sandboxed Skill Transfer & Generalization Layer
    skill_transfer_enabled: bool = False
    _skill_transfer_layer = None
    _last_skill_transfer_audit_result = None

    async def run_capability_maturation_real_run_audit(self) -> Optional[dict]:
        if not self.capability_maturation_enabled:
            return None
        from speace_core.cellular_brain.capability_maturation.capability_maturation_real_run_audit_runner import (
            CapabilityMaturationRealRunAudit,
        )
        audit = CapabilityMaturationRealRunAudit(seed=42)
        suite = audit.run_audit_suite()
        self._last_capability_maturation_real_run_audit_result = suite.model_dump()
        return self._last_capability_maturation_real_run_audit_result

    # T71 — Global Cognitive Workspace hooks
    def get_global_workspace(self):
        if self._global_workspace is None:
            self._global_workspace = GlobalWorkspace(
                broadcast_dim=64,
                symbolic_dim=16,
                num_modules=10,
                seed=42,
                memory=self._memory,
            )
        return self._global_workspace

    def get_global_workspace_state(self) -> Optional[dict]:
        if not self.global_workspace_enabled or self._global_workspace is None:
            return None
        return self._global_workspace.get_global_state()

    def get_global_workspace_attention_focus(self) -> Optional[str]:
        if not self.global_workspace_enabled or self._global_workspace is None:
            return None
        return self._global_workspace.get_attention_focus()

    def broadcast_to_global_workspace(self, module_id: str, representation: List[float]) -> None:
        if not self.global_workspace_enabled:
            return
        gw = self.get_global_workspace()
        gw.broadcast(module_id, representation)

    # T65 hooks
    def get_skill_transfer_layer(self):
        if self._skill_transfer_layer is None:
            from speace_core.cellular_brain.skill_transfer.skill_transfer_layer import (
                SkillTransferLayer,
            )
            self._skill_transfer_layer = SkillTransferLayer(seed=42)
        return self._skill_transfer_layer

    def get_skill_transfer_state(self) -> dict:
        if not self.skill_transfer_enabled:
            return {"error": "skill_transfer_disabled"}
        layer = self.get_skill_transfer_layer()
        return layer.get_state()

    async def run_skill_transfer(self) -> Optional[dict]:
        if not self.skill_transfer_enabled:
            return None
        layer = self.get_skill_transfer_layer()
        result = layer.run_transfer()
        self._last_skill_transfer_audit_result = result.model_dump()
        return self._last_skill_transfer_audit_result

    async def run_skill_transfer_audit(self) -> Optional[dict]:
        if not self.skill_transfer_enabled:
            return None
        from speace_core.cellular_brain.skill_transfer.skill_transfer_audit import (
            SkillTransferAudit,
        )
        audit = SkillTransferAudit(seed=42)
        result = audit.run_audit()
        self._last_skill_transfer_audit_result = result.model_dump()
        return self._last_skill_transfer_audit_result

    async def run_skill_transfer_real_run_audit(self) -> Optional[dict]:
        if not self.skill_transfer_enabled:
            return None
        from speace_core.cellular_brain.skill_transfer.skill_transfer_real_run_audit_runner import (
            SkillTransferRealRunAudit,
        )
        audit = SkillTransferRealRunAudit(seed=42)
        suite = audit.run_audit_suite()
        self._last_skill_transfer_audit_result = suite.model_dump()
        return self._last_skill_transfer_audit_result

    # ------------------------------------------------------------------ #
    # ARC-AGI benchmark integration
    # ------------------------------------------------------------------ #

    async def run_arc_agi_benchmark(
        self, split: str = "training", limit: Optional[int] = None
    ) -> Dict[str, Any]:
        if self._arc_agi_adapter is None:
            raise RuntimeError(
                "ARC-AGI adapter not initialized. "
                "Enable arc_agi_benchmark_enabled in genome or set it before build."
            )
        tasks = self._arc_agi_adapter.load_tasks(split=split, limit=limit)
        result = self._arc_agi_adapter.run_benchmark(tasks=tasks)
        return result

    async def run_arc_agi_task(self, task_id: Optional[str] = None) -> List[Any]:
        if self._arc_agi_adapter is None:
            raise RuntimeError("ARC-AGI adapter not initialized.")
        tasks = self._arc_agi_adapter.load_tasks(split="training")
        task = next((t for t in tasks if t.task_id == task_id), None) if task_id else tasks[0]
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        return self._arc_agi_adapter.evaluate_task(task)

    def get_arc_agi_adapter(self) -> Any:
        return self._arc_agi_adapter

    @classmethod
    def build_mvp(cls, genome: SharedGenome, **kwargs: Any) -> "CellularBrainOrchestrator":
        n_inputs = 10
        n_hidden = 60
        n_outputs = 10
        n_synapses = 300
        n_astros = 5
        n_micro = 2
        n_oligo = 2

        input_neurons = [
            DigitalNeuron(cell_id=f"in_{i}", role="digital_neuron", threshold=0.5)
            for i in range(n_inputs)
        ]
        hidden_neurons = [
            DigitalNeuron(cell_id=f"hid_{i}", role="digital_neuron", threshold=0.5)
            for i in range(n_hidden)
        ]
        output_neurons = [
            DigitalNeuron(cell_id=f"out_{i}", role="digital_neuron", threshold=0.5)
            for i in range(n_outputs)
        ]

        all_neurons = input_neurons + hidden_neurons + output_neurons
        for n in all_neurons:
            n.bind_genome(genome)

        synapses: List[DigitalSynapse] = []
        for _ in range(n_synapses):
            src = random.choice(all_neurons)
            tgt = random.choice(all_neurons)
            if src.cell_id == tgt.cell_id:
                continue
            syn = DigitalSynapse(
                cell_id=f"syn_{src.cell_id}_{tgt.cell_id}",
                role="digital_synapse",
                source=src.cell_id,
                target=tgt.cell_id,
                weight=random.uniform(0.1, 0.9),
            )
            syn.bind_genome(genome)
            synapses.append(syn)
            src.targets.append(tgt.cell_id)

        astrocytes = [
            DigitalAstrocyte(cell_id=f"astro_{i}", role="digital_astrocyte")
            for i in range(n_astros)
        ]
        microglia = [
            DigitalMicroglia(cell_id=f"micro_{i}", role="digital_microglia")
            for i in range(n_micro)
        ]
        oligodendrocytes = [
            DigitalOligodendrocyte(cell_id=f"oligo_{i}", role="digital_oligodendrocyte")
            for i in range(n_oligo)
        ]

        circuit = NeuralCircuit(
            circuit_id="mvp_circuit",
            input_neurons=input_neurons,
            hidden_neurons=hidden_neurons,
            output_neurons=output_neurons,
            synapses=synapses,
            astrocytes=astrocytes,
            microglia=microglia,
            oligodendrocytes=oligodendrocytes,
        )

        return cls(genome=genome, circuit=circuit, **kwargs)


# --------------------------------------------------------------------------- #
# Helper: seed vocabulary for the LinguisticCognitiveBridge
# --------------------------------------------------------------------------- #

def _build_bridge_vocabulary() -> dict:
    """Seed vocabulary for the bridge's Wernicke area (8-dim semantic space)."""
    return {
        "consciousness": [0.1, 0.9, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0],
        "awareness":    [0.1, 0.9, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0],
        "coherence":    [0.0, 0.8, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0],
        "energy":       [0.0, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "thought":      [0.0, 0.6, 0.5, 0.0, 0.0, 0.4, 0.0, 0.0],
        "predict":      [0.0, 0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 0.5],
        "remember":     [0.0, 0.0, 0.3, 0.0, 0.0, 0.5, 0.0, 0.8],
        "learn":        [0.0, 0.0, 0.7, 0.0, 0.0, 0.0, 0.8, 0.0],
        "workspace":    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.9, 0.0],
        "linguistic":   [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.7],
    }
