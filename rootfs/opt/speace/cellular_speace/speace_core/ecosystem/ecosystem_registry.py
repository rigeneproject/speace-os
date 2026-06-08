"""EcosystemRegistry — manages external source registration and lifecycle."""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.ecosystem.ecosystem_state import EcosystemSource


class EcosystemRegistry:
    """Registry of external ecosystem sources."""

    def __init__(self, data_root: str = "data/ecosystem") -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._sources: Dict[str, EcosystemSource] = {}
        self._config_path = self._data_root / "sources.json"
        self._load_sources()

    def register(self, source: EcosystemSource) -> None:
        """Add or update a source."""
        self._sources[source.source_id] = source
        self._persist()

    def unregister(self, source_id: str) -> bool:
        """Remove a source."""
        removed = source_id in self._sources
        self._sources.pop(source_id, None)
        if removed:
            self._persist()
        return removed

    def get(self, source_id: str) -> Optional[EcosystemSource]:
        return self._sources.get(source_id)

    def list_sources(self, active_only: bool = False) -> List[EcosystemSource]:
        sources = list(self._sources.values())
        if active_only:
            sources = [s for s in sources if s.active]
        return sources

    def update_trust(self, source_id: str, delta: float) -> None:
        source = self._sources.get(source_id)
        if source is None:
            return
        source.trust_score = max(0.0, min(1.0, source.trust_score + delta))
        if source.trust_score < 0.2:
            source.active = False
            source.boundary_status = "observed"
        self._persist()

    def touch(self, source_id: str) -> None:
        source = self._sources.get(source_id)
        if source is not None:
            source.last_seen = time.time()

    def update_boundary_status(self, source_id: str, status: str) -> bool:
        source = self._sources.get(source_id)
        if source is None or status not in ("observed", "trusted", "assimilated"):
            return False
        source.boundary_status = status
        self._persist()
        return True

    def _persist(self) -> None:
        try:
            data = [s.model_dump(mode="json") for s in self._sources.values()]
            self._config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load_sources(self) -> None:
        if not self._config_path.exists():
            return
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            for item in data:
                source = EcosystemSource(**item)
                self._sources[source.source_id] = source
        except (json.JSONDecodeError, OSError, TypeError):
            pass
