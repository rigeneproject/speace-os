"""OrganismStateCollector — read-only aggregator for SPEACE organismic state.

Collects metrics from data files and optionally from a live orchestrator instance.
All operations are read-only and safe.
"""

import json
import logging
import pathlib
from typing import Any, Dict, List, Optional


class OrganismStateCollector:
    """Collects organismic state from persistent data and optional live objects."""

    def __init__(
        self,
        data_root: str = "data",
        orchestrator: Optional[Any] = None,
    ) -> None:
        self.data_root = pathlib.Path(data_root)
        self.orchestrator = orchestrator

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _read_jsonl(path: pathlib.Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if limit and len(entries) >= limit:
                        break
        except OSError:
            return []
        return entries

    @staticmethod
    def _last_jsonl(path: pathlib.Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        last: Optional[Dict[str, Any]] = None
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        last = json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return None
        return last

    # ------------------------------------------------------------------ #
    # Body
    # ------------------------------------------------------------------ #

    def collect_body(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "cpu": 0.0,
            "memory_bytes": 0.0,
            "disk_bytes": 0.0,
            "network_bytes": 0.0,
            "temperature": 0.0,
            "processes": 0.0,
            "battery": 0.0,
            "timestamp": None,
        }

        # File fallback
        last = self._last_jsonl(self.data_root / "embodiment" / "environment_state.jsonl")
        if last and "state" in last:
            s = last["state"]
            state["cpu"] = s.get("cpu_avg", 0.0)
            state["memory_bytes"] = s.get("mem_used", 0.0)
            state["disk_bytes"] = s.get("disk_used", 0.0)
            state["network_bytes"] = s.get("net_in", 0.0) + s.get("net_out", 0.0)
            state["temperature"] = s.get("temp_avg", 0.0)
            state["processes"] = s.get("process_count", 0.0)
            state["battery"] = s.get("battery_level", 0.0)
            state["timestamp"] = last.get("timestamp")

        # Live orchestrator sensors
        if self.orchestrator is not None:
            sensor = getattr(self.orchestrator, "_last_sensor_snapshot", None)
            if sensor and isinstance(sensor, dict):
                cpu = sensor.get("cpu", {})
                mem = sensor.get("memory", {})
                disk = sensor.get("disk", {})
                net = sensor.get("network", {})
                temp = sensor.get("temperature", {})
                proc = sensor.get("process", {})
                power = sensor.get("power", {})
                state["cpu"] = cpu.get("usage_percent", state["cpu"])
                state["memory_bytes"] = mem.get("used_bytes", state["memory_bytes"])
                drives = disk.get("drives", [])
                if drives:
                    state["disk_bytes"] = drives[0].get("used_bytes", state["disk_bytes"])
                state["network_bytes"] = net.get("bytes_received", 0.0) + net.get("bytes_sent", 0.0)
                state["temperature"] = temp.get("cpu_celsius", state["temperature"])
                state["processes"] = proc.get("process_count", state["processes"])
                state["battery"] = power.get("battery_percent", state["battery"])

        return state

    # ------------------------------------------------------------------ #
    # Cognition
    # ------------------------------------------------------------------ #

    def collect_cognition(self) -> Dict[str, Any]:
        cognition: Dict[str, Any] = {
            "global_workspace": {},
            "self_model": {},
            "attention_focus": None,
            "active_goals": [],
        }

        # Global Workspace from orchestrator
        if self.orchestrator is not None:
            try:
                gw_state = self.orchestrator.get_global_workspace_state()
                if gw_state:
                    cognition["global_workspace"] = gw_state
                focus = self.orchestrator.get_global_workspace_attention_focus()
                cognition["attention_focus"] = focus
            except Exception:
                logging.getLogger(__name__).warning("State collection failed for cognition", exc_info=True)

        # Self-Model from files
        snap = self._last_jsonl(self.data_root / "self_model" / "snapshots.jsonl")
        if snap:
            cognition["self_model"] = {
                "developmental_stage": snap.get("developmental_stage", "unknown"),
                "coherence_phi": snap.get("coherence_phi", 0.0),
                "identity_vector_length": len(snap.get("identity_vector", [])),
            }
        else:
            # Fallback to identity kernel life_story last entry
            life = self._last_jsonl(self.data_root / "identity_kernel" / "life_story.jsonl")
            if life:
                cognition["self_model"] = {
                    "developmental_stage": "unknown",
                    "coherence_phi": 0.0,
                    "identity_vector_length": 0,
                    "latest_narrative": life.get("title", ""),
                }

        # Narrative trace (last 5)
        narrative = self._read_jsonl(self.data_root / "self_model" / "narrative_trace.jsonl")
        if not narrative:
            narrative = self._read_jsonl(self.data_root / "identity_kernel" / "life_story.jsonl")
        cognition["narrative_trace"] = narrative[-5:] if narrative else []

        # Active goals from drives tendency
        drives_last = self._last_jsonl(self.data_root / "drives" / "drive_history.jsonl")
        if drives_last:
            cognition["active_goals"] = [drives_last.get("action_tendency", "idle")]

        return cognition

    # ------------------------------------------------------------------ #
    # Dynamics
    # ------------------------------------------------------------------ #

    def collect_dynamics(self) -> Dict[str, Any]:
        dynamics: Dict[str, Any] = {
            "chaos_score": 0.0,
            "rigidity_score": 0.0,
            "drift": 0.0,
            "attractor_count": 0,
            "criticality": {
                "branching_ratio": 0.0,
                "near_critical": False,
            },
            "stabilizer": {
                "last_intervention": None,
                "intervention_count": 0,
            },
        }

        # Stabilizer interventions
        interventions = self._read_jsonl(self.data_root / "regulation" / "stabilizer_interventions.jsonl")
        if interventions:
            patterns = {i.get("pattern_detected") for i in interventions}
            dynamics["attractor_count"] = len(patterns)
            dynamics["stabilizer"]["intervention_count"] = len(interventions)
            last = interventions[-1]
            dynamics["stabilizer"]["last_intervention"] = {
                "tick": last.get("tick"),
                "pattern": last.get("pattern_detected"),
                "modulation": last.get("modulation"),
                "severity": last.get("severity"),
            }
            # Derive chaos/rigidity from recent patterns
            recent = interventions[-20:]
            severity_sum = sum(i.get("severity", 0.0) for i in recent)
            dynamics["chaos_score"] = min(1.0, severity_sum / max(1, len(recent)))
            rigidity_count = sum(1 for i in recent if i.get("pattern_detected") == "rigidity")
            dynamics["rigidity_score"] = rigidity_count / max(1, len(recent))

        # Morphological memory snapshots for drift
        snaps = self._read_jsonl(self.data_root / "morphological_memory" / "snapshots.jsonl")
        if len(snaps) >= 2:
            phi_values = [s.get("coherence_phi", 0.0) for s in snaps]
            dynamics["drift"] = phi_values[-1] - phi_values[0]

        # Live criticality monitor
        if self.orchestrator is not None:
            cm = getattr(self.orchestrator, "_criticality_monitor", None)
            if cm is not None:
                try:
                    dynamics["criticality"]["branching_ratio"] = cm.get_branching_ratio()
                    dynamics["criticality"]["near_critical"] = abs(cm.get_branching_ratio() - 1.0) < 0.1
                except Exception:
                    logging.getLogger(__name__).warning("State collection failed for dynamics criticality", exc_info=True)

            # Emergent dynamics stabilizer
            eds = getattr(self.orchestrator, "_emergent_dynamics_stabilizer", None)
            if eds is not None:
                try:
                    last_result = getattr(self.orchestrator, "_last_emergent_dynamics_result", None)
                    if last_result and isinstance(last_result, dict):
                        dynamics["emergent_dynamics"] = last_result
                except Exception:
                    logging.getLogger(__name__).warning("State collection failed for dynamics emergent", exc_info=True)

        return dynamics

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    def collect_identity(self) -> Dict[str, Any]:
        identity: Dict[str, Any] = {
            "distributed_nodes": [],
            "node_count": 0,
            "consensus_identity_hash": "",
            "trust_scores": {},
            "divergence_detected": False,
            "narrative_sync": [],
        }

        peers = self._read_jsonl(self.data_root / "distributed" / "identity_peers.jsonl")
        nodes = []
        consensus_hash = ""
        for entry in peers:
            if entry.get("type") == "node_registry":
                nodes = entry.get("nodes", [])
            if entry.get("type") == "identity_snapshot":
                consensus_hash = entry.get("consensus_hash", "")

        identity["distributed_nodes"] = nodes
        identity["node_count"] = len(nodes)
        identity["consensus_identity_hash"] = consensus_hash
        identity["trust_scores"] = {
            n.get("node_id", "?"): n.get("trust_score", 0.0) for n in nodes
        }
        # Divergence if any node trust is very low
        identity["divergence_detected"] = any(
            n.get("trust_score", 1.0) < 0.25 for n in nodes
        )

        # Life story / narrative sync
        life = self._read_jsonl(self.data_root / "identity_kernel" / "life_story.jsonl")
        identity["narrative_sync"] = life[-5:] if life else []

        return identity

    # ------------------------------------------------------------------ #
    # Drives
    # ------------------------------------------------------------------ #

    def collect_drives(self) -> Dict[str, Any]:
        drives_state: Dict[str, Any] = {
            "drives": [],
            "action_tendency": "idle",
            "dominant_drive": None,
        }

        last = self._last_jsonl(self.data_root / "drives" / "drive_history.jsonl")
        if last:
            drives_map = last.get("drives", {})
            drive_list = []
            max_urgency = -1.0
            dominant = None
            for key, d in drives_map.items():
                urgency = d.get("urgency", 0.0)
                drive_list.append({
                    "name": d.get("name", key),
                    "level": d.get("current_value", 0.0),
                    "priority": d.get("priority", 0.0),
                    "urgency": urgency,
                    "setpoint": d.get("setpoint", 0.0),
                })
                if urgency > max_urgency:
                    max_urgency = urgency
                    dominant = d.get("name", key)
            drives_state["drives"] = drive_list
            drives_state["action_tendency"] = last.get("action_tendency", "idle")
            drives_state["dominant_drive"] = dominant

        # Live homeostatic drive if available
        if self.orchestrator is not None:
            hd = getattr(self.orchestrator, "_homeostatic_drive", None)
            if hd is not None:
                try:
                    live_drives = []
                    for name in hd.list_drives():
                        sig = hd.get_drive_signal(name)
                        live_drives.append({
                            "name": name,
                            "level": sig,
                            "priority": 0.0,
                            "urgency": abs(sig),
                            "setpoint": 0.0,
                        })
                    if live_drives:
                        drives_state["drives"] = live_drives
                        drives_state["dominant_drive"] = max(
                            live_drives, key=lambda d: d["urgency"]
                        )["name"]
                except Exception:
                    logging.getLogger(__name__).warning("State collection failed for drives", exc_info=True)

        return drives_state

    # ------------------------------------------------------------------ #
    # Safety
    # ------------------------------------------------------------------ #

    def collect_safety(self) -> Dict[str, Any]:
        safety: Dict[str, Any] = {
            "blocked_actions": [],
            "allowed_actions": [],
            "revert_available": False,
            "risk_level": "low",
            "pending_patches": 0,
            "anomaly_flags": [],
        }

        # Stabilizer interventions as anomaly flags
        interventions = self._read_jsonl(self.data_root / "regulation" / "stabilizer_interventions.jsonl")
        recent = interventions[-10:] if interventions else []
        for i in recent:
            sev = i.get("severity", 0.0)
            if sev > 2.0:
                safety["anomaly_flags"].append({
                    "type": "stabilizer_high_severity",
                    "tick": i.get("tick"),
                    "severity": sev,
                })

        # Self-improvement proposals
        proposals = self._read_jsonl(self.data_root / "self_improvement" / "proposals.jsonl")
        pending = [p for p in proposals if p.get("status") in ("pending", "proposed")]
        safety["pending_patches"] = len(pending)
        for p in pending:
            safety["anomaly_flags"].append({
                "type": "pending_proposal",
                "proposal_id": p.get("proposal_id", "?"),
                "description": p.get("description", ""),
            })

        # Risk level synthesis
        if safety["pending_patches"] > 3 or len([f for f in safety["anomaly_flags"] if f["type"] == "stabilizer_high_severity"]) > 2:
            safety["risk_level"] = "high"
        elif safety["pending_patches"] > 0 or safety["anomaly_flags"]:
            safety["risk_level"] = "medium"

        # Orchestrator safety signals
        if self.orchestrator is not None:
            if getattr(self.orchestrator, "stabilization_recommended", False):
                safety["anomaly_flags"].append({"type": "stabilization_recommended"})
            if getattr(self.orchestrator, "plasticity_reduction_recommended", False):
                safety["anomaly_flags"].append({"type": "plasticity_reduction_recommended"})
            if getattr(self.orchestrator, "neurogenesis_recommended", False):
                safety["anomaly_flags"].append({"type": "neurogenesis_recommended"})

        return safety

    # ------------------------------------------------------------------ #
    # Embodiment (extended body / prediction error)
    # ------------------------------------------------------------------ #

    def collect_embodiment(self) -> Dict[str, Any]:
        emb: Dict[str, Any] = {
            "depth": 0.0,
            "loop_latency_ms": 0.0,
            "prediction_accuracy": 0.0,
            "action_success_rate": 0.0,
            "registered_nodes": 0,
            "sensor_status": "unknown",
            "actuator_status": "unknown",
            "prediction_error": 0.0,
        }

        if self.orchestrator is not None:
            monitor = getattr(self.orchestrator, "_embodiment_monitor", None)
            if monitor is not None:
                try:
                    report = monitor.get_embodiment_report()
                    if isinstance(report, dict):
                        emb["depth"] = report.get("embodiment_depth", 0.0)
                        emb["loop_latency_ms"] = report.get("loop_latency_ms", 0.0)
                        emb["prediction_accuracy"] = report.get("prediction_accuracy", 0.0)
                        emb["action_success_rate"] = report.get("action_success_rate", 0.0)
                except Exception:
                    logging.getLogger(__name__).warning("State collection failed for embodiment report", exc_info=True)

            # Prediction error from physical environment model
            phys = getattr(self.orchestrator, "_physical_environment", None)
            if phys is not None:
                try:
                    last_pred = getattr(self.orchestrator, "_last_predicted_state_dict", None)
                    last_sensor = getattr(self.orchestrator, "_last_sensor_snapshot", None)
                    if last_pred and last_sensor:
                        flat_actual = self._flatten_sensor(last_sensor)
                        flat_pred = self._flatten_sensor(last_pred)
                        errs = [abs(flat_actual.get(k, 0) - flat_pred.get(k, 0)) for k in set(flat_actual) | set(flat_pred)]
                        emb["prediction_error"] = sum(errs) / max(1, len(errs))
                except Exception:
                    logging.getLogger(__name__).warning("State collection failed for embodiment prediction error", exc_info=True)

            # Sensor / actuator status
            if getattr(self.orchestrator, "_sensor_array", None) is not None:
                emb["sensor_status"] = "active"
            if getattr(self.orchestrator, "_embodied_actuator", None) is not None:
                emb["actuator_status"] = "active"

        return emb

    @staticmethod
    def _flatten_sensor(snapshot: Dict[str, Any]) -> Dict[str, float]:
        """Flatten a nested sensor snapshot for comparison."""
        flat: Dict[str, float] = {}
        cpu = snapshot.get("cpu", {})
        flat["cpu_avg"] = cpu.get("usage_percent", 0.0) or 0.0
        mem = snapshot.get("memory", {})
        flat["mem_used"] = mem.get("used_bytes", 0.0) or 0.0
        disk = snapshot.get("disk", {})
        drives = disk.get("drives", [])
        flat["disk_used"] = drives[0].get("used_bytes", 0.0) or 0.0 if drives else 0.0
        net = snapshot.get("network", {})
        flat["net_in"] = net.get("bytes_received", 0.0) or 0.0
        flat["net_out"] = net.get("bytes_sent", 0.0) or 0.0
        temp = snapshot.get("temperature", {})
        flat["temp_avg"] = temp.get("cpu_celsius", 0.0) or 0.0
        proc = snapshot.get("process", {})
        flat["process_count"] = float(proc.get("process_count", 0.0) or 0.0)
        return flat

    # ------------------------------------------------------------------ #
    # Aggregate
    # ------------------------------------------------------------------ #

    def collect_all(self) -> Dict[str, Any]:
        return {
            "body": self.collect_body(),
            "cognition": self.collect_cognition(),
            "dynamics": self.collect_dynamics(),
            "identity": self.collect_identity(),
            "drives": self.collect_drives(),
            "safety": self.collect_safety(),
            "embodiment": self.collect_embodiment(),
            "timestamp": None,  # filled by metrics_bus
        }
