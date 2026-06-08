from __future__ import annotations

import os
import pathlib
import shutil
import stat
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from speace_core.cellular_brain.virtual_file_system.vfs_models import (
    AccessRule,
    AssimilatedPath,
    FileAccessAudit,
    FileMetadata,
    VFSConfig,
    VFSPermission,
)


class VirtualFileSystemEngine:
    """VFS — mappa la root del computer senza duplicare file fisici.

    Ogni richiesta di lettura/scrittura viene reindirizzata al file reale
    nella root, applicando le regole di accesso definite dal DNA digitale.
    """

    def __init__(self, config: Optional[VFSConfig] = None) -> None:
        self._config = config or VFSConfig()
        self._index: Dict[str, AssimilatedPath] = {}
        self._audit_log: List[FileAccessAudit] = []
        self._root_path = pathlib.Path(self._config.root_mount_point)
        self._root_link = pathlib.Path(self._config.speace_install_path) / "root_link"

    @property
    def config(self) -> VFSConfig:
        return self._config

    def index_root(self) -> Dict[str, Any]:
        """Indicizza la root del computer (solo metadati, nessuna copia)."""
        indexed = 0
        errors = 0
        try:
            for entry in self._root_path.iterdir():
                try:
                    resolved = self._resolve_path(entry.name)
                    if resolved is None:
                        continue
                    meta = self._stat_path(resolved)
                    if meta is None:
                        continue
                    self._index[entry.name] = AssimilatedPath(
                        virtual_path=str(entry),
                        real_path=str(resolved),
                        metadata=meta,
                        assimilated_at=datetime.now(timezone.utc).isoformat(),
                    )
                    indexed += 1
                except (OSError, PermissionError):
                    errors += 1
        except PermissionError:
            pass
        return {
            "root": str(self._root_path),
            "indexed": indexed,
            "errors": errors,
            "total_indexed": len(self._index),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def read_file(self, virtual_path: str) -> Optional[bytes]:
        """Legge un file dalla root attraverso il VFS."""
        real_path = self._resolve_to_real(virtual_path)
        if real_path is None:
            return None
        rule = self._check_access(real_path, VFSPermission.READ)
        if rule is not None and not rule.allowed:
            self._audit(str(real_path), "read", False, f"blocked_by_dna_rule: {rule.rule_id}")
            return None
        try:
            with open(real_path, "rb") as f:
                data = f.read()
            self._audit(str(real_path), "read", True)
            return data
        except (OSError, PermissionError) as exc:
            self._audit(str(real_path), "read", False, str(exc))
            return None

    def write_file(self, virtual_path: str, data: bytes) -> bool:
        """Scrive un file nella root attraverso il VFS (subordinato a regole DNA)."""
        real_path = self._resolve_to_real(virtual_path)
        if real_path is None:
            return False
        rule = self._check_access(real_path, VFSPermission.WRITE)
        if rule is not None and not rule.allowed:
            self._audit(str(real_path), "write", False, f"blocked_by_dna_rule: {rule.rule_id}")
            return False
        try:
            with open(real_path, "wb") as f:
                f.write(data)
            self._audit(str(real_path), "write", True)
            return True
        except (OSError, PermissionError) as exc:
            self._audit(str(real_path), "write", False, str(exc))
            return False

    def list_directory(self, virtual_path: str) -> Optional[List[Dict[str, Any]]]:
        """Elenca il contenuto di una directory nella root."""
        real_path = self._resolve_to_real(virtual_path)
        if real_path is None:
            return None
        if not real_path.is_dir():
            return None
        rule = self._check_access(real_path, VFSPermission.READ)
        if rule is not None and not rule.allowed:
            self._audit(str(real_path), "list_dir", False, f"blocked_by_dna_rule: {rule.rule_id}")
            return None
        entries: List[Dict[str, Any]] = []
        try:
            for entry in real_path.iterdir():
                try:
                    st = entry.stat(follow_symlinks=False)
                    entries.append({
                        "name": entry.name,
                        "path": str(entry),
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
                        "path": str(entry),
                        "is_file": False,
                        "is_dir": False,
                        "size_bytes": 0,
                        "error": "access_denied",
                    })
            self._audit(str(real_path), "list_dir", True)
            return entries
        except PermissionError as exc:
            self._audit(str(real_path), "list_dir", False, str(exc))
            return None

    def get_metadata(self, virtual_path: str) -> Optional[FileMetadata]:
        """Recupera i metadati di un file/directory nella root."""
        real_path = self._resolve_to_real(virtual_path)
        if real_path is None:
            return None
        return self._stat_path(real_path)

    def search(self, pattern: str, root_virtual: str = "", max_results: int = 50) -> List[Dict[str, Any]]:
        """Cerca file nella root che corrispondono a un pattern (max max_results)."""
        real_root = self._resolve_to_real(root_virtual) if root_virtual else self._root_path
        if real_root is None:
            return []
        results: List[Dict[str, Any]] = []
        try:
            for entry in real_root.rglob(pattern):
                try:
                    st = entry.stat(follow_symlinks=False)
                    results.append({
                        "virtual_path": str(entry),
                        "real_path": str(entry),
                        "size_bytes": st.st_size,
                        "is_file": entry.is_file(follow_symlinks=False),
                        "is_dir": entry.is_dir(follow_symlinks=False),
                    })
                    if len(results) >= max_results:
                        break
                except (OSError, PermissionError):
                    pass
        except PermissionError:
            pass
        return results

    def get_index(self) -> Dict[str, AssimilatedPath]:
        return dict(self._index)

    def get_audit_log(self, limit: int = 100) -> List[FileAccessAudit]:
        return self._audit_log[-limit:]

    def _resolve_to_real(self, virtual_path: str) -> Optional[pathlib.Path]:
        """Risolve un path virtuale nel path reale sulla root."""
        p = pathlib.Path(virtual_path)
        if p.is_absolute():
            if str(p).startswith(str(self._root_link)):
                return p
            if str(p).startswith(str(self._root_path)):
                return p
            if p.drive:
                return p
            return None
        full = self._root_path / p
        if full.exists():
            return full
        link_path = self._root_link / p
        if link_path.exists():
            return link_path
        return None

    def _resolve_path(self, name: str) -> Optional[pathlib.Path]:
        """Risolve un nome entry della root."""
        candidate = self._root_path / name
        if candidate.exists() or candidate.is_symlink():
            return candidate
        link_candidate = self._root_link / name
        if link_candidate.exists():
            return link_candidate
        return None

    def _stat_path(self, path: pathlib.Path) -> Optional[FileMetadata]:
        try:
            st = path.stat(follow_symlinks=False)
            return FileMetadata(
                size_bytes=st.st_size,
                is_file=path.is_file(follow_symlinks=False),
                is_dir=path.is_dir(follow_symlinks=False),
                is_symlink=path.is_symlink(),
                modified_at=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                created_at=datetime.fromtimestamp(st.st_ctime, tz=timezone.utc).isoformat(),
                permissions=stat.filemode(st.st_mode),
            )
        except OSError:
            return None

    def _check_access(self, real_path: pathlib.Path, permission: VFSPermission) -> Optional[AccessRule]:
        """Verifica le regole DNA per l'accesso al path."""
        path_str = str(real_path)
        for rule in self._config.access_rules:
            if path_str.startswith(rule.path_prefix):
                if permission in rule.allowed_permissions:
                    return rule
                return AccessRule(
                    rule_id=rule.rule_id,
                    path_prefix=rule.path_prefix,
                    allowed_permissions=[],
                    allowed=False,
                    requires_approval=False,
                )
        return AccessRule(
            rule_id="default",
            path_prefix="",
            allowed_permissions=[VFSPermission.READ],
            allowed=True,
            requires_approval=False,
        )

    def _audit(self, path: str, operation: str, success: bool, reason: str = "") -> None:
        self._audit_log.append(FileAccessAudit(
            path=path,
            operation=operation,
            success=success,
            reason=reason or "",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ))
