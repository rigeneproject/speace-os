import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class EnergyAccountingLedger:
    """T58 — Registra entrate/uscite energetiche simulate."""

    def __init__(self, report_dir: str = "reports/metabolism"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.entries: List[Dict[str, Any]] = []

    def record_consumption(self, module_name: str, amount: float, reason: str = "") -> None:
        self.entries.append(
            {
                "type": "consumption",
                "module": module_name,
                "amount": amount,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def record_saving(self, module_name: str, amount: float, reason: str = "") -> None:
        self.entries.append(
            {
                "type": "saving",
                "module": module_name,
                "amount": amount,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def record_reservation(self, resource_class: str, amount: float, reason: str = "") -> None:
        self.entries.append(
            {
                "type": "reservation",
                "resource_class": resource_class,
                "amount": amount,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def compute_net_energy_delta(self) -> float:
        consumed = sum(e["amount"] for e in self.entries if e["type"] == "consumption")
        saved = sum(e["amount"] for e in self.entries if e["type"] == "saving")
        return saved - consumed

    def export_json(self, path: Optional[Path] = None) -> Path:
        target = path or self.report_dir / f"energy_ledger_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        target.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")
        return target

    def export_markdown(self, path: Optional[Path] = None) -> Path:
        target = path or self.report_dir / f"energy_ledger_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        lines = ["# Energy Accounting Ledger", f"**Entries:** {len(self.entries)}", ""]
        for e in self.entries:
            lines.append(f"- {e['type']} | {e.get('module', e.get('resource_class', ''))} | {e['amount']:.4f} | {e.get('reason', '')}")
        target.write_text("\n".join(lines), encoding="utf-8")
        return target
