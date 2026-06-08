from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.topological_som.som_engine import SOMEngine, SOMNeuron


class SOMTrainingResult(BaseModel):
    quantization_error: float = 0.0
    final_map: List[SOMNeuron] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SOMController:
    """Coordinates SOM training and evaluation."""

    def __init__(
        self,
        engine: Optional[SOMEngine] = None,
        input_dim: int = 784,
        grid_width: int = 10,
        grid_height: int = 10,
    ):
        self.engine = engine or SOMEngine(
            input_dim=input_dim,
            grid_width=grid_width,
            grid_height=grid_height,
        )

    def train(self, dataset: List[List[float]], epochs: int = 1) -> SOMTrainingResult:
        self.engine.train(dataset, epochs=epochs)
        qe = self.engine.get_quantization_error(dataset)
        return SOMTrainingResult(
            quantization_error=qe,
            final_map=self.engine.map,
        )

    def get_bmu_for(self, inputs: List[float]) -> SOMNeuron:
        return self.engine.find_bmu(inputs)
