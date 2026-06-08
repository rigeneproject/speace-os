import json
import time
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

from speace_core.persistence.persistent_object import PersistentObject

T = TypeVar("T", bound=PersistentObject)


class PersistentStore(Generic[T]):
    """Append-only JSONL-backed store for PersistentObject subclasses."""

    def __init__(
        self,
        model_class: Type[T],
        store_name: str,
        data_dir: str = "data/persistence",
        compaction_interval: int = 1000,
    ):
        self._model_class = model_class
        self._store_name = store_name
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._data_dir / f"{store_name}.jsonl"
        self._compaction_interval = compaction_interval
        self._objects: Dict[str, T] = {}
        self._lock = Lock()
        self._write_count = 0
        self._load()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def put(self, obj: T) -> str:
        with self._lock:
            obj.updated_at = time.time()
            self._objects[obj.persistent_id] = obj
            self._append(obj)
            self._write_count += 1
            if self._write_count >= self._compaction_interval:
                self._compact()
                self._write_count = 0
            return obj.persistent_id

    def get(self, persistent_id: str) -> Optional[T]:
        with self._lock:
            obj = self._objects.get(persistent_id)
            if obj is not None and obj.deleted:
                return None
            return obj

    def delete(self, persistent_id: str) -> bool:
        with self._lock:
            obj = self._objects.get(persistent_id)
            if obj is None or obj.deleted:
                return False
            obj.deleted = True
            obj.updated_at = time.time()
            self._append(obj)
            self._write_count += 1
            return True

    def query(
        self,
        *,
        object_type: Optional[str] = None,
        tick_min: Optional[int] = None,
        tick_max: Optional[int] = None,
        predicate: Optional[Callable[[T], bool]] = None,
    ) -> List[T]:
        results: List[T] = []
        with self._lock:
            for obj in self._objects.values():
                if obj.deleted:
                    continue
                if object_type is not None and obj.object_type != object_type:
                    continue
                if tick_min is not None and obj.tick < tick_min:
                    continue
                if tick_max is not None and obj.tick > tick_max:
                    continue
                if predicate is not None and not predicate(obj):
                    continue
                results.append(obj)
        return results

    def list_all(self, object_type: Optional[str] = None) -> List[T]:
        return self.query(object_type=object_type)

    def count(self, object_type: Optional[str] = None) -> int:
        return len(self.list_all(object_type=object_type))

    def clear(self) -> None:
        with self._lock:
            self._objects.clear()
            self._write_count = 0

    # ------------------------------------------------------------------ #
    # Bulk operations
    # ------------------------------------------------------------------ #

    def snapshot(self, objects: List[T]) -> int:
        written = 0
        with self._lock:
            for obj in objects:
                obj.updated_at = time.time()
                self._objects[obj.persistent_id] = obj
                self._append(obj)
                written += 1
            self._write_count += written
            if self._write_count >= self._compaction_interval:
                self._compact()
                self._write_count = 0
        return written

    def load(self) -> int:
        with self._lock:
            self._objects.clear()
            return self._load()

    # ------------------------------------------------------------------ #
    # Internal persistence
    # ------------------------------------------------------------------ #

    def _append(self, obj: T) -> None:
        line = obj.model_dump_json()
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _load(self) -> int:
        if not self._file_path.exists():
            return 0
        count = 0
        with open(self._file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    obj = self._model_class.model_validate(data)
                    self._objects[obj.persistent_id] = obj
                    count += 1
                except Exception:
                    continue
        return count

    def _compact(self) -> None:
        alive = [obj for obj in self._objects.values() if not obj.deleted]
        temp_path = self._file_path.with_suffix(".jsonl.tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            for obj in alive:
                f.write(obj.model_dump_json() + "\n")
        temp_path.replace(self._file_path)
