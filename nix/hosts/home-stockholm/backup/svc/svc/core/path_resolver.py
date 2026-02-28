"""Path resolution utilities for backup and restore operations."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..controllers import DockerController


@dataclass
class ResolvedPath:
    """A resolved backup/restore path."""

    source_type: str  # "volume" or "path"
    source_name: str  # Original volume name or path
    filesystem_path: str  # Resolved filesystem path
    exists: bool  # Whether the path exists


def normalize_path(p: str) -> str:
    """Normalize a path by removing trailing slashes (except for root)."""
    if p == "/":
        return p
    return p.rstrip("/")


class PathResolver:
    """Resolves volumes and paths to filesystem locations."""

    def __init__(self, config: Config, docker: DockerController):
        self.config = config
        self.docker = docker

    async def resolve_volume(self, volume: str) -> ResolvedPath:
        """Resolve a docker volume to its filesystem path."""
        mount = await self.docker.volume_mountpoint(volume)

        if mount is not None:
            mount_path = Path(mount)
            # Strip _data suffix if present (docker volume internal structure)
            fs_path = str(mount_path.parent) if mount_path.name == "_data" else str(mount_path)
        else:
            # Fallback to default docker volumes path
            fs_path = f"{self.config.paths.docker_volumes_root}/{volume}"

        fs_path = normalize_path(fs_path)
        exists = Path(fs_path).exists()

        return ResolvedPath(
            source_type="volume",
            source_name=volume,
            filesystem_path=fs_path,
            exists=exists,
        )

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

    async def resolve_all(
        self, volumes: Sequence[str], paths: Sequence[str]
    ) -> tuple[list[ResolvedPath], list[str]]:
        """
        Resolve all volumes and paths.

        Returns:
            Tuple of (resolved_paths, missing_paths)
            where missing_paths contains descriptions of paths that don't exist.

        """
        resolved: list[ResolvedPath] = []
        missing: list[str] = []

        for volume in volumes:
            rp = await self.resolve_volume(volume)
            resolved.append(rp)
            if not rp.exists:
                missing.append(f"volume:{volume} -> {rp.filesystem_path}")

        for path in paths:
            rp = self.resolve_path(path)
            resolved.append(rp)
            if not rp.exists:
                missing.append(f"path:{rp.filesystem_path}")

        return resolved, missing

    async def get_backup_paths(
        self, volumes: Sequence[str], paths: Sequence[str]
    ) -> tuple[list[str], list[str]]:
        """
        Get filesystem paths for backup.

        Returns:
            Tuple of (paths_to_backup, missing_descriptions)

        """
        resolved, missing = await self.resolve_all(volumes, paths)
        filesystem_paths = [r.filesystem_path for r in resolved]
        return filesystem_paths, missing
