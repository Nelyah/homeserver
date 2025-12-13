"""Configuration models for svc."""

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, Field, ValidationError

try:
    from pydantic import ConfigDict  # pydantic v2
except ImportError:  # pragma: no cover
    ConfigDict = None  # pydantic v1

from .exceptions import ConfigError


class PydanticBase(BaseModel):
    """Base model with compatibility for pydantic v1 and v2."""

    if ConfigDict is not None:
        model_config = ConfigDict(populate_by_name=True, extra="forbid")
    else:

        class Config:
            """Pydantic v1 configuration."""

            allow_population_by_field_name = True
            extra = "forbid"


class RetentionPolicy(PydanticBase):
    """Restic retention policy configuration."""

    last: int | None = None
    hourly: int | None = None
    daily: int | None = None
    weekly: int | None = None
    monthly: int | None = None
    yearly: int | None = None


class BackupConfig(PydanticBase):
    """Backup configuration for a service."""

    enable: bool = False
    needs_service_stopped: bool = Field(default=False, alias="needsServiceStopped")
    volumes: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    policy: RetentionPolicy | None = None


class RestoreConfig(PydanticBase):
    """Restore configuration for a service."""

    tag: str
    volumes: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    stop_compose: bool = Field(default=False, alias="stopCompose")
    compose_unit: str = Field(default="", alias="composeUnit")
    target: str = "/"


class ServiceConfig(PydanticBase):
    """Configuration for a single service."""

    name: str
    backup: BackupConfig
    restore: RestoreConfig


class PathsConfig(PydanticBase):
    """Path configuration for the application."""

    secrets_root: str = Field(default="/var/lib/secrets", alias="secretsRoot")
    deploy_root: str = Field(default="/var/lib/docker-services", alias="deployRoot")
    docker_volumes_root: str = Field(default="/data/docker-data/volumes", alias="dockerVolumesRoot")


class Config(PydanticBase):
    """Root configuration model."""

    paths: PathsConfig
    services: dict[str, ServiceConfig] = Field(default_factory=dict)


TModel = TypeVar("TModel", bound=BaseModel)


def validate_model(model_cls: type[TModel], data: object) -> TModel:
    """Validate data against a pydantic model (v1/v2 compatible)."""
    if hasattr(model_cls, "model_validate"):  # pydantic v2
        return model_cls.model_validate(data)  # type: ignore[attr-defined]
    return model_cls.parse_obj(data)  # type: ignore[reportDeprecated]  # pydantic v1


def load_config(config_path: str) -> Config:
    """Load and validate configuration from JSON file."""
    path = Path(config_path)
    if not path.exists():
        message = f"Config file not found: {config_path}"
        raise ConfigError(message)

    try:
        with path.open() as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        message = f"Invalid JSON in config file: {e}"
        raise ConfigError(message) from e

    try:
        return validate_model(Config, data)
    except ValidationError as e:
        message = f"Invalid config schema: {e}"
        raise ConfigError(message) from e


def load_restic_env(secrets_root: str, env: str) -> dict[str, str]:
    """Load restic environment variables from env file."""
    env_file = Path(secrets_root) / "restic" / f"{env}.env"
    if not env_file.exists():
        message = f"Restic env file not found: {env_file}"
        raise ConfigError(message)

    result: dict[str, str] = {}
    with env_file.open() as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()

    required = ["RESTIC_PASSWORD", "RESTIC_REPOSITORY"]
    for key in required:
        if key not in result:
            message = f"Missing {key} in {env_file}"
            raise ConfigError(message)

    return result
