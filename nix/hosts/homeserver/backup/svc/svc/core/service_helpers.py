"""Service validation and helper utilities."""

import os

from ..config import Config, ServiceConfig
from ..exceptions import PermissionError, ServiceNotFoundError


def validate_service(config: Config, service_name: str) -> ServiceConfig:
    """
    Validate service exists and has backup enabled.

    Args:
        config: Application configuration
        service_name: Name of the service to validate

    Returns:
        ServiceConfig if valid

    Raises:
        ServiceNotFoundError: If service not found or backup not enabled

    """
    if service_name not in config.services:
        available = ", ".join(sorted(config.services.keys()))
        raise ServiceNotFoundError(f"Service '{service_name}' not found. Available: {available}")

    svc = config.services[service_name]
    if not svc.backup.enable:
        raise ServiceNotFoundError(f"Service '{service_name}' does not have backup enabled")
    return svc


def get_service(config: Config, service_name: str) -> ServiceConfig:
    """
    Get service configuration (without requiring backup enabled).

    Args:
        config: Application configuration
        service_name: Name of the service

    Returns:
        ServiceConfig

    Raises:
        ServiceNotFoundError: If service not found

    """
    if service_name not in config.services:
        available = ", ".join(sorted(config.services.keys()))
        raise ServiceNotFoundError(f"Service '{service_name}' not found. Available: {available}")
    return config.services[service_name]


def require_root(operation: str) -> None:
    """
    Raise PermissionError if not running as root.

    Args:
        operation: Description of the operation requiring root

    Raises:
        PermissionError: If not running as root

    """
    if os.geteuid() != 0:
        raise PermissionError(f"{operation} requires root privileges. Try: sudo svc ...")
