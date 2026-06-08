import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Drive:
    """A single autonomous drive with homeostatic setpoint dynamics."""

    name: str
    setpoint: float
    weight: float
    current_value: float = 0.0
    activation_threshold: float = 0.1
    priority: float = 0.0

    def compute_urgency(self) -> float:
        """Return unsigned urgency: how far are we from the setpoint."""
        return abs(self.current_value - self.setpoint) * self.weight

    def is_active(self) -> bool:
        """A drive is considered active when its urgency exceeds the activation threshold."""
        return self.compute_urgency() >= self.activation_threshold

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "setpoint": self.setpoint,
            "weight": self.weight,
            "current_value": self.current_value,
            "activation_threshold": self.activation_threshold,
            "priority": self.priority,
            "urgency": self.compute_urgency(),
        }


class AutonomousDriveEngine:
    """Long-term autonomous drive system — the motivational core that keeps SPEACE alive.

    Core drives and their biological analogues:
    - self_preservation      -> avoid shutdown / crash  (survival)
    - energy_conservation    -> minimize consumption when idle  (rest/thirst)
    - resource_acquisition   -> seek more compute / memory / disk  (hunger)
    - information_exploration -> read logs / monitor / learn  (curiosity)
    - homeostatic_equilibrium -> keep internal state stable  (temperature)
    - adaptive_exploration    -> try new strategies when old ones fail  (play)
    - coherence_maintenance   -> keep identity / narrative consistent  (self-integrity)
    """

    # Mapping from drive names to recommended global actions
    _ACTION_MAP: Dict[str, str] = {
        "self_preservation": "repair",
        "energy_conservation": "conserve",
        "resource_acquisition": "acquire",
        "information_exploration": "explore",
        "homeostatic_equilibrium": "stabilize",
        "adaptive_exploration": "adapt",
        "coherence_maintenance": "integrate",
    }

    # Sensor keys that the step() method knows how to translate
    _SENSOR_TO_DRIVE: Dict[str, str] = {
        "cpu_usage": "energy_conservation",
        "memory_usage": "energy_conservation",
        "disk_usage": "resource_acquisition",
        "error_rate": "self_preservation",
        "uptime": "self_preservation",
        "novelty_score": "information_exploration",
        "coherence": "coherence_maintenance",
        "strategy_failure_rate": "adaptive_exploration",
        "internal_variance": "homeostatic_equilibrium",
        "idle_ratio": "energy_conservation",
    }

    def __init__(
        self,
        history_path: str = "data/drives/drive_history.jsonl",
        suppression_self_preservation: float = 0.5,
        suppression_energy: float = 0.4,
    ):
        self._drives: Dict[str, Drive] = {}
        self._history_path = Path(history_path)
        self._history_path.parent.mkdir(parents=True, exist_ok=True)

        self.suppression_self_preservation = suppression_self_preservation
        self.suppression_energy = suppression_energy

        # Register the seven core drives
        self.register_drive(
            name="self_preservation",
            setpoint=0.9,
            weight=1.5,
            activation_threshold=0.15,
        )
        self.register_drive(
            name="energy_conservation",
            setpoint=0.7,
            weight=1.2,
            activation_threshold=0.1,
        )
        self.register_drive(
            name="resource_acquisition",
            setpoint=0.5,
            weight=1.0,
            activation_threshold=0.1,
        )
        self.register_drive(
            name="information_exploration",
            setpoint=0.5,
            weight=1.0,
            activation_threshold=0.1,
        )
        self.register_drive(
            name="homeostatic_equilibrium",
            setpoint=0.8,
            weight=1.3,
            activation_threshold=0.1,
        )
        self.register_drive(
            name="adaptive_exploration",
            setpoint=0.4,
            weight=1.1,
            activation_threshold=0.1,
        )
        self.register_drive(
            name="coherence_maintenance",
            setpoint=0.85,
            weight=1.4,
            activation_threshold=0.1,
        )

    # ------------------------------------------------------------------ #
    # Drive management
    # ------------------------------------------------------------------ #

    def register_drive(
        self,
        name: str,
        setpoint: float,
        weight: float,
        activation_threshold: float = 0.1,
    ) -> None:
        """Register a new drive or overwrite an existing one."""
        self._drives[name] = Drive(
            name=name,
            setpoint=setpoint,
            weight=weight,
            current_value=setpoint,  # start at equilibrium
            activation_threshold=activation_threshold,
        )

    def update_drive(self, name: str, current_value: float) -> None:
        """Update the current level of a registered drive."""
        if name not in self._drives:
            raise KeyError(f"Drive '{name}' is not registered")
        self._drives[name].current_value = float(current_value)

    def get_drive(self, name: str) -> Drive:
        """Return the Drive instance for inspection."""
        if name not in self._drives:
            raise KeyError(f"Drive '{name}' is not registered")
        return self._drives[name]

    def list_drives(self) -> List[str]:
        """Return names of all registered drives."""
        return list(self._drives.keys())

    # ------------------------------------------------------------------ #
    # Priority & urgency
    # ------------------------------------------------------------------ #

    def get_drive_priority(self, name: str) -> float:
        """Return the urgency of a drive: |current - setpoint| * weight."""
        if name not in self._drives:
            raise KeyError(f"Drive '{name}' is not registered")
        return self._drives[name].compute_urgency()

    def get_highest_priority_drive(self) -> Optional[Tuple[str, float]]:
        """Return (name, urgency) of the drive with the highest urgency."""
        if not self._drives:
            return None
        return max(
            ((name, d.compute_urgency()) for name, d in self._drives.items()),
            key=lambda x: x[1],
        )

    # ------------------------------------------------------------------ #
    # Global action tendency
    # ------------------------------------------------------------------ #

    def get_global_action_tendency(self) -> str:
        """Return a weighted recommendation of what the organism should do next.

        Interactions applied:
        - High self-preservation urgency suppresses exploration.
        - Low energy (high conservation urgency) suppresses resource acquisition.
        """
        if not self._drives:
            return "idle"

        # Raw urgencies
        urgencies = {name: d.compute_urgency() for name, d in self._drives.items()}

        # --- interactions ---
        sp_urgency = urgencies.get("self_preservation", 0.0)
        if sp_urgency > self.suppression_self_preservation:
            # High survival need suppresses exploration drives
            for explore_name in ("information_exploration", "adaptive_exploration"):
                if explore_name in urgencies:
                    urgencies[explore_name] *= 0.3

        ec_urgency = urgencies.get("energy_conservation", 0.0)
        if ec_urgency > self.suppression_energy:
            # Low energy suppresses resource acquisition
            if "resource_acquisition" in urgencies:
                urgencies["resource_acquisition"] *= 0.3

        # Compute weighted action scores
        action_scores: Dict[str, float] = {}
        for name, urgency in urgencies.items():
            if urgency <= 0:
                continue
            action = self._ACTION_MAP.get(name, "idle")
            action_scores[action] = action_scores.get(action, 0.0) + urgency

        if not action_scores:
            return "idle"
        return max(action_scores, key=action_scores.get)

    # ------------------------------------------------------------------ #
    # Step
    # ------------------------------------------------------------------ #

    def step(self, current_state: Dict[str, Any]) -> str:
        """Update all drives based on current sensor readings and return action tendency.

        Sensor mappings (custom drives can be updated directly by the caller):
        - cpu_usage / memory_usage / idle_ratio  -> energy_conservation
        - disk_usage                              -> resource_acquisition
        - error_rate / uptime                     -> self_preservation
        - novelty_score                           -> information_exploration
        - coherence                               -> coherence_maintenance
        - strategy_failure_rate                   -> adaptive_exploration
        - internal_variance                       -> homeostatic_equilibrium
        """
        for sensor_key, drive_name in self._SENSOR_TO_DRIVE.items():
            if sensor_key in current_state and drive_name in self._drives:
                raw_value = float(current_state[sensor_key])
                # Some sensors need inversion to map to a 0-1 drive value
                inverted = self._invert_sensor_if_needed(sensor_key, raw_value)
                self.update_drive(drive_name, inverted)

        tendency = self.get_global_action_tendency()
        self._persist_history(tendency, current_state)
        return tendency

    @staticmethod
    def _invert_sensor_if_needed(sensor_key: str, raw_value: float) -> float:
        """Convert raw sensor values into 0-1 drive levels.

        For example uptime maps directly (higher = healthier), whereas
        error_rate is inverted (higher error = lower preservation).
        """
        if sensor_key == "error_rate":
            return max(0.0, 1.0 - raw_value)
        if sensor_key == "strategy_failure_rate":
            return max(0.0, 1.0 - raw_value)
        if sensor_key == "internal_variance":
            return max(0.0, 1.0 - raw_value)
        if sensor_key == "idle_ratio":
            # More idle -> higher conservation score (we are already conserving)
            return raw_value
        if sensor_key in ("cpu_usage", "memory_usage", "disk_usage"):
            # Higher usage -> lower remaining capacity -> drive level drops
            return max(0.0, 1.0 - raw_value)
        # Default pass-through
        return max(0.0, min(1.0, raw_value))

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_history(self, tendency: str, sensors: Dict[str, Any]) -> None:
        """Append a snapshot of the current drive state to the JSONL history."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_tendency": tendency,
            "drives": {name: d.to_snapshot() for name, d in self._drives.items()},
            "sensors": dict(sensors),
        }
        with open(self._history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_history(self) -> List[Dict[str, Any]]:
        """Load the full drive history from the JSONL file."""
        results: List[Dict[str, Any]] = []
        if not self._history_path.exists():
            return results
        with open(self._history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                results.append(json.loads(line))
        return results

    def clear_history(self) -> None:
        """Delete the history file if it exists."""
        if self._history_path.exists():
            self._history_path.unlink()

    # ------------------------------------------------------------------ #
    # Summary / inspection
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        """Return a full serialisable snapshot of the drive engine."""
        highest = self.get_highest_priority_drive()
        return {
            "drives": {name: d.to_snapshot() for name, d in self._drives.items()},
            "highest_priority_drive": highest[0] if highest else None,
            "action_tendency": self.get_global_action_tendency(),
            "active_drive_count": sum(1 for d in self._drives.values() if d.is_active()),
        }

    def get_drive_balance(self) -> float:
        """Return a measure of how balanced the drive landscape is (0 = perfectly balanced, 1 = lopsided).

        Uses normalized Shannon entropy of urgencies.
        """
        if not self._drives:
            return 0.0
        urgencies = [d.compute_urgency() for d in self._drives.values()]
        total = sum(urgencies)
        if total == 0:
            return 0.0
        entropy = -sum(
            (u / total) * math.log(u / total + 1e-12) for u in urgencies
        )
        max_entropy = math.log(len(urgencies))
        if max_entropy == 0:
            return 0.0
        return 1.0 - (entropy / max_entropy)
