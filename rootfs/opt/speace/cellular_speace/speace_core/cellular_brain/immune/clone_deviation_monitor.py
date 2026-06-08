from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict


class DeviationEvent(BaseModel):
    clone_id: str
    metric_name: str
    expected_value: float
    actual_value: float
    deviation_ratio: float

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DeviationReport(BaseModel):
    deviations: List[DeviationEvent] = []
    summary: str = ""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CloneDeviationMonitor:
    """Monitors deviations between distributed clone states."""

    def __init__(
        self,
        phi_tolerance: float = 0.1,
        energy_tolerance: float = 0.1,
        neuron_count_tolerance: float = 0.2,
        activation_tolerance: float = 0.3,
    ):
        self.phi_tolerance = phi_tolerance
        self.energy_tolerance = energy_tolerance
        self.neuron_count_tolerance = neuron_count_tolerance
        self.activation_tolerance = activation_tolerance

    def compare_clone_states(self, clone_states: Dict[str, Dict[str, Any]]) -> DeviationReport:
        deviations = []
        if len(clone_states) < 2:
            return DeviationReport(deviations=deviations, summary="Insufficient clones for comparison")

        metrics_keys = ["coherence_phi", "mean_energy", "neuron_count", "mean_activation"]
        for metric in metrics_keys:
            values = {
                clone_id: state.get(metric, 0.0)
                for clone_id, state in clone_states.items()
            }
            if not values:
                continue
            avg = sum(values.values()) / len(values)
            if avg == 0:
                continue
            for clone_id, val in values.items():
                ratio = abs(val - avg) / avg if avg != 0 else 0.0
                tolerance = getattr(self, f"{metric}_tolerance", 0.1)
                if ratio > tolerance:
                    deviations.append(
                        DeviationEvent(
                            clone_id=clone_id,
                            metric_name=metric,
                            expected_value=avg,
                            actual_value=val,
                            deviation_ratio=ratio,
                        )
                    )

        summary = f"Detected {len(deviations)} deviations across {len(clone_states)} clones"
        return DeviationReport(deviations=deviations, summary=summary)
