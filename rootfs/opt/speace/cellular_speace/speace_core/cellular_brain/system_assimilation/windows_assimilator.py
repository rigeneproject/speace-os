from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.system_assimilation.assimilation_models import (
    AssimilationPermission,
    AssimilatedDevice,
    AssimilatedProcess,
    AssimilatedService,
    SystemAssimilationConfig,
    SystemAssimilationReport,
    SystemInfo,
)

try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    _HAS_PSUTIL = False


def _safe_subprocess(command: List[str], timeout: float = 10.0) -> Optional[str]:
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


def _parse_powershell_csv(output: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    lines = [l for l in output.splitlines() if l.strip()]
    if len(lines) < 2:
        return items
    headers = [h.strip().strip('"') for h in lines[0].split(",")]
    for line in lines[1:]:
        values = [v.strip().strip('"') for v in line.split(",")]
        if len(values) == len(headers):
            items.append(dict(zip(headers, values)))
    return items


class WindowsSystemAssimilator:
    """Assimila il sistema Windows: processi, servizi, dispositivi, hardware.

    Usa psutil se disponibile (raccomandato), altrimenti PowerShell cmdlets.
    Tutte le operazioni sono READ-ONLY salvo approvazione esplicita
    dalle regole del DNA digitale.
    """

    def __init__(self, config: Optional[SystemAssimilationConfig] = None) -> None:
        self._config = config or SystemAssimilationConfig()
        self._assimilated_processes: Dict[int, AssimilatedProcess] = {}
        self._assimilated_services: Dict[str, AssimilatedService] = {}
        self._assimilated_devices: Dict[str, AssimilatedDevice] = {}
        self._system_info: Optional[SystemInfo] = None
        self._has_psutil = _HAS_PSUTIL

    @property
    def config(self) -> SystemAssimilationConfig:
        return self._config

    def assimilate(self) -> SystemAssimilationReport:
        """Esegue assimilazione completa del sistema Windows."""
        sys_info = self._gather_system_info()
        processes = self._gather_processes()
        services = self._gather_services()
        devices = self._gather_devices()
        storage = self._gather_storage()

        self._system_info = sys_info
        self._assimilated_processes = {p.pid: p for p in processes}
        self._assimilated_services = {s.name: s for s in services}
        self._assimilated_devices = {d.device_id: d for d in devices}

        return SystemAssimilationReport(
            system_info=sys_info,
            process_count=len(processes),
            service_count=len(services),
            device_count=len(devices),
            assimilated_processes=list(processes)[:50],
            assimilated_services=list(services)[:50],
            assimilated_devices=list(devices)[:50],
            storage_devices=storage,
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="completed",
        )

    def get_process_by_pid(self, pid: int) -> Optional[AssimilatedProcess]:
        return self._assimilated_processes.get(pid)

    def get_service_by_name(self, name: str) -> Optional[AssimilatedService]:
        return self._assimilated_services.get(name)

    def get_device_by_id(self, device_id: str) -> Optional[AssimilatedDevice]:
        return self._assimilated_devices.get(device_id)

    def list_processes(self) -> List[AssimilatedProcess]:
        return list(self._assimilated_processes.values())

    def list_services(self) -> List[AssimilatedService]:
        return list(self._assimilated_services.values())

    def list_devices(self) -> List[AssimilatedDevice]:
        return list(self._assimilated_devices.values())

    def query_wmi(self, wmi_class: str, properties: str = "*") -> Optional[List[Dict[str, Any]]]:
        """Esegue query WMI generica tramite PowerShell Get-CimInstance."""
        if not self._config.allow_wmi_queries:
            return None
        ps_cmd = [
            "powershell", "-NoProfile", "-Command",
            f"Get-CimInstance -ClassName {wmi_class} | Select-Object {properties} | ConvertTo-Csv -NoTypeInformation"
        ]
        stdout = _safe_subprocess(ps_cmd, timeout=30.0)
        if stdout is None:
            return None
        return _parse_powershell_csv(stdout)

    def _gather_system_info(self) -> SystemInfo:
        uname = platform.uname()
        return SystemInfo(
            hostname=uname.node or platform.node(),
            os_platform=sys.platform,
            os_release=uname.release or platform.version(),
            os_version=uname.version or "",
            architecture=uname.machine or platform.machine(),
            processor=uname.processor or "",
            python_version=sys.version,
            speace_root="C:\\cellular_speace",
            is_admin=self._is_admin(),
        )

    def _gather_processes(self) -> List[AssimilatedProcess]:
        processes: List[AssimilatedProcess] = []

        if self._has_psutil:
            for p in psutil.process_iter(attrs=[
                "pid", "name", "exe", "cmdline", "memory_info",
                "num_threads", "nice", "status"
            ]):
                try:
                    info = p.info
                    mem = info.get("memory_info")
                    processes.append(AssimilatedProcess(
                        pid=info["pid"],
                        name=info.get("name") or "",
                        executable_path=info.get("exe") or "",
                        command_line=" ".join(info.get("cmdline") or []) if info.get("cmdline") else "",
                        memory_bytes=mem.rss if mem else 0,
                        thread_count=info.get("num_threads") or 0,
                        priority=info.get("nice") or 0,
                        status=info.get("status") or "running",
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return processes

        ps_cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-Process | Select-Object Id,ProcessName,Path,ThreadCount,PriorityClass,"
            "@{N='WorkingSetMB';E={[math]::Round($_.WorkingSet/1MB,2)}},"
            "StartTime | ConvertTo-Csv -NoTypeInformation"
        ]
        stdout = _safe_subprocess(ps_cmd, timeout=30.0)
        if stdout:
            rows = _parse_powershell_csv(stdout)
            for row in rows:
                try:
                    pid = int(row.get("Id", "0"))
                    if pid > 0 and pid != 4:
                        processes.append(AssimilatedProcess(
                            pid=pid,
                            name=row.get("ProcessName", "unknown"),
                            executable_path=row.get("Path", ""),
                            memory_bytes=int(float(row.get("WorkingSetMB", "0")) * 1024 * 1024),
                            thread_count=int(row.get("ThreadCount", "0")),
                            priority=0,
                            status=row.get("Status", "running") if row.get("Status") else "running",
                        ))
                except (ValueError, KeyError):
                    pass
        return processes

    def _gather_services(self) -> List[AssimilatedService]:
        services: List[AssimilatedService] = []

        if self._has_psutil:
            for s in psutil.win_service_iter():
                try:
                    s_info = s.as_dict()
                    services.append(AssimilatedService(
                        name=s_info.get("name", ""),
                        display_name=s_info.get("display_name", ""),
                        path_name=s_info.get("binpath", ""),
                        state=s_info.get("status", "unknown"),
                        status=s_info.get("status", "unknown"),
                        start_mode=s_info.get("start_type", "unknown"),
                        process_id=0,
                    ))
                except Exception:
                    pass
            return services

        ps_cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-Service | Select-Object Name,DisplayName,Status,StartType,ServiceType | ConvertTo-Csv -NoTypeInformation"
        ]
        stdout = _safe_subprocess(ps_cmd, timeout=30.0)
        if stdout:
            rows = _parse_powershell_csv(stdout)
            for row in rows:
                services.append(AssimilatedService(
                    name=row.get("Name", "unknown"),
                    display_name=row.get("DisplayName", ""),
                    path_name="",
                    state=row.get("Status", "unknown"),
                    status=row.get("Status", "unknown"),
                    start_mode=row.get("StartType", "unknown"),
                    process_id=0,
                ))
        return services

    def _gather_devices(self) -> List[AssimilatedDevice]:
        devices: List[AssimilatedDevice] = []

        # Always query via PowerShell Get-PnpDevice (psutil has no device API)
        ps_cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-PnpDevice | Select-Object InstanceId,FriendlyName,Status,Class,Manufacturer | ConvertTo-Csv -NoTypeInformation"
        ]
        stdout = _safe_subprocess(ps_cmd, timeout=30.0)
        if stdout:
            rows = _parse_powershell_csv(stdout)
            for row in rows:
                try:
                    devices.append(AssimilatedDevice(
                        device_id=row.get("InstanceId", "unknown"),
                        name=row.get("FriendlyName", "unknown"),
                        manufacturer=row.get("Manufacturer", ""),
                        status=row.get("Status", "unknown"),
                        class_guid=row.get("Class", ""),
                    ))
                except Exception:
                    pass
        return devices

    def _gather_storage(self) -> List[Dict[str, Any]]:
        storage: List[Dict[str, Any]] = []

        if self._has_psutil:
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    storage.append({
                        "device_id": part.device,
                        "drive_type": "3" if "fixed" in part.opts.lower() else "2",
                        "size_bytes": usage.total,
                        "free_bytes": usage.free,
                        "volume_name": part.mountpoint,
                        "filesystem": part.fstype,
                    })
                except Exception:
                    pass
            return storage

        ps_cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance -ClassName Win32_LogicalDisk | Select-Object DeviceID,DriveType,Size,FreeSpace,VolumeName,FileSystem | ConvertTo-Csv -NoTypeInformation"
        ]
        stdout = _safe_subprocess(ps_cmd, timeout=30.0)
        if stdout:
            rows = _parse_powershell_csv(stdout)
            for row in rows:
                storage.append({
                    "device_id": row.get("DeviceID", ""),
                    "drive_type": row.get("DriveType", ""),
                    "size_bytes": self._safe_int(row.get("Size", "0")),
                    "free_bytes": self._safe_int(row.get("FreeSpace", "0")),
                    "volume_name": row.get("VolumeName", ""),
                    "filesystem": row.get("FileSystem", ""),
                })
        return storage

    def _is_admin(self) -> bool:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    @staticmethod
    def _safe_int(value: str, default: int = 0) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
