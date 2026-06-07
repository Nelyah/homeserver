"""Path resolution utilities for backup and restore operations."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..config import KubernetesBackupConfig
from ..controllers import KubernetesController


@dataclass
class ResolvedPath:
    """A resolved backup/restore path."""

    source_type: str  # "path" or "kubernetes-pvc"
    source_name: str  # Original path or namespace/PVC
    filesystem_path: str  # Resolved filesystem path
    exists: bool  # Whether the path exists


def normalize_path(p: str) -> str:
    """Normalize a path by removing trailing slashes (except for root)."""
    if p == "/":
        return p
    return p.rstrip("/")


class PathResolver:
    """Resolves configured backup targets to filesystem locations."""

    def __init__(self, kubernetes: KubernetesController):
        self.kubernetes = kubernetes

    def resolve_path(self, path: str) -> ResolvedPath:
        """Resolve a direct path (mostly normalization and existence check)."""
        normalized = normalize_path(path)
        exists = Path(normalized).exists()

        return ResolvedPath(
            source_type="path",
            source_name=path,
            filesystem_path=normalized,
            exists=exists,
        )

    async def resolve_kubernetes_pvc(self, namespace: str, pvc: str) -> ResolvedPath:
        """Resolve a Kubernetes PVC to its backing filesystem path."""
        fs_path = normalize_path(await self.kubernetes.pvc_filesystem_path(namespace, pvc))
        exists = await asyncio.to_thread(Path(fs_path).exists)

        return ResolvedPath(
            source_type="kubernetes-pvc",
            source_name=f"{namespace}/{pvc}",
            filesystem_path=fs_path,
            exists=exists,
        )

    async def resolve_all(
        self,
        paths: Sequence[str],
        kubernetes: KubernetesBackupConfig | None = None,
    ) -> tuple[list[ResolvedPath], list[str]]:
        """
        Resolve all configured filesystem paths and Kubernetes PVCs.

        Returns:
            Tuple of (resolved_paths, missing_paths)
            where missing_paths contains descriptions of paths that don't exist.

        """
        resolved: list[ResolvedPath] = []
        missing: list[str] = []

        for path in paths:
            rp = self.resolve_path(path)
            resolved.append(rp)
            if not rp.exists:
                missing.append(f"path:{rp.filesystem_path}")

        if kubernetes is not None:
            for pvc in kubernetes.pvcs:
                rp = await self.resolve_kubernetes_pvc(kubernetes.namespace, pvc)
                resolved.append(rp)
                if not rp.exists:
                    missing.append(f"kubernetes-pvc:{rp.source_name} -> {rp.filesystem_path}")

        return resolved, missing

    async def get_backup_paths(
        self,
        paths: Sequence[str],
        kubernetes: KubernetesBackupConfig | None = None,
    ) -> tuple[list[str], list[str]]:
        """
        Get filesystem paths for backup.

        Returns:
            Tuple of (paths_to_backup, missing_descriptions)

        """
        resolved, missing = await self.resolve_all(paths, kubernetes)
        filesystem_paths = [r.filesystem_path for r in resolved]
        return filesystem_paths, missing
