from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from speace_core.cellular_brain.base.digital_cell import DigitalCell
    from speace_core.dna.models import SharedGenome


class DifferentiationContext:
    def __init__(
        self,
        region: str,
        need: str,
        risk_level: float = 0.0,
        extra: Dict[str, Any] = None,
    ):
        self.region = region
        self.need = need
        self.risk_level = risk_level
        self.extra = extra or {}


class CellFactory:
    def __init__(self, genome: "SharedGenome"):
        self.genome = genome

    def differentiate(
        self,
        cell_id: str,
        context: DifferentiationContext,
    ) -> "DigitalCell":
        from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
        from speace_core.cellular_brain.cells.digital_astrocyte import DigitalAstrocyte
        from speace_core.cellular_brain.cells.digital_microglia import DigitalMicroglia
        from speace_core.cellular_brain.cells.digital_oligodendrocyte import DigitalOligodendrocyte
        from speace_core.cellular_brain.cells.auditory_neuron import AuditoryNeuron
        from speace_core.cellular_brain.cells.broca_neuron import BrocaNeuron
        from speace_core.cellular_brain.cells.wernicke_neuron import WernickeNeuron
        from speace_core.cellular_brain.cells.semantic_pointer_neuron import SemanticPointerNeuron

        role = self._resolve_role(context)
        if role not in self.genome.morphology.allowed_cell_types:
            raise ValueError(f"Role '{role}' not allowed by genome morphology")

        cell: DigitalCell
        if role == "digital_neuron":
            defaults = self.genome.expression_rules.get("digital_neuron", None)
            kwargs: Dict[str, Any] = {"cell_id": cell_id, "role": role}
            if defaults:
                kwargs["threshold"] = defaults.threshold_defaults.get("threshold", 0.5)
                kwargs["plasticity_rate"] = defaults.threshold_defaults.get("plasticity_rate", 0.05)
            cell = DigitalNeuron(**kwargs)
        elif role == "digital_astrocyte":
            cell = DigitalAstrocyte(cell_id=cell_id, role=role)
        elif role == "digital_microglia":
            cell = DigitalMicroglia(cell_id=cell_id, role=role)
        elif role == "digital_oligodendrocyte":
            cell = DigitalOligodendrocyte(cell_id=cell_id, role=role)
        elif role == "auditory_neuron":
            defaults = self.genome.expression_rules.get("auditory_neuron", None)
            kwargs: Dict[str, Any] = {"cell_id": cell_id, "role": role}
            if defaults:
                kwargs["threshold"] = defaults.threshold_defaults.get("threshold", 0.4)
                kwargs["plasticity_rate"] = defaults.threshold_defaults.get("plasticity_rate", 0.06)
            cell = AuditoryNeuron(**kwargs)
        elif role == "broca_neuron":
            defaults = self.genome.expression_rules.get("broca_neuron", None)
            kwargs = {"cell_id": cell_id, "role": role}
            if defaults:
                kwargs["threshold"] = defaults.threshold_defaults.get("threshold", 0.5)
                kwargs["plasticity_rate"] = defaults.threshold_defaults.get("plasticity_rate", 0.07)
            cell = BrocaNeuron(**kwargs)
        elif role == "wernicke_neuron":
            defaults = self.genome.expression_rules.get("wernicke_neuron", None)
            kwargs = {"cell_id": cell_id, "role": role}
            if defaults:
                kwargs["threshold"] = defaults.threshold_defaults.get("threshold", 0.45)
                kwargs["plasticity_rate"] = defaults.threshold_defaults.get("plasticity_rate", 0.08)
            cell = WernickeNeuron(**kwargs)
        elif role == "semantic_pointer_neuron":
            defaults = self.genome.expression_rules.get("semantic_pointer_neuron", None)
            kwargs = {"cell_id": cell_id, "role": role}
            if defaults:
                kwargs["threshold"] = defaults.threshold_defaults.get("threshold", 0.3)
                kwargs["plasticity_rate"] = defaults.threshold_defaults.get("plasticity_rate", 0.1)
            cell = SemanticPointerNeuron(**kwargs)
        else:
            raise ValueError(f"Unknown role '{role}'")

        cell.bind_genome(self.genome)
        return cell

    def _resolve_role(self, context: DifferentiationContext) -> str:
        if context.risk_level > 0.7:
            return "digital_microglia"
        mapping = {
            ("brain", "memory"): "digital_neuron",
            ("brain", "processing"): "digital_neuron",
            ("brain", "regulation"): "digital_astrocyte",
            ("brain", "optimization"): "digital_oligodendrocyte",
            ("language", "auditory"): "auditory_neuron",
            ("language", "comprehension"): "wernicke_neuron",
            ("language", "production"): "broca_neuron",
            ("language", "symbolic_grounding"): "semantic_pointer_neuron",
        }
        return mapping.get((context.region, context.need), "digital_neuron")
