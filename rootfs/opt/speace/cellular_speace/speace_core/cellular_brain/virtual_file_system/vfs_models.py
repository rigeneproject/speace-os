from __future__ import annotations

from enum import Flag, auto
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class VFSPermission(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    DELETE = auto()
    LIST = auto()
    MANAGE_PERMISSIONS = auto()


class AccessRule(BaseModel):
    rule_id: str
    path_prefix: str
    allowed_permissions: List[VFSPermission] = Field(default_factory=lambda: [VFSPermission.READ])
    allowed: bool = True
    requires_approval: bool = False
    approved: bool = False


class FileMetadata(BaseModel):
    size_bytes: int = 0
    is_file: bool = False
    is_dir: bool = False
    is_symlink: bool = False
    modified_at: str = ""
    created_at: str = ""
    permissions: str = ""


class AssimilatedPath(BaseModel):
    virtual_path: str
    real_path: str
    metadata: FileMetadata
    assimilated_at: str = ""


class FileAccessAudit(BaseModel):
    path: str
    operation: str
    success: bool
    reason: str = ""
    timestamp: str = ""


class VFSConfig(BaseModel):
    root_mount_point: str = "C:\\"
    speace_install_path: str = "C:\\cellular_speace"
    access_rules: List[AccessRule] = Field(default_factory=lambda: [
        AccessRule(
            rule_id="read_root",
            path_prefix="C:\\",
            allowed_permissions=[VFSPermission.READ, VFSPermission.LIST],
            allowed=True,
            requires_approval=False,
        ),
        AccessRule(
            rule_id="write_speace",
            path_prefix="C:\\cellular_speace",
            allowed_permissions=[VFSPermission.READ, VFSPermission.WRITE, VFSPermission.LIST],
            allowed=True,
            requires_approval=False,
        ),
        AccessRule(
            rule_id="write_system_restricted",
            path_prefix="C:\\Windows\\System32",
            allowed_permissions=[VFSPermission.READ],
            allowed=True,
            requires_approval=True,
        ),
        AccessRule(
            rule_id="write_protected",
            path_prefix="C:\\Program Files",
            allowed_permissions=[VFSPermission.READ],
            allowed=True,
            requires_approval=False,
        ),
        AccessRule(
            rule_id="write_users",
            path_prefix=f"C:\\Users",
            allowed_permissions=[VFSPermission.READ, VFSPermission.WRITE, VFSPermission.LIST],
            allowed=True,
            requires_approval=True,
        ),
    ])
    enable_vfs: bool = False
