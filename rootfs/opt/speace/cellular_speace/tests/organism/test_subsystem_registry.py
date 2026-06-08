import pytest

from speace_core.cellular_brain.organism import SubsystemRegistry, SubsystemStatus


def test_subsystem_registry_registers_subsystem():
    reg = SubsystemRegistry()
    status = reg.register_subsystem("safety")
    assert status.subsystem_name == "safety"
    assert reg.get_status("safety") is not None


def test_registry_blocks_disabled_subsystem_routing():
    reg = SubsystemRegistry()
    reg.register_subsystem("evo")
    reg.get_status("evo").enabled = False
    active = reg.list_active()
    assert "evo" not in active


def test_registry_marks_degraded_subsystem():
    reg = SubsystemRegistry()
    reg.register_subsystem("bench")
    assert reg.mark_degraded("bench", reason="overload") is True
    assert reg.get_status("bench").degraded is True
    assert reg.list_degraded() == ["bench"]


def test_registry_update_status():
    reg = SubsystemRegistry()
    reg.register_subsystem("mem")
    new_status = SubsystemStatus(subsystem_name="mem", health_score=0.5)
    assert reg.update_status("mem", new_status) is True
    assert reg.get_status("mem").health_score == 0.5


def test_registry_update_missing_subsystem():
    reg = SubsystemRegistry()
    assert reg.update_status("missing", SubsystemStatus(subsystem_name="missing")) is False


def test_registry_mark_degraded_missing():
    reg = SubsystemRegistry()
    assert reg.mark_degraded("missing") is False


def test_registry_list_active_excludes_degraded():
    reg = SubsystemRegistry()
    reg.register_subsystem("a")
    reg.register_subsystem("b")
    reg.mark_degraded("b")
    assert reg.list_active() == ["a"]


def test_registry_snapshot():
    reg = SubsystemRegistry()
    reg.register_subsystem("safety")
    snap = reg.snapshot()
    assert snap["active_count"] == 1
    assert snap["degraded_count"] == 0
