"""AdaptivePreferenceModel — learns what SPEACE should prefer (T108).

Tracks preferences inferred from human choices, successful regulations,
and recurring interaction patterns. All read-only: preferences inform
behavior, never trigger autonomous actions.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class AdaptivePreferenceModel:
    """Learns and stores adaptive preferences."""

    def __init__(
        self,
        preferences_path: str = "data/experience/preference_model.json",
    ) -> None:
        self.preferences_path = pathlib.Path(preferences_path)
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        self._prefs: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _load(self) -> Dict[str, Any]:
        if self.preferences_path.exists():
            try:
                return json.loads(self.preferences_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "language": None,
            "voice": None,
            "monitor_host": None,
            "governance_mode": "observation_only",
            "drive_biases": {},
            "learned_at": time.time(),
        }

    def _save(self) -> None:
        try:
            with self.preferences_path.open("w", encoding="utf-8") as f:
                json.dump(self._prefs, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Preference updates
    # ------------------------------------------------------------------ #

    def set_language(self, lang: str) -> None:
        self._prefs["language"] = lang
        self._save()

    def set_voice(self, voice_name: str) -> None:
        self._prefs["voice"] = voice_name
        self._save()

    def set_monitor_host(self, host: str) -> None:
        self._prefs["monitor_host"] = host
        self._save()

    def reinforce_drive_bias(self, drive_name: str, delta: float) -> None:
        biases = self._prefs.setdefault("drive_biases", {})
        biases[drive_name] = biases.get(drive_name, 0.0) + delta
        # Clamp
        biases[drive_name] = max(-1.0, min(1.0, biases[drive_name]))
        self._save()

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: Any = None) -> Any:
        return self._prefs.get(key, default)

    def summary(self) -> Dict[str, Any]:
        return dict(self._prefs)
