from typing import Any, Dict, List

from pydantic import BaseModel, Field


class GenomeIdentity(BaseModel):
    entity_name: str = "SPEACE"
    nature: str = "cybernetic_evolutionary_entity"
    core_function: str = "increase_systemic_coherence"
    substrate: str = "digital_physical_hybrid"
    continuity_principle: str = "preserve_identity_through_adaptive_change"


class GenomeMorphology(BaseModel):
    allowed_cell_types: List[str] = []
    allowed_tissues: List[str] = []
    organs: List[str] = []


class CellExpressionRules(BaseModel):
    role: str
    express: List[str] = []
    threshold_defaults: Dict[str, float] = Field(default_factory=dict)


class HomeostasisParams(BaseModel):
    default_threshold: float = 0.5
    default_plasticity_rate: float = 0.05
    max_energy: float = 1.0
    overload_threshold: float = 0.85
    noise_suppression_rate: float = 0.2
    energy_recovery_rate: float = 0.01


class ImmuneParams(BaseModel):
    prune_threshold: float = 0.1
    quarantine_error_limit: int = 10
    myelination_success_threshold: float = 0.8
    latency_reduction: float = 0.3


class CellDifferentiationRule(BaseModel):
    regions: List[str] = []
    role: str = ""
    threshold_modifier: float = 0.0
    plasticity_modifier: float = 1.0
    energy_profile: str = "normal"
    signal_sign: int = 1
    refractory_period: int = 0
    memory_affinity: float = 0.0
    inhibition_affinity: float = 0.0


class DynamicsParams(BaseModel):
    temporal_dynamics: Dict[str, Any] = Field(default_factory=dict)
    neural_oscillator: Dict[str, Any] = Field(default_factory=dict)
    phase_coupling: Dict[str, Any] = Field(default_factory=dict)
    energy_field: Dict[str, Any] = Field(default_factory=dict)
    predictive_coding: Dict[str, Any] = Field(default_factory=dict)
    active_inference: Dict[str, Any] = Field(default_factory=dict)
    homeostatic_drive: Dict[str, Any] = Field(default_factory=dict)
    criticality_monitor: Dict[str, Any] = Field(default_factory=dict)


class SystemAssimilationRule(BaseModel):
    path_prefix: str
    allowed_permissions: List[str] = ["read"]
    requires_approval: bool = False
    approved: bool = False


class SystemAssimilationParams(BaseModel):
    enable_vfs: bool = True
    enable_assimilation: bool = True
    root_mount_point: str = "C:\\"
    access_rules: List[SystemAssimilationRule] = Field(default_factory=lambda: [
        SystemAssimilationRule(path_prefix="C:\\", allowed_permissions=["read"], requires_approval=False),
        SystemAssimilationRule(path_prefix="C:\\cellular_speace", allowed_permissions=["read", "write"], requires_approval=False),
        SystemAssimilationRule(path_prefix="C:\\Windows\\System32", allowed_permissions=["read"], requires_approval=True),
        SystemAssimilationRule(path_prefix="C:\\Program Files", allowed_permissions=["read"], requires_approval=False),
    ])


class SharedGenome(BaseModel):
    identity: GenomeIdentity = Field(default_factory=GenomeIdentity)
    morphology: GenomeMorphology = Field(default_factory=GenomeMorphology)
    expression_rules: Dict[str, CellExpressionRules] = Field(default_factory=dict)
    homeostasis: HomeostasisParams = Field(default_factory=HomeostasisParams)
    immune: ImmuneParams = Field(default_factory=ImmuneParams)
    dynamics: DynamicsParams = Field(default_factory=DynamicsParams)
    ilf_core: Dict[str, Any] = Field(default_factory=dict)
    edd_cvt_core: Dict[str, Any] = Field(default_factory=dict)
    cell_differentiation_rules: Dict[str, CellDifferentiationRule] = Field(
        default_factory=dict
    )
    brain_regions: Dict[str, Any] = Field(default_factory=dict)
    monitoring_dashboard: Dict[str, Any] = Field(default_factory=dict)
    system_assimilation: SystemAssimilationParams = Field(default_factory=SystemAssimilationParams)

    def get_genes_for_role(self, role: str) -> List[str]:
        rules = self.expression_rules.get(role)
        if rules is None:
            return []
        return list(rules.express)

    def get_differentiation_rule(self, cell_type: str) -> CellDifferentiationRule | None:
        return self.cell_differentiation_rules.get(cell_type)
