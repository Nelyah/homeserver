"""Docker controller with async support."""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ContainerInfo:
    """Information about a Docker container."""

    name: str
    status: str
    project: str | None  # com.docker.compose.project label
    service: str | None  # com.docker.compose.service label

    @property
    def is_up(self) -> bool:
        """Check if container status indicates it's running."""
        return self.status.startswith("Up")

    @property
    def is_healthy(self) -> bool:
        """Check if container is not marked unhealthy."""
        return "unhealthy" not in self.status

    @property
    def is_orphan(self) -> bool:
        """Check if container is an orphan (no compose project, not running)."""
        return self.project is None and not self.is_up


@dataclass
class ImageInfo:
    """Information about a Docker image."""

    id: str
    repository: str
    tag: str
    size: str


class DockerController:
    """Controls docker operations needed for volume path resolution."""

    def __init__(self, docker_bin: str = "/run/current-system/sw/bin/docker"):
        self.docker = docker_bin
        if not Path(self.docker).exists():
            found = shutil.which("docker")
            if found:
                self.docker = found

    async def volume_mountpoint(self, volume: str) -> str | None:
        """Get the mountpoint path for a docker volume."""
        if not Path(self.docker).exists():
            return None

        proc = await asyncio.create_subprocess_exec(
            self.docker,
            "volume",
            "inspect",
            volume,
            "--format",
            "{{.Mountpoint}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            return None

        mount = stdout.decode().strip()
        return mount or None

    async def list_containers(self) -> list[ContainerInfo]:
        """List all containers with their status and compose labels."""
        if not Path(self.docker).exists():
            return []

        # Format: name|status|project|service
        fmt = '{{.Names}}|{{.Status}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}'
        proc = await asyncio.create_subprocess_exec(
            self.docker,
            "ps",
            "--all",
            "--format",
            fmt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            return []

        containers: list[ContainerInfo] = []
        for line in stdout.decode().strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                containers.append(
                    ContainerInfo(
                        name=parts[0],
                        status=parts[1],
                        project=parts[2] or None,
                        service=parts[3] or None,
                    )
                )
        return containers

    async def get_dangling_images(self) -> list[ImageInfo]:
        """List dangling images (tagged <none>:<none>)."""
        if not Path(self.docker).exists():
            return []

        # Format: id|repository|tag|size
        fmt = "{{.ID}}|{{.Repository}}|{{.Tag}}|{{.Size}}"
        proc = await asyncio.create_subprocess_exec(
            self.docker,
            "images",
            "--filter",
            "dangling=true",
            "--format",
            fmt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            return []

        images: list[ImageInfo] = []
        for line in stdout.decode().strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                images.append(
                    ImageInfo(
                        id=parts[0],
                        repository=parts[1],
                        tag=parts[2],
                        size=parts[3],
                    )
                )
        return images

    async def remove_images(self, image_ids: list[str]) -> tuple[list[str], list[str]]:
        """Remove images by ID. Returns (removed, failed) lists."""
        if not image_ids or not Path(self.docker).exists():
            return [], []

        removed: list[str] = []
        failed: list[str] = []

        for image_id in image_ids:
            proc = await asyncio.create_subprocess_exec(
                self.docker,
                "rmi",
                image_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode == 0:
                removed.append(image_id)
            else:
                failed.append(image_id)

        return removed, failed

    async def remove_containers(self, container_names: list[str]) -> tuple[list[str], list[str]]:
        """Remove containers by name. Returns (removed, failed) lists."""
        if not container_names or not Path(self.docker).exists():
            return [], []

        removed: list[str] = []
        failed: list[str] = []

        for name in container_names:
            proc = await asyncio.create_subprocess_exec(
                self.docker,
                "rm",
                name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            if proc.returncode == 0:
                removed.append(name)
            else:
                failed.append(name)

        return removed, failed
