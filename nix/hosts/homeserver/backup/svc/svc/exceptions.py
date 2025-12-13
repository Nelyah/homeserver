"""Custom exceptions for svc."""

# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_SERVICE_NOT_FOUND = 3
EXIT_RESTIC_ERROR = 4
EXIT_SYSTEMCTL_ERROR = 5
EXIT_PERMISSION_ERROR = 6


class SvcError(Exception):
    """Base exception for svc errors."""

    exit_code = EXIT_CONFIG_ERROR


class ConfigError(SvcError):
    """Configuration loading or validation error."""

    exit_code = EXIT_CONFIG_ERROR


class ServiceNotFoundError(SvcError):
    """Requested service not found or backup not enabled."""

    exit_code = EXIT_SERVICE_NOT_FOUND


class ResticError(SvcError):
    """Restic command execution failed."""

    exit_code = EXIT_RESTIC_ERROR


class SystemctlError(SvcError):
    """Systemctl operation failed."""

    exit_code = EXIT_SYSTEMCTL_ERROR


class PermissionError(SvcError):
    """Operation requires root privileges."""

    exit_code = EXIT_PERMISSION_ERROR


class DependencyError(SvcError):
    """Required external dependency is missing."""

    exit_code = EXIT_CONFIG_ERROR


class DockerError(SvcError):
    """Docker command execution failed."""

    exit_code = EXIT_CONFIG_ERROR
