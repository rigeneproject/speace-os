"""CoherenceObserver — T154-A Read-only Coherence Observer.

Observes systemic harmony without modifying anything. Produces coherence
reports with metrics:

- modular coherence
- redundancy efficiency
- causal clarity
- symmetry/asymmetry balance
- narrative coherence
- cognitive entropy
- regulation density
- mutation stability
- energy efficiency
- functional elegance
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class CoherenceObserver:
    """Read-only observer of systemic coherence."""

    def __init__(
        self,
        project_root: Optional[str] = None,
        data_root: str = "data/analysis/coherence",
    ) -> None:
        if project_root is None:
            # speace_core/cellular_brain/analysis/ → project root
            self._project_root = Path(__file__).resolve().parents[3]
        else:
            self._project_root = Path(project_root)
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._report_path = self._data_root / "coherence_reports.jsonl"

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def observe(self) -> Dict[str, Any]:
        """Run a full coherence observation and return the report."""
        report = {
            "run_id": f"coh_{int(time.time())}",
            "timestamp": time.time(),
            "metrics": {
                "modular_coherence": self._modular_coherence(),
                "redundancy_efficiency": self._redundancy_efficiency(),
                "causal_clarity": self._causal_clarity(),
                "symmetry_asymmetry_balance": self._symmetry_asymmetry_balance(),
                "narrative_coherence": self._narrative_coherence(),
                "cognitive_entropy": self._cognitive_entropy(),
                "regulation_density": self._regulation_density(),
                "mutation_stability": self._mutation_stability(),
                "energy_efficiency": self._energy_efficiency(),
                "functional_elegance": self._functional_elegance(),
                "reflective_narrative_diversity": self._reflective_narrative_diversity(),
                "conceptual_hierarchy_depth": self._conceptual_hierarchy_depth(),
            },
        }
        # Aggregate coherence score (mean of all 12 metrics, clamped)
        values = [v for v in report["metrics"].values() if v is not None]
        if values:
            report["aggregate_coherence"] = round(
                sum(values) / len(values), 4
            )
        else:
            report["aggregate_coherence"] = None
        self._persist(report)
        return report

    def get_reports(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._report_path.exists():
            return []
        lines = self._report_path.read_text(encoding="utf-8").strip().split("\n")
        reports = []
        for line in lines[-limit:]:
            try:
                reports.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return reports

    def latest_report(self) -> Optional[Dict[str, Any]]:
        reports = self.get_reports(limit=1)
        return reports[0] if reports else None

    # ------------------------------------------------------------------ #
    # Metrics
    # ------------------------------------------------------------------ #

    def _modular_coherence(self) -> float:
        """Ratio of tested modules vs total modules (higher = better)."""
        core_modules = self._count_modules("speace_core")
        test_modules = self._count_modules("tests")
        if core_modules == 0:
            return 0.0
        return round(min(1.0, test_modules / max(core_modules, 1)), 4)

    def _redundancy_efficiency(self) -> float:
        """Estimate duplicate file names (lower duplicates = higher score)."""
        names: Dict[str, int] = {}
        for root, _dirs, files in os.walk(self._project_root / "speace_core"):
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    names[f] = names.get(f, 0) + 1
        if not names:
            return 1.0
        duplicates = sum(1 for c in names.values() if c > 1)
        return round(max(0.0, 1.0 - (duplicates / len(names))), 4)

    def _causal_clarity(self) -> float:
        """Ratio of causal hypotheses to total actions in audit logs."""
        causal_count = self._count_jsonl_lines("data/embodiment/causal_learning/causal_reports.jsonl")
        action_count = self._count_jsonl_lines("data/embodiment/embodied_action_actuator/embodied_action_audit.jsonl")
        action_count += self._count_jsonl_lines("data/embodiment/micro_actuator/micro_actuator_audit.jsonl")
        if action_count == 0:
            return 0.0
        return round(min(1.0, causal_count / max(action_count, 1)), 4)

    def _symmetry_asymmetry_balance(self) -> float:
        """Balance between successes and failures in audit logs."""
        successes = self._count_jsonl_field("data/embodiment/embodied_action_actuator/embodied_action_audit.jsonl", "outcome", "success")
        failures = self._count_jsonl_field("data/embodiment/embodied_action_actuator/embodied_action_audit.jsonl", "outcome", "failure")
        total = successes + failures
        if total == 0:
            return 0.5
        # Perfect balance when successes == failures (ideal = 0.5 each)
        # Score peaks when ratio is close to 1.0 (symmetry)
        ratio = successes / total
        return round(1.0 - abs(ratio - 0.5) * 2, 4)

    def _narrative_coherence(self) -> float:
        """Low variance in narrative event types = coherent narrative."""
        types = self._collect_jsonl_field_values("data/experience/narrative_timeline.jsonl", "event_type")
        if not types:
            return 0.5
        counts: Dict[str, int] = {}
        for t in types:
            counts[t] = counts.get(t, 0) + 1
        total = len(types)
        # Shannon entropy normalised
        entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
        max_entropy = math.log2(len(counts)) if counts else 1.0
        if max_entropy == 0:
            return 1.0
        # High coherence = low entropy (focused narrative)
        return round(1.0 - (entropy / max_entropy), 4)

    def _cognitive_entropy(self) -> float:
        """Variance of recent coherence scores — high variance = high entropy."""
        reports = self.get_reports(limit=10)
        if len(reports) < 2:
            return 0.5
        scores = [r.get("aggregate_coherence", 0.5) for r in reports if r.get("aggregate_coherence") is not None]
        if len(scores) < 2:
            return 0.5
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        # Normalise roughly: variance > 0.1 → high entropy
        return round(min(1.0, variance * 10), 4)

    def _regulation_density(self) -> float:
        """Presence of governance/regulation files relative to codebase size."""
        reg_count = self._count_files_containing("speace_core", "regulation", ".py")
        gov_count = self._count_files_containing("speace_core", "governance", ".py")
        total = self._count_py_files("speace_core")
        if total == 0:
            return 0.0
        return round(min(1.0, (reg_count + gov_count) / max(total * 0.05, 1)), 4)

    def _mutation_stability(self) -> float:
        """Check for uncommitted changes as a proxy of instability."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self._project_root,
                capture_output=True,
                text=True,
            )
            changed = len([l for l in result.stdout.splitlines() if l.strip()])
            # More changes = lower stability
            return round(max(0.0, 1.0 - (changed / 50)), 4)
        except Exception:
            return 0.5

    def _energy_efficiency(self) -> float:
        """Proxy: CPU usage low = high efficiency."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            # cpu 0% → 1.0, cpu 100% → 0.0
            return round(max(0.0, 1.0 - (cpu / 100.0)), 4)
        except Exception:
            return None

    def _functional_elegance(self) -> float:
        """Ratio of tests to code, absence of syntax errors."""
        code = self._count_py_files("speace_core")
        tests = self._count_py_files("tests")
        if code == 0:
            return 0.0
        ratio = tests / code
        # Ideal ratio around 1.0 or higher
        return round(min(1.0, ratio), 4)

    def _reflective_narrative_diversity(self) -> float:
        """Token-type ratio in recent inner-narrative fragments (high = richer reflection)."""
        path = self._project_root / "data" / "experience" / "inner_narrative" / "inner_narrative.jsonl"
        if not path.exists():
            return 0.5
        try:
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            if not lines:
                return 0.5
            tokens: set[str] = set()
            total_tokens = 0
            for line in lines[-50:]:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    content = obj.get("content", "")
                    for token in content.lower().split():
                        token = token.strip(".,;:!?")
                        if len(token) > 2:
                            tokens.add(token)
                            total_tokens += 1
                except json.JSONDecodeError:
                    continue
            if total_tokens == 0:
                return 0.5
            return round(len(tokens) / total_tokens, 4)
        except Exception:
            return 0.5

    def _conceptual_hierarchy_depth(self) -> float:
        """Max level in active concept graph nodes normalized to 3."""
        path = self._project_root / "data" / "cognition" / "concept_graph" / "nodes.jsonl"
        if not path.exists():
            return 0.5
        try:
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            max_level = 0
            for line in lines:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("status") == "approved":
                        level = obj.get("level", 0)
                        if level > max_level:
                            max_level = level
                except json.JSONDecodeError:
                    continue
            return round(min(1.0, max_level / 3.0), 4)
        except Exception:
            return 0.5

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self, report: Dict[str, Any]) -> None:
        try:
            with self._report_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _count_modules(self, subpath: str) -> int:
        path = self._project_root / subpath
        if not path.exists():
            return 0
        count = 0
        for root, dirs, files in os.walk(path):
            if "__init__.py" in files:
                count += 1
        return count

    def _count_py_files(self, subpath: str) -> int:
        path = self._project_root / subpath
        if not path.exists():
            return 0
        count = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                if f.endswith(".py"):
                    count += 1
        return count

    def _count_files_containing(self, subpath: str, keyword: str, suffix: str) -> int:
        path = self._project_root / subpath
        if not path.exists():
            return 0
        count = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                if f.endswith(suffix) and keyword in f.lower():
                    count += 1
        return count

    def _count_jsonl_lines(self, relative_path: str) -> int:
        path = self._project_root / relative_path
        if not path.exists():
            return 0
        try:
            return sum(1 for _ in path.open("r", encoding="utf-8") if _.strip())
        except OSError:
            return 0

    def _count_jsonl_field(self, relative_path: str, field: str, value: str) -> int:
        path = self._project_root / relative_path
        if not path.exists():
            return 0
        count = 0
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if obj.get(field) == value:
                            count += 1
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return count

    def _collect_jsonl_field_values(self, relative_path: str, field: str) -> List[str]:
        path = self._project_root / relative_path
        if not path.exists():
            return []
        values: List[str] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        val = obj.get(field)
                        if isinstance(val, str):
                            values.append(val)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        return values
