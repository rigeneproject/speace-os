from speace_core.cellular_brain.cells.digital_oligodendrocyte import DigitalOligodendrocyte, Pathway
from speace_core.cellular_brain.regulation.myelination_engine import MyelinationEngine


def test_myelination_engine():
    oligo = DigitalOligodendrocyte(cell_id="o1", role="digital_oligodendrocyte")
    engine = MyelinationEngine([oligo])
    pathways = [
        Pathway(path_id="p1", success_rate=0.9, use_frequency=20),
        Pathway(path_id="p2", success_rate=0.5, use_frequency=5),
    ]
    count = engine.run(pathways)
    assert count == 1
    assert pathways[0].latency == 0.7
