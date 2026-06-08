"""CyberPhysicalSensorArray — read-only embodiment sensors for SPEACE.

Gathers continuous data about the machine's physical state.
All operations are READ-ONLY and safe.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import psutil

    _HAS_PSUTIL = True
except Exception:  # pragma: no cover
    _HAS_PSUTIL = False


def _safe_subprocess(command: List[str], timeout: float = 5.0) -> Optional[str]:
    """Run a read-only subprocess command safely."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _parse_float(text: str) -> Optional[float]:
    """Safely parse a float from text."""
    try:
        return float(text.strip().replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _normalize(value: Optional[float], min_val: float, max_val: float) -> Optional[float]:
    """Normalize a value to [0, 1] range."""
    if value is None:
        return None
    if max_val == min_val:
        return 0.0
    normalized = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


class CyberPhysicalSensorArray:
    """Read-only sensor array that feels the physical machine SPEACE runs on."""

    def __init__(self, history_size: int = 1000) -> None:
        self._has_psutil = _HAS_PSUTIL
        self._history: deque[Dict[str, Any]] = deque(maxlen=history_size)
        self._lock = threading.Lock()
        self._sampling_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._interval_ms: int = 1000

    # ------------------------------------------------------------------ #
    # Sensor primitives
    # ------------------------------------------------------------------ #

    def get_cpu_state(self) -> Dict[str, Any]:
        """Return CPU usage, frequency, temperature (if available), and core count."""
        state: Dict[str, Any] = {
            "usage_percent": None,
            "frequency_mhz": None,
            "temperature_celsius": None,
            "core_count_logical": None,
            "core_count_physical": None,
        }

        if self._has_psutil:
            state["usage_percent"] = psutil.cpu_percent(interval=None)
            freq = psutil.cpu_freq()
            if freq:
                state["frequency_mhz"] = freq.current
            state["core_count_logical"] = psutil.cpu_count(logical=True)
            state["core_count_physical"] = psutil.cpu_count(logical=False)
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for key, entries in temps.items():
                        for entry in entries:
                            if entry.current is not None:
                                state["temperature_celsius"] = entry.current
                                break
                        if state["temperature_celsius"] is not None:
                            break
            except Exception:
                pass
        else:
            state["core_count_logical"] = os.cpu_count()
            # Attempt platform-specific read-only fallbacks
            if sys.platform.startswith("win"):
                stdout = _safe_subprocess(
                    ["wmic", "cpu", "get", "loadpercentage", "/value"]
                )
                if stdout:
                    for line in stdout.splitlines():
                        if "LoadPercentage" in line:
                            val = line.split("=")[-1].strip()
                            state["usage_percent"] = _parse_float(val)
                freq_stdout = _safe_subprocess(
                    ["wmic", "cpu", "get", "maxclockspeed", "/value"]
                )
                if freq_stdout:
                    for line in freq_stdout.splitlines():
                        if "MaxClockSpeed" in line:
                            val = line.split("=")[-1].strip()
                            state["frequency_mhz"] = _parse_float(val)
            elif sys.platform.startswith("linux"):
                # Parse /proc/stat for a rough CPU usage snapshot
                try:
                    with open("/proc/stat", "r") as f:
                        line = f.readline()
                    if line.startswith("cpu "):
                        parts = line.split()[1:]
                        total = sum(int(x) for x in parts if x.isdigit())
                        idle = int(parts[3])
                        busy = total - idle
                        # Percentage as busy/total; None if total is 0
                        if total > 0:
                            state["usage_percent"] = (busy / total) * 100.0
                except Exception:
                    pass

        state["usage_percent_normalized"] = _normalize(
            state["usage_percent"], 0.0, 100.0
        )
        state["frequency_mhz_normalized"] = _normalize(
            state["frequency_mhz"], 0.0, 5000.0
        )
        state["temperature_celsius_normalized"] = _normalize(
            state["temperature_celsius"], 20.0, 100.0
        )
        return state

    def get_memory_state(self) -> Dict[str, Any]:
        """Return total, used, free, and percent memory."""
        state: Dict[str, Any] = {
            "total_bytes": None,
            "used_bytes": None,
            "free_bytes": None,
            "percent": None,
        }

        if self._has_psutil:
            mem = psutil.virtual_memory()
            state["total_bytes"] = mem.total
            state["used_bytes"] = mem.used
            state["free_bytes"] = mem.free
            state["percent"] = mem.percent
        elif sys.platform.startswith("linux"):
            try:
                total = None
                free = None
                available = None
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            total = int(line.split()[1]) * 1024
                        elif line.startswith("MemFree:"):
                            free = int(line.split()[1]) * 1024
                        elif line.startswith("MemAvailable:"):
                            available = int(line.split()[1]) * 1024
                if total is not None:
                    state["total_bytes"] = total
                    if available is not None:
                        state["free_bytes"] = available
                        state["used_bytes"] = total - available
                        state["percent"] = (state["used_bytes"] / total) * 100.0
                    elif free is not None:
                        state["free_bytes"] = free
                        state["used_bytes"] = total - free
                        state["percent"] = (state["used_bytes"] / total) * 100.0
            except Exception:
                pass
        elif sys.platform.startswith("win"):
            # Use safe wmic fallback on Windows
            total_stdout = _safe_subprocess(
                ["wmic", "computersystem", "get", "totalphysicalmemory", "/value"]
            )
            if total_stdout:
                for line in total_stdout.splitlines():
                    if "TotalPhysicalMemory" in line:
                        val = line.split("=")[-1].strip()
                        total = _parse_float(val)
                        if total is not None:
                            state["total_bytes"] = int(total)
            free_stdout = _safe_subprocess(
                ["wmic", "os", "get", "freephysicalmemory", "/value"]
            )
            if free_stdout:
                for line in free_stdout.splitlines():
                    if "FreePhysicalMemory" in line:
                        val = line.split("=")[-1].strip()
                        free = _parse_float(val)
                        if free is not None and state["total_bytes"] is not None:
                            state["free_bytes"] = int(free) * 1024
                            state["used_bytes"] = state["total_bytes"] - state["free_bytes"]
                            state["percent"] = (
                                state["used_bytes"] / state["total_bytes"]
                            ) * 100.0

        state["percent_normalized"] = _normalize(state["percent"], 0.0, 100.0)
        return state

    def get_disk_state(self) -> Dict[str, Any]:
        """Return disk usage per drive and read/write bytes if available."""
        drives: List[Dict[str, Any]] = []
        read_bytes: Optional[int] = None
        write_bytes: Optional[int] = None

        if self._has_psutil:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append(
                        {
                            "device": part.device,
                            "mountpoint": part.mountpoint,
                            "total_bytes": usage.total,
                            "used_bytes": usage.used,
                            "free_bytes": usage.free,
                            "percent": usage.percent,
                            "percent_normalized": _normalize(
                                usage.percent, 0.0, 100.0
                            ),
                        }
                    )
                except Exception:
                    pass
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    read_bytes = disk_io.read_bytes
                    write_bytes = disk_io.write_bytes
            except Exception:
                pass
        else:
            # Fallback: inspect the current working directory drive
            cwd = os.getcwd()
            try:
                total, used, free = shutil.disk_usage(cwd)
                drives.append(
                    {
                        "device": cwd,
                        "mountpoint": cwd,
                        "total_bytes": total,
                        "used_bytes": used,
                        "free_bytes": free,
                        "percent": (used / total) * 100.0 if total else 0.0,
                        "percent_normalized": _normalize(
                            (used / total) * 100.0 if total else 0.0, 0.0, 100.0
                        ),
                    }
                )
            except Exception:
                pass

        return {
            "drives": drives,
            "read_bytes": read_bytes,
            "write_bytes": write_bytes,
        }

    def get_network_state(self) -> Dict[str, Any]:
        """Return bytes sent/received and connection count."""
        state: Dict[str, Any] = {
            "bytes_sent": None,
            "bytes_received": None,
            "connections": None,
            "packets_sent": None,
            "packets_received": None,
        }

        if self._has_psutil:
            try:
                net_io = psutil.net_io_counters()
                state["bytes_sent"] = net_io.bytes_sent
                state["bytes_received"] = net_io.bytes_recv
                state["packets_sent"] = net_io.packets_sent
                state["packets_received"] = net_io.packets_recv
            except Exception:
                pass
            try:
                conns = psutil.net_connections(kind="inet")
                state["connections"] = len(conns)
            except (psutil.AccessDenied, Exception):
                pass

        return state

    def get_process_state(self) -> Dict[str, Any]:
        """Return top processes by CPU/memory and running process count."""
        state: Dict[str, Any] = {
            "process_count": None,
            "top_by_cpu": [],
            "top_by_memory": [],
        }

        if self._has_psutil:
            procs: List[Dict[str, Any]] = []
            for p in psutil.process_iter(attrs=["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    info = p.info
                    procs.append(
                        {
                            "pid": info["pid"],
                            "name": info["name"],
                            "cpu_percent": info["cpu_percent"] or 0.0,
                            "memory_percent": info["memory_percent"] or 0.0,
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            state["process_count"] = len(procs)
            state["top_by_cpu"] = sorted(
                procs, key=lambda x: x["cpu_percent"], reverse=True
            )[:5]
            state["top_by_memory"] = sorted(
                procs, key=lambda x: x["memory_percent"], reverse=True
            )[:5]
        elif sys.platform.startswith("linux"):
            try:
                pids = [
                    int(x) for x in os.listdir("/proc") if x.isdigit()
                ]
                state["process_count"] = len(pids)
            except Exception:
                pass
        elif sys.platform.startswith("win"):
            stdout = _safe_subprocess(["wmic", "process", "list", "brief"])
            if stdout:
                lines = [l for l in stdout.splitlines() if l.strip()]
                # Header line + data lines
                if len(lines) > 1:
                    state["process_count"] = len(lines) - 1

        return state

    def get_power_state(self) -> Dict[str, Any]:
        """Return battery percent and plugged-in status (if laptop)."""
        state: Dict[str, Any] = {
            "battery_percent": None,
            "power_plugged": None,
            "seconds_left": None,
        }

        if self._has_psutil:
            try:
                battery = psutil.sensors_battery()
                if battery:
                    state["battery_percent"] = battery.percent
                    state["power_plugged"] = battery.power_plugged
                    state["seconds_left"] = battery.secsleft
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                capacity_path = "/sys/class/power_supply/BAT0/capacity"
                if os.path.exists(capacity_path):
                    with open(capacity_path, "r") as f:
                        val = f.read().strip()
                        state["battery_percent"] = _parse_float(val)
                status_path = "/sys/class/power_supply/BAT0/status"
                if os.path.exists(status_path):
                    with open(status_path, "r") as f:
                        status = f.read().strip().lower()
                        state["power_plugged"] = status in ("charging", "full")
            except Exception:
                pass
        elif sys.platform.startswith("win"):
            # Attempt WMI read-only query for battery
            stdout = _safe_subprocess(
                ["wmic", "path", "win32_battery", "get", "estimatedchargeremaining", "/value"]
            )
            if stdout:
                for line in stdout.splitlines():
                    if "EstimatedChargeRemaining" in line:
                        val = line.split("=")[-1].strip()
                        state["battery_percent"] = _parse_float(val)

        state["battery_percent_normalized"] = _normalize(
            state["battery_percent"], 0.0, 100.0
        )
        return state

    def get_temperature_state(self) -> Dict[str, Any]:
        """Return CPU/GPU temperatures if available."""
        state: Dict[str, Any] = {"cpu_celsius": None, "gpu_celsius": None}

        if self._has_psutil:
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for key, entries in temps.items():
                        for entry in entries:
                            if entry.current is not None and state["cpu_celsius"] is None:
                                if "cpu" in key.lower() or "core" in key.lower():
                                    state["cpu_celsius"] = entry.current
                            if entry.current is not None and state["gpu_celsius"] is None:
                                if "gpu" in key.lower() or "nvidia" in key.lower():
                                    state["gpu_celsius"] = entry.current
            except Exception:
                pass

        state["cpu_celsius_normalized"] = _normalize(state["cpu_celsius"], 20.0, 100.0)
        state["gpu_celsius_normalized"] = _normalize(state["gpu_celsius"], 20.0, 100.0)
        return state

    def get_filesystem_events(self, path: str = ".", duration: int = 5) -> Dict[str, Any]:
        """Return recently modified files under *path* within the last *duration* seconds."""
        now = time.time()
        cutoff = now - duration
        events: List[Dict[str, Any]] = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                        mtime = stat.st_mtime
                        if mtime >= cutoff:
                            events.append(
                                {
                                    "path": entry.path,
                                    "is_file": entry.is_file(follow_symlinks=False),
                                    "is_dir": entry.is_dir(follow_symlinks=False),
                                    "size_bytes": stat.st_size,
                                    "modified_at": datetime.fromtimestamp(
                                        mtime, tz=timezone.utc
                                    ).isoformat(),
                                }
                            )
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

        return {
            "monitored_path": os.path.abspath(path),
            "duration_seconds": duration,
            "events": events,
            "event_count": len(events),
        }

    def get_root_filesystem_overview(self) -> Dict[str, Any]:
        """Monitora la root del computer tramite il link simbolico root_link."""
        root_link = "C:\\cellular_speace\\root_link"
        entries: List[Dict[str, Any]] = []
        if not os.path.exists(root_link):
            return {"error": "root_link_not_found", "root_link": root_link}
        try:
            with os.scandir(root_link) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        entries.append({
                            "name": entry.name,
                            "is_file": entry.is_file(follow_symlinks=False),
                            "is_dir": entry.is_dir(follow_symlinks=False),
                            "size_bytes": st.st_size,
                            "modified_at": datetime.fromtimestamp(
                                st.st_mtime, tz=timezone.utc
                            ).isoformat(),
                        })
                    except (OSError, PermissionError):
                        entries.append({
                            "name": entry.name,
                            "is_file": False,
                            "is_dir": False,
                            "size_bytes": 0,
                            "error": "access_denied",
                        })
        except (OSError, PermissionError):
            pass
        return {
            "root_link": root_link,
            "resolved_root": os.path.realpath(root_link),
            "entry_count": len(entries),
            "entries": entries,
        }

    # ------------------------------------------------------------------ #
    # Composite API
    # ------------------------------------------------------------------ #

    def read_all(self) -> Dict[str, Any]:
        """Return a snapshot of all sensors with a UTC timestamp."""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu": self.get_cpu_state(),
            "memory": self.get_memory_state(),
            "disk": self.get_disk_state(),
            "network": self.get_network_state(),
            "process": self.get_process_state(),
            "power": self.get_power_state(),
            "temperature": self.get_temperature_state(),
            "filesystem": self.get_filesystem_events(),
            "root_filesystem": self.get_root_filesystem_overview(),
        }
        with self._lock:
            self._history.append(snapshot)
        return snapshot

    # ------------------------------------------------------------------ #
    # Background sampling
    # ------------------------------------------------------------------ #

    def start_continuous_sampling(self, interval_ms: int = 1000) -> None:
        """Start a background thread that samples sensors continuously."""
        if self._sampling_thread is not None and self._sampling_thread.is_alive():
            return
        self._interval_ms = max(100, interval_ms)
        self._stop_event.clear()
        self._sampling_thread = threading.Thread(
            target=self._sample_loop, daemon=True
        )
        self._sampling_thread.start()

    def stop_continuous_sampling(self) -> None:
        """Signal the background sampling thread to stop."""
        self._stop_event.set()
        if self._sampling_thread is not None:
            self._sampling_thread.join(timeout=2.0)
            self._sampling_thread = None

    def _sample_loop(self) -> None:
        while not self._stop_event.is_set():
            self.read_all()
            # Sleep in small chunks to remain responsive to stop events
            remaining = self._interval_ms / 1000.0
            while remaining > 0 and not self._stop_event.is_set():
                sleep_time = min(0.1, remaining)
                time.sleep(sleep_time)
                remaining -= sleep_time

    # ------------------------------------------------------------------ #
    # History & delta
    # ------------------------------------------------------------------ #

    def get_history(self, n_samples: int = 10) -> List[Dict[str, Any]]:
        """Return the last *n_samples* sensor snapshots."""
        with self._lock:
            return list(self._history)[-n_samples:]

    def get_sensor_delta(self) -> Dict[str, Any]:
        """Return the difference between the last two sensor readings."""
        with self._lock:
            if len(self._history) < 2:
                return {}
            current = self._history[-1]
            previous = self._history[-2]

        delta: Dict[str, Any] = {
            "timestamp": current.get("timestamp"),
            "previous_timestamp": previous.get("timestamp"),
        }

        for key in ("cpu", "memory", "disk", "network", "power", "temperature"):
            cur = current.get(key, {})
            prev = previous.get(key, {})
            delta[key] = {}
            for sub_key, cur_val in cur.items():
                if isinstance(cur_val, (int, float)) and sub_key in prev:
                    prev_val = prev[sub_key]
                    if isinstance(prev_val, (int, float)):
                        delta[key][sub_key] = cur_val - prev_val

        # Disk drive usage deltas
        cur_drives = current.get("disk", {}).get("drives", [])
        prev_drives = previous.get("disk", {}).get("drives", [])
        delta["disk"]["drive_deltas"] = []
        prev_by_mount = {d["mountpoint"]: d for d in prev_drives}
        for d in cur_drives:
            pm = d.get("mountpoint")
            if pm in prev_by_mount:
                pd = prev_by_mount[pm]
                delta["disk"]["drive_deltas"].append(
                    {
                        "mountpoint": pm,
                        "used_bytes_delta": d.get("used_bytes", 0)
                        - pd.get("used_bytes", 0),
                        "percent_delta": d.get("percent", 0.0)
                        - pd.get("percent", 0.0),
                    }
                )

        # Process count delta
        cur_count = current.get("process", {}).get("process_count")
        prev_count = previous.get("process", {}).get("process_count")
        if isinstance(cur_count, (int, float)) and isinstance(prev_count, (int, float)):
            delta["process"] = {"process_count_delta": cur_count - prev_count}

        # Filesystem event count delta
        cur_events = current.get("filesystem", {}).get("event_count", 0)
        prev_events = previous.get("filesystem", {}).get("event_count", 0)
        delta["filesystem"] = {"event_count_delta": cur_events - prev_events}

        return delta
