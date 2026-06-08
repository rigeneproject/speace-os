"""DashboardStateReader — read-only state aggregator for the SPEACE dashboard."""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class DashboardStateReader:
    """Reads SPEACE state from JSONL data files.  All methods are read-only."""

    def __init__(self, data_root: str = "data") -> None:
        self.data_root = pathlib.Path(data_root)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _read_jsonl(self, path: pathlib.Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read lines from a JSONL file safely."""
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

    def _last_jsonl(self, path: pathlib.Path) -> Optional[Dict[str, Any]]:
        """Return the last valid JSON object from a JSONL file."""
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
    # Data sources
    # ------------------------------------------------------------------ #

    def _read_embodiment(self) -> Dict[str, Any]:
        last = self._last_jsonl(self.data_root / "embodiment" / "environment_state.jsonl")
        if last is None:
            return {
                "cpu": 0.0,
                "memory": 0.0,
                "disk": 0.0,
                "network": 0.0,
                "processes": 0.0,
                "temperature": 0.0,
                "battery": 0.0,
            }
        state = last.get("state", {})
        return {
            "cpu": state.get("cpu_avg", 0.0),
            "memory": state.get("mem_used", 0.0),
            "disk": state.get("disk_used", 0.0),
            "network": state.get("net_in", 0.0) + state.get("net_out", 0.0),
            "processes": state.get("process_count", 0.0),
            "temperature": state.get("temp_avg", 0.0),
            "battery": state.get("battery_level", 0.0),
        }

    def _read_drives(self) -> List[Dict[str, Any]]:
        last = self._last_jsonl(self.data_root / "drives" / "drive_history.jsonl")
        if last is None:
            return []
        drives = last.get("drives", {})
        return [
            {
                "name": d.get("name", key),
                "level": d.get("current_value", 0.0),
                "priority": d.get("priority", 0.0),
                "tendency": last.get("action_tendency", "idle"),
            }
            for key, d in drives.items()
        ]

    def _read_self_model(self) -> Dict[str, Any]:
        base = self.data_root / "self_model"
        last_snapshot = self._last_jsonl(base / "snapshots.jsonl")
        narrative = self._read_jsonl(base / "narrative_trace.jsonl")
        narrative = narrative[-5:] if narrative else []
        return {
            "identity_signature": last_snapshot.get("identity_vector", []) if last_snapshot else [],
            "developmental_stage": last_snapshot.get("developmental_stage", "unknown") if last_snapshot else "unknown",
            "coherence": last_snapshot.get("coherence_phi", 0.0) if last_snapshot else 0.0,
            "narrative": narrative,
        }

    def _read_workspace(self) -> Dict[str, Any]:
        # Workspace is not yet persisted to disk in SPEACE; return defaults.
        return {
            "global_state": "active",
            "attention_focus": None,
            "awareness_level": 0.0,
        }

    def _read_stabilizer(self) -> Dict[str, Any]:
        interventions = self._read_jsonl(self.data_root / "regulation" / "stabilizer_interventions.jsonl")
        if not interventions:
            return {
                "last_intervention": None,
                "attractor_count": 0,
                "stability_score": 1.0,
            }
        last = interventions[-1]
        return {
            "last_intervention": {
                "tick": last.get("tick"),
                "pattern": last.get("pattern_detected"),
                "modulation": last.get("modulation"),
            },
            "attractor_count": len({i.get("pattern_detected") for i in interventions}),
            "stability_score": 1.0 - min(last.get("severity", 0.0), 1.0),
        }

    def _read_distributed(self) -> Dict[str, Any]:
        peers = self._read_jsonl(self.data_root / "distributed" / "identity_peers.jsonl")
        nodes = []
        consensus_hash = ""
        for entry in peers:
            if entry.get("type") == "node_registry":
                nodes = entry.get("nodes", [])
            if entry.get("type") == "identity_snapshot":
                consensus_hash = entry.get("consensus_hash", "")
        return {
            "node_count": len(nodes),
            "consensus_identity_hash": consensus_hash,
            "nodes": nodes,
        }

    def _read_social(self) -> Dict[str, Any]:
        # Social cognition state is not yet persisted; return empty defaults.
        return {
            "agent_count": 0,
            "average_trust": 0.0,
            "cooperation_rate": 0.0,
            "agents": [],
        }

    def _read_embodiment_meta(self) -> Dict[str, Any]:
        # Embodiment metadata not yet persisted; return defaults.
        return {
            "depth": 0.0,
            "loop_latency_ms": 0.0,
            "prediction_accuracy": 0.0,
            "action_success_rate": 0.0,
        }

    def _read_organismic_summary(self) -> Dict[str, Any]:
        # Prefer morphological memory snapshots, fall back to stabilizer/embodiment.
        snapshots = self._read_jsonl(self.data_root / "morphological_memory" / "snapshots.jsonl")
        if snapshots:
            latest = snapshots[-1]
            return {
                "ticks": latest.get("tick", 0),
                "coherence_phi": latest.get("coherence_phi", 0.0),
                "mean_energy": latest.get("average_energy", 0.0),
                "active_neurons": latest.get("active_synapse_count", 0),
                "pruned_count": latest.get("pruned_synapse_count", 0),
            }
        # Fallback: try to infer from available data
        env = self._last_jsonl(self.data_root / "embodiment" / "environment_state.jsonl")
        stab = self._read_jsonl(self.data_root / "regulation" / "stabilizer_interventions.jsonl")
        return {
            "ticks": (stab[-1].get("tick", 0) if stab else 0),
            "coherence_phi": 0.0,
            "mean_energy": 0.0,
            "active_neurons": 0,
            "pruned_count": 0,
        }

    def _read_narrative(self) -> List[Dict[str, Any]]:
        # life_story is the autobiographical identity kernel narrative
        life_story = self._read_jsonl(self.data_root / "identity_kernel" / "life_story.jsonl")
        return life_story[-5:] if life_story else []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_current_state(self) -> Dict[str, Any]:
        return {
            "organismic_summary": self._read_organismic_summary(),
            "workspace": self._read_workspace(),
            "self_model": self._read_self_model(),
            "sensors": self._read_embodiment(),
            "drives": self._read_drives(),
            "embodiment": self._read_embodiment_meta(),
            "stabilizer": self._read_stabilizer(),
            "distributed": self._read_distributed(),
            "social": self._read_social(),
            "narrative": self._read_narrative(),
        }

    def get_history(self, metric: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return historical data points for a given metric."""
        # Supported metrics from morphological snapshots
        snapshots = self._read_jsonl(self.data_root / "morphological_memory" / "snapshots.jsonl")
        if snapshots:
            data = []
            for snap in snapshots[-limit:]:
                tick = snap.get("tick", 0)
                value = snap.get(metric)
                if value is None:
                    # Map common aliases
                    if metric == "mean_energy":
                        value = snap.get("average_energy")
                    elif metric == "active_neurons":
                        value = snap.get("active_synapse_count")
                    elif metric == "pruned_count":
                        value = snap.get("pruned_synapse_count")
                if value is not None:
                    data.append({"tick": tick, "value": value})
            return data

        # Fallback: embodiment history for cpu / memory
        if metric in ("cpu", "memory", "temperature"):
            entries = self._read_jsonl(self.data_root / "embodiment" / "environment_state.jsonl")
            key_map = {
                "cpu": "cpu_avg",
                "memory": "mem_used",
                "temperature": "temp_avg",
            }
            data = []
            for entry in entries[-limit:]:
                ts = entry.get("timestamp", "")
                val = entry.get("state", {}).get(key_map[metric])
                if val is not None:
                    data.append({"timestamp": ts, "value": val})
            return data

        # Fallback: stabilizer severity as stability_score
        if metric == "stability_score":
            entries = self._read_jsonl(self.data_root / "regulation" / "stabilizer_interventions.jsonl")
            data = []
            for entry in entries[-limit:]:
                tick = entry.get("tick", 0)
                severity = entry.get("severity", 0.0)
                data.append({"tick": tick, "value": 1.0 - min(severity, 1.0)})
            return data

        return []

    def get_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        events = self._read_jsonl(self.data_root / "morphological_memory" / "events.jsonl")
        return events[-limit:] if events else []
