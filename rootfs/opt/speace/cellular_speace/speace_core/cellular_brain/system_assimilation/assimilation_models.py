from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AssimilationPermission(str, Enum):
    MONITOR = "monitor"
    CONTROL = "control"
    MODIFY = "modify"
    TERMINATE = "terminate"
    INSTALL = "install"
    CONFIGURE = "configure"


class AssimilatedProcess(BaseModel):
    pid: int
    name: str = ""
    executable_path: str = ""
    command_line: str = ""
    memory_bytes: int = 0
    thread_count: int = 0
    priority: int = 0
    status: str = "unknown"


class AssimilatedService(BaseModel):
    name: str
    display_name: str = ""
    path_name: str = ""
    state: str = "unknown"
    status: str = "unknown"
    start_mode: str = "unknown"
    process_id: int = 0


class AssimilatedDevice(BaseModel):
    device_id: str
    name: str = ""
    manufacturer: str = ""
    status: str = "unknown"
    class_guid: str = ""


class SystemInfo(BaseModel):
    hostname: str = ""
    os_platform: str = ""
    os_release: str = ""
    os_version: str = ""
    architecture: str = ""
    processor: str = ""
    python_version: str = ""
    speace_root: str = "C:\\cellular_speace"
    is_admin: bool = False


class SystemAssimilationConfig(BaseModel):
    allow_process_monitoring: bool = True
    allow_service_monitoring: bool = True
    allow_device_monitoring: bool = True
    allow_wmi_queries: bool = True
    allow_process_control: bool = False
    allow_service_control: bool = False
    enable_assimilation: bool = False


class SystemAssimilationReport(BaseModel):
    system_info: SystemInfo = Field(default_factory=SystemInfo)
    process_count: int = 0
    service_count: int = 0
    device_count: int = 0
    assimilated_processes: List[AssimilatedProcess] = Field(default_factory=list)
    assimilated_services: List[AssimilatedService] = Field(default_factory=list)
    assimilated_devices: List[AssimilatedDevice] = Field(default_factory=list)
    storage_devices: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: str = ""
    status: str = "pending"
