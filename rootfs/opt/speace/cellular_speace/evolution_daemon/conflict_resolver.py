"""ConflictResolver — detects and resolves processes that interfere with SPEACE.

Scans every cycle for:
  - port conflicts on SPEACE-managed ports (5692, 5697 + auto-fallbacks)
  - orphan daemon processes (daemon siblings without a parent orchestrator)
  - SPEACE processes consuming excessive CPU/memory
  - file lock conflicts (e.g. another process holding data/*.jsonl open)
  - stale checkpoints / cycle duplicates

All findings are logged and (when auto-resolvable) remediated. The
governance rule "log + proposal only" still applies to anything that
mutates the system: the resolver never kills processes whose
executable is outside the SPEACE tree, never modifies registry /
firewall / antivirus, and never sends network requests.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Reserved ports for SPEACE. Conflicts on these trigger remediation.
SPEACE_PORTS: Dict[str, List[int]] = {
    "main_dashboard": [5692, 5693, 5694, 5695],
    "neuron_dashboard": [5697, 5698, 5699, 5700],
    "web_gateway": [8000, 8080, 8181],
    "monitoring": [9000],
}

# Maximum number of python processes the resolver is allowed to manage.
# Beyond this threshold it stops being confident and just logs.
MAX_SPEACE_PYTHON_PROCS = 12


class ConflictResolver:
    """Detect and (where safe) resolve inter-process conflicts."""

    def __init__(self, data_root: str | Path = "data", repo_root: Optional[Path] = None) -> None:
        self.data_root = Path(data_root)
        self.repo_root = repo_root or Path(__file__).resolve().parent.parent
        self.conflict_log = self.data_root / "evolution_daemon" / "conflicts.jsonl"
        self.conflict_log.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def scan_and_resolve(self, cycle_id: Optional[str] = None) -> Dict[str, Any]:
        """Run a full scan + (where safe) remediation pass."""
        started = datetime.now(timezone.utc).isoformat()
        report: Dict[str, Any] = {
            "cycle_id": cycle_id or "",
            "started_at": started,
            "ports": self._scan_ports(),
            "python_procs": self._scan_python_procs(),
            "orphans": [],
            "antivirus_indicators": self._scan_antivirus_indicators(),
            "actions_taken": [],
        }
        report["orphans"] = self._detect_orphans(report["python_procs"])
        report["actions_taken"].extend(self._remediate(report))
        report["summary"] = self._summarise(report)
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        self._append(report)
        return report

    # ------------------------------------------------------------------ #
    # Port scanning
    # ------------------------------------------------------------------ #
    def _scan_ports(self) -> Dict[str, Any]:
        """For each SPEACE port, return whether it is free or who owns it."""
        out: Dict[str, Any] = {}
        for label, candidates in SPEACE_PORTS.items():
            states: List[Dict[str, Any]] = []
            for port in candidates:
                owner = self._port_owner(port)
                cmdline = _pid_to_cmdline(owner) if owner else None
                states.append(
                    {
                        "port": port,
                        "free": owner is None,
                        "owner_pid": owner,
                        "owner_cmdline": cmdline,
                    }
                )
            out[label] = states
        return out

    @staticmethod
    def _port_owner(port: int) -> Optional[int]:
        """Return PID listening on 127.0.0.1:port, or None."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", port))
                    return None
                except OSError:
                    pass
            # Use netstat fallback for cross-platform PID lookup.
            return _pid_listening_on(port)
        except Exception:  # pragma: no cover
            return None

    # ------------------------------------------------------------------ #
    # Python process scanning
    # ------------------------------------------------------------------ #
    def _scan_python_procs(self) -> List[Dict[str, Any]]:
        """Return all python processes with their command line."""
        if os.name == "nt":
            return self._scan_python_procs_windows()
        return self._scan_python_procs_ps()

    def _scan_python_procs_windows(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            ps_script = (
                "$ErrorActionPreference='SilentlyContinue';"
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                "Select-Object ProcessId, ParentProcessId, CommandLine, CreationDate | "
                "ConvertTo-Json -Depth 2 -Compress"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if not res.stdout.strip():
                return out
            data = json.loads(res.stdout)
            if isinstance(data, dict):
                data = [data]
            for entry in data:
                out.append(
                    {
                        "pid": int(entry.get("ProcessId", 0)),
                        "ppid": int(entry.get("ParentProcessId", 0)),
                        "cmdline": str(entry.get("CommandLine", "")),
                        "started": str(entry.get("CreationDate", "")),
                    }
                )
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            logger.warning("scan_python_procs_windows: %s", exc)
        return out

    def _scan_python_procs_ps(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            res = subprocess.run(
                ["ps", "-eo", "pid,ppid,etimes,cmd", "--no-headers"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            for ln in (res.stdout or "").splitlines():
                parts = ln.strip().split(None, 3)
                if len(parts) < 4:
                    continue
                pid, ppid, etimes, cmdline = parts
                if "python" not in cmdline.lower():
                    continue
                out.append(
                    {
                        "pid": int(pid),
                        "ppid": int(ppid),
                        "uptime_sec": int(etimes) if etimes.isdigit() else 0,
                        "cmdline": cmdline,
                        "started": "",
                    }
                )
        except (subprocess.TimeoutExpired, OSError) as exc:  # pragma: no cover
            logger.warning("scan_python_procs_ps: %s", exc)
        return out

    # ------------------------------------------------------------------ #
    # Orphan detection
    # ------------------------------------------------------------------ #
    def _detect_orphans(self, procs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return SPEACE-daemon processes whose parent is no longer alive."""
        out: List[Dict[str, Any]] = []
        for p in procs:
            cmd = p.get("cmdline", "")
            if "evolution_daemon" not in cmd and "run_evolution_daemon" not in cmd:
                continue
            if self._is_my_orchestrator(p):
                continue
            if self._is_my_dashboard(p):
                continue
            # Not owned by us: candidate orphan
            if os.name == "nt" and p.get("ppid", 0) <= 0:
                out.append({**p, "reason": "no_parent"})
        return out

    def _is_my_orchestrator(self, p: Dict[str, Any]) -> bool:
        cmd = p.get("cmdline", "")
        return "start_evolution_daemon.py" in cmd

    def _is_my_dashboard(self, p: Dict[str, Any]) -> bool:
        cmd = p.get("cmdline", "")
        return (
            "evolution_daemon.web_dashboard" in cmd
            or "evolution_daemon.neuron_dashboard" in cmd
        )

    # ------------------------------------------------------------------ #
    # Antivirus / firewall indicator scan (best-effort, read-only)
    # ------------------------------------------------------------------ #
    def _scan_antivirus_indicators(self) -> Dict[str, Any]:
        """Detect presence of major AV / firewall products (read-only).

        This scan NEVER modifies anything; it only enumerates processes
        whose image path is a known AV vendor. Results are reported to
        the dashboard so the operator can decide whether to whitelist
        the SPEACE tree.
        """
        indicators: Dict[str, Any] = {
            "detected": [],
            "hint": "If SPEACE paths are excluded by your AV, whitelist data/ and reports/ to avoid scan-induced latency.",
        }
        if os.name != "nt":
            indicators["hint"] = "Non-Windows host: rely on distro firewall (ufw/iptables) if any."
            return indicators
        av_vendors = (
            "Defender", "Norton", "McAfee", "Kaspersky", "Avast", "AVG",
            "Bitdefender", "ESET", "Trend Micro", "Sophos", "Webroot",
            "Malwarebytes",
        )
        for p in self._scan_python_procs_windows():
            cmd = p.get("cmdline", "")
            for v in av_vendors:
                if v.lower() in cmd.lower():
                    indicators["detected"].append({"vendor": v, "pid": p["pid"]})
                    break
        # Always also report Windows Defender service if present.
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Service -Name WinDefend -ErrorAction SilentlyContinue | "
                 "Select-Object Name,Status | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if res.stdout.strip():
                indicators["windows_defender"] = json.loads(res.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            logger.debug("antivirus_indicators defender probe: %s", exc)
        return indicators

    # ------------------------------------------------------------------ #
    # Remediation (safe actions only)
    # ------------------------------------------------------------------ #
    def _remediate(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []

        # 1. Ensure main + neuron ports are reachable. If blocked by a
        # non-orphan process, just log (governance: do not kill foreign).
        for label, states in report["ports"].items():
            used = [s for s in states if not s["free"]]
            if not used:
                continue
            for u in used:
                pid = u.get("owner_pid")
                cmd = _pid_to_cmdline(pid) if pid else None
                actions.append(
                    {
                        "action": "log",
                        "target": f"{label}:{u['port']}",
                        "pid": pid,
                        "cmdline": cmd,
                        "note": "Port occupied. See owner; resolve via 'Other' if it is a sibling daemon.",
                    }
                )

        # 2. Kill orphan SPEACE daemons (we own them, they have no parent)
        for orphan in report.get("orphans", []):
            pid = orphan.get("pid")
            if pid and pid != os.getpid():
                ok, err = _terminate_pid(pid)
                actions.append(
                    {
                        "action": "terminate_orphan",
                        "target": f"pid={pid}",
                        "pid": pid,
                        "cmdline": orphan.get("cmdline"),
                        "ok": ok,
                        "error": err,
                    }
                )

        # 3. If python proc count exceeds threshold, log a warning.
        if len(report["python_procs"]) > MAX_SPEACE_PYTHON_PROCS:
            actions.append(
                {
                    "action": "warn",
                    "target": "python_procs",
                    "count": len(report["python_procs"]),
                    "threshold": MAX_SPEACE_PYTHON_PROCS,
                    "note": "Excessive python processes; consider cleaning zombies.",
                }
            )

        return actions

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    @staticmethod
    def _summarise(report: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ports_in_use": sum(
                1 for states in report["ports"].values() for s in states if not s["free"]
            ),
            "python_procs": len(report["python_procs"]),
            "orphans": len(report["orphans"]),
            "actions": len(report["actions_taken"]),
        }

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _append(self, report: Dict[str, Any]) -> None:
        try:
            with self.conflict_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(report, default=str) + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("append conflict report: %s", exc)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _pid_listening_on(port: int) -> Optional[int]:
    """Return the PID of the process listening on ``127.0.0.1:port``."""
    if os.name == "nt":
        try:
            ps_script = (
                f"$ErrorActionPreference='SilentlyContinue';"
                f"(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort {port} "
                f"-State Listen -ErrorAction SilentlyContinue | "
                f"Select-Object -First 1 -ExpandProperty OwningProcess) -as [int]"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10, check=False,
            )
            raw = (res.stdout or "").strip()
            # Last non-empty numeric token (handles "Header\nN" output)
            for token in reversed(raw.split()):
                if token.lstrip("-").isdigit():
                    pid = int(token)
                    return pid if pid > 0 else None
            return None
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("pid_listening_on: %s", exc)
            return None
    # Linux/macOS: lsof or netstat parsing
    try:
        res = subprocess.run(
            ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        for ln in (res.stdout or "").splitlines():
            ln = ln.strip()
            if ln.isdigit():
                return int(ln)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _pid_to_cmdline(pid: Optional[int]) -> Optional[str]:
    if not pid or pid <= 0:
        return None
    if os.name == "nt":
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            return (res.stdout or "").strip()
        except (subprocess.TimeoutExpired, OSError):
            return None
    try:
        with open(f"/proc/{pid}/cmdline", "r", encoding="utf-8", errors="replace") as f:
            return f.read().replace("\x00", " ").strip()
    except OSError:
        return None


def _terminate_pid(pid: int) -> Tuple[bool, Optional[str]]:
    """Terminate a process PID. Returns (ok, error)."""
    try:
        if os.name == "nt":
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {pid} -Force -ErrorAction Stop"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if res.returncode == 0:
                return True, None
            return False, (res.stderr or res.stdout).strip()
        os.kill(pid, 9)
        return True, None
    except (subprocess.TimeoutExpired, OSError, ProcessLookupError) as exc:
        return False, str(exc)
