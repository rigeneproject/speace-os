from speace_core.cellular_brain.cells.digital_oligodendrocyte import DigitalOligodendrocyte, Pathway


def test_myelinate():
    oligo = DigitalOligodendrocyte(cell_id="o1", role="digital_oligodendrocyte")
    path = Pathway(path_id="p1", success_rate=0.9, use_frequency=20, latency=1.0, energy_cost=1.0)
    oligo.myelinate(path)
    assert path.latency == 0.7
    assert path.energy_cost == 0.6
    assert path.priority == 0.2
