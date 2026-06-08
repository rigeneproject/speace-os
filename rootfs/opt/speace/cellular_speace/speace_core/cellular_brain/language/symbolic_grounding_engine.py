import json
import pathlib
from typing import Dict, Optional


class SymbolicGroundingEngine:
    """Links symbolic labels (words, concepts) to cell assemblies.

    This engine is the foundation for thought and language in SPEACE:
    it maintains bidirectional mappings between assembly IDs and
    human-readable symbolic labels, enabling grounded symbolic
    reasoning over neural substrates.
    """

    def __init__(
        self,
        store_path: Optional[pathlib.Path] = None,
    ):
        self.store_path = store_path
        self._assembly_to_label: Dict[str, str] = {}
        self._label_to_assembly: Dict[str, str] = {}

        if self.store_path and self.store_path.exists():
            self._load()

    def ground_assembly(self, assembly_id: str, label: str) -> None:
        """Associate a symbolic label to an existing cell assembly.

        Args:
            assembly_id: Unique identifier of the cell assembly.
            label: Human-readable symbolic label (word/concept).
        """
        # If label already bound to a different assembly, unbind it first
        existing_assembly = self._label_to_assembly.get(label)
        if existing_assembly and existing_assembly != assembly_id:
            self._assembly_to_label.pop(existing_assembly, None)

        # If assembly already bound to a different label, unbind it first
        existing_label = self._assembly_to_label.get(assembly_id)
        if existing_label and existing_label != label:
            self._label_to_assembly.pop(existing_label, None)

        self._assembly_to_label[assembly_id] = label
        self._label_to_assembly[label] = assembly_id
        self._persist()

    def get_label(self, assembly_id: str) -> Optional[str]:
        """Retrieve the symbolic label associated with an assembly.

        Args:
            assembly_id: Unique identifier of the cell assembly.

        Returns:
            The label string, or None if not grounded.
        """
        return self._assembly_to_label.get(assembly_id)

    def get_assembly(self, label: str) -> Optional[str]:
        """Retrieve the assembly ID associated with a symbolic label.

        Args:
            label: Human-readable symbolic label.

        Returns:
            The assembly ID string, or None if not grounded.
        """
        return self._label_to_assembly.get(label)

    def unground(self, assembly_id: Optional[str] = None, label: Optional[str] = None) -> bool:
        """Remove a grounding link by assembly_id and/or label.

        Args:
            assembly_id: Optional assembly ID to unground.
            label: Optional label to unground.

        Returns:
            True if a binding was removed, False otherwise.
        """
        removed = False

        if assembly_id and assembly_id in self._assembly_to_label:
            lbl = self._assembly_to_label.pop(assembly_id)
            self._label_to_assembly.pop(lbl, None)
            removed = True

        if label and label in self._label_to_assembly:
            aid = self._label_to_assembly.pop(label)
            self._assembly_to_label.pop(aid, None)
            removed = True

        if removed:
            self._persist()
        return removed

    def list_groundings(self) -> Dict[str, str]:
        """Return a copy of all assembly->label mappings."""
        return dict(self._assembly_to_label)

    def _persist(self) -> None:
        if self.store_path is None:
            return
        data = {
            "assembly_to_label": self._assembly_to_label,
            "label_to_assembly": self._label_to_assembly,
        }
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        if self.store_path is None or not self.store_path.exists():
            return
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            self._assembly_to_label = data.get("assembly_to_label", {})
            self._label_to_assembly = data.get("label_to_assembly", {})
        except (json.JSONDecodeError, KeyError):
            self._assembly_to_label = {}
            self._label_to_assembly = {}
