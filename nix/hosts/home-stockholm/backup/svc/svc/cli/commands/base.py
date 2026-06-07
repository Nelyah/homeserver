"""Base command protocol and application context."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from ...config import Config
from ...controllers import (
    KubernetesController,
    ResticRunner,
    SystemctlController,
)
from ...core import PathResolver
from ..renderer import Renderer

TArgs = TypeVar("TArgs")


@dataclass
class AppContext:
    """
    Application context passed to commands.

    Contains all dependencies needed by commands.
    """

    config: Config
    renderer: Renderer
    dry_run: bool
    verbose: bool

    # Lazily initialized controllers
    _systemctl: SystemctlController | None = None
    _kubernetes: KubernetesController | None = None
    _path_resolver: PathResolver | None = None

    @property
    def systemctl(self) -> SystemctlController:
        """Get or create a SystemctlController."""
        if self._systemctl is None:
            self._systemctl = SystemctlController(dry_run=self.dry_run)
        return self._systemctl

    @property
    def kubernetes(self) -> KubernetesController:
        """Get or create a KubernetesController."""
        if self._kubernetes is None:
            self._kubernetes = KubernetesController(dry_run=self.dry_run)
        return self._kubernetes

    @property
    def path_resolver(self) -> PathResolver:
        """Get or create a PathResolver."""
        if self._path_resolver is None:
            self._path_resolver = PathResolver(self.kubernetes)
        return self._path_resolver

    def create_restic_runner(self, env_vars: dict[str, str]) -> ResticRunner:
        """Create a ResticRunner with the given environment variables."""
        return ResticRunner(env_vars, dry_run=self.dry_run)


class Command(ABC, Generic[TArgs]):
    """Abstract base class for CLI commands."""

    @abstractmethod
    async def execute(self, args: TArgs, ctx: AppContext) -> int:
        """
        Execute the command.

        Args:
            args: Parsed command-line arguments
            ctx: Application context

        Returns:
            Exit code

        """
        ...
