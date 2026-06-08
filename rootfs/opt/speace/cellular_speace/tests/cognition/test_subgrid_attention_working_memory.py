import pytest

from speace_core.cellular_brain.cognition.subgrid_attention_working_memory import (
    MemorySlot,
    SubgridAttentionWorkingMemory,
)


class TestSubgridAttentionWorkingMemory:
    def test_decompose_by_objects(self):
        sawm = SubgridAttentionWorkingMemory(max_slots=4)
        grid = [
            [0, 1, 1, 0],
            [0, 1, 1, 0],
            [0, 0, 0, 2],
            [0, 0, 0, 2],
        ]
        slots = sawm.decompose_by_objects(grid)
        assert len(slots) == 2
        # Object 1 (color 1) should be 2x2
        assert len(slots[0].subgrid) == 2
        assert len(slots[0].subgrid[0]) == 2
        # Object 2 (color 2) should be 2x1
        assert len(slots[1].subgrid) == 2
        assert len(slots[1].subgrid[0]) == 1

    def test_decompose_by_patches(self):
        sawm = SubgridAttentionWorkingMemory(max_slots=4)
        grid = [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 0, 1, 2],
            [3, 4, 5, 6],
        ]
        slots = sawm.decompose_by_patches(grid, patch_size=2)
        assert len(slots) == 4
        assert slots[0].subgrid == [[1, 2], [5, 6]]
        assert slots[0].anchor == (0, 0)

    def test_attention_shift(self):
        sawm = SubgridAttentionWorkingMemory(max_slots=2)
        sawm.load_slots([MemorySlot([[1, 1]], anchor=(0, 0), slot_id=0)])
        sawm.attention_shift(0, [[2, 2]])
        assert sawm.slots[0].transformed == [[2, 2]]

    def test_compose_output(self):
        sawm = SubgridAttentionWorkingMemory(max_slots=2)
        sawm.load_slots([
            MemorySlot([[1, 1]], anchor=(0, 0), slot_id=0),
            MemorySlot([[2, 2]], anchor=(2, 0), slot_id=1),
        ])
        out = sawm.compose_output(target_size=(1, 4))
        assert out == [[1, 1, 2, 2]]

    def test_compose_with_transformed(self):
        sawm = SubgridAttentionWorkingMemory(max_slots=2)
        sawm.load_slots([
            MemorySlot([[1, 0]], anchor=(0, 0), slot_id=0),
            MemorySlot([[0, 2]], anchor=(0, 1), slot_id=1),
        ])
        sawm.attention_shift(1, [[2, 2]])
        out = sawm.compose_output(target_size=(2, 2))
        assert out[0] == [1, 0]
        assert out[1] == [2, 2]

    def test_reset(self):
        sawm = SubgridAttentionWorkingMemory(max_slots=2)
        sawm.load_slots([MemorySlot([[1]], anchor=(0, 0), slot_id=0)])
        sawm.reset()
        assert sawm.slots == []
