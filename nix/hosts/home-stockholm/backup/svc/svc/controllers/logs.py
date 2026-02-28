"""Journald log scanning controller for svc doctor."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("svc.controllers.logs")


# Default patterns for log scanning (always enabled for all services)
DEFAULT_ERROR_PATTERNS: list[str] = [
    "ERROR",
    "FATAL",
    "CRITICAL",
    "Exception",
    "Traceback",
    "OCI runtime",
]
DEFAULT_WARNING_PATTERNS: list[str] = ["WARN", "WARNING"]
# Conservative default ignore patterns - only clear false positives
DEFAULT_IGNORE_PATTERNS: list[str] = [
    "context canceled",      # Normal during graceful shutdown
    "received signal",       # Normal shutdown signal handling
    "Exiting gracefully",    # Normal shutdown
]

# JSON severity values that map to ERROR
JSON_ERROR_LEVELS: set[str] = {"error", "err", "fatal", "critical", "crit", "panic", "alert", "emerg"}
# JSON severity values that map to WARNING
JSON_WARNING_LEVELS: set[str] = {"warn", "warning"}


class LogSeverity(StrEnum):
    """Severity level of a log scan result."""

    ERROR = "error"
    WARNING = "warning"
    OK = "ok"


@dataclass
class LogEntry:
    """A single log line that matched a pattern."""

    timestamp: str
    message: str
    severity: LogSeverity
    count: int = 1  # How many times this message appeared (after deduplication)


def _empty_log_entries() -> list[LogEntry]:
    return []


@dataclass(frozen=True)
class JournalEntry:
    """A parsed journald entry with a normalized timestamp."""

    timestamp: str
    message: str


@dataclass
class LogScanResult:
    """Result of scanning a service's logs."""

    service: str
    severity: LogSeverity  # Overall: error > warning > ok
    error_count: int        # Total occurrences
    warning_count: int      # Total occurrences
    unique_errors: int = 0  # Unique error messages after deduplication
    unique_warnings: int = 0  # Unique warning messages after deduplication
    entries: list[LogEntry] = field(default_factory=_empty_log_entries)

    @property
    def is_ok(self) -> bool:
        """Check if there are no errors or warnings."""
        return self.severity == LogSeverity.OK

    @property
    def has_errors(self) -> bool:
        """Check if there are errors."""
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings (but no errors)."""
        return self.warning_count > 0 and self.error_count == 0


@dataclass(frozen=True)
class LogScanPatterns:
    """Optional log scanning patterns for a service."""

    error: list[str] | None = None
    warning: list[str] | None = None
    ignore: list[str] | None = None


@dataclass(frozen=True)
class LogScanOptions:
    """Options for a log scan request."""

    patterns: LogScanPatterns | None = None
    since: str = "24h ago"
    max_entries: int = 10
    container_names: list[str] | None = None


class _JournalEntryModel(BaseModel):
    level: str | None = None
    severity: str | None = None
    lvl: str | None = None
    log_level: str | None = None
    loglevel: str | None = None
    msg: str | None = None
    message: str | None = None
    text: str | None = None

    class Config:
        extra = "allow"


class LogsController:
    """Scans journald logs for error patterns."""

    def __init__(self, journalctl_bin: str = "/run/current-system/sw/bin/journalctl"):
        self.journalctl = journalctl_bin
        if not Path(self.journalctl).exists():
            # Fallback for non-NixOS systems
            self.journalctl = "/usr/bin/journalctl"

    async def scan_service_logs(
        self, service: str, *, options: LogScanOptions | None = None
    ) -> LogScanResult:
        """
        Scan journald logs for a docker-compose service.

        Args:
            service: Service name (used to construct unit name)
            options: Scan options (patterns, time window, container names)

        Returns:
            LogScanResult with counts and sample log entries

        """
        scan_options = options or LogScanOptions()
        error_re, warning_re, ignore_re = _compile_scan_patterns(scan_options.patterns)

        entries = await self._fetch_entries(service, scan_options)
        error_entries, warning_entries = _scan_entries(
            entries,
            error_re=error_re,
            warning_re=warning_re,
            ignore_re=ignore_re,
        )

        severity = (
            LogSeverity.ERROR
            if error_entries
            else LogSeverity.WARNING
            if warning_entries
            else LogSeverity.OK
        )

        # Deduplicate entries separately by severity
        deduped_errors = _deduplicate_entries(error_entries)
        deduped_warnings = _deduplicate_entries(warning_entries)

        max_entries = scan_options.max_entries
        combined = deduped_errors[:max_entries] + deduped_warnings[: max_entries - len(deduped_errors)]

        return LogScanResult(
            service=service,
            severity=severity,
            error_count=len(error_entries),
            warning_count=len(warning_entries),
            unique_errors=len(deduped_errors),
            unique_warnings=len(deduped_warnings),
            entries=combined[:max_entries],
        )

    async def _fetch_entries(self, service: str, options: LogScanOptions) -> list[JournalEntry]:
        """Fetch journald entries for a service, preferring container logs."""
        unit = f"docker-compose-{service}.service"

        if options.container_names:
            entries = await self._fetch_container_logs(options.container_names, options.since)
            if entries:
                return entries

        return await self._fetch_unit_logs(unit, options.since)

    async def _fetch_unit_logs(self, unit: str, since: str) -> list[JournalEntry]:
        """Fetch log entries from journald for a systemd unit."""
        if not Path(self.journalctl).exists():
            logger.warning("journalctl not found at %s", self.journalctl)
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                self.journalctl,
                "-u",
                unit,
                "--since",
                since,
                "--no-pager",
                "-q",  # Quiet mode, no metadata lines
                "-o",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                # Unit might not exist or have no logs
                return []

            return _parse_journal_json_lines(stdout.decode(errors="replace"))

        except OSError as e:
            logger.warning("Failed to fetch logs for %s: %s", unit, e)
            return []

    async def _fetch_container_logs(
        self, container_names: list[str], since: str
    ) -> list[JournalEntry]:
        """Fetch log entries from journald for one or more containers."""
        if not Path(self.journalctl).exists():
            logger.warning("journalctl not found at %s", self.journalctl)
            return []

        match_args: list[str] = []
        for name in container_names:
            if not name:
                continue
            if match_args:
                match_args.append("+")
            match_args.append(f"CONTAINER_NAME={name}")

        if not match_args:
            return []

        try:
            proc = await asyncio.create_subprocess_exec(
                self.journalctl,
                *match_args,
                "--since",
                since,
                "--no-pager",
                "-q",
                "-o",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode != 0:
                return []

            return _parse_journal_json_lines(stdout.decode(errors="replace"))
        except OSError as e:
            logger.warning("Failed to fetch container logs: %s", e)
            return []


def _compile_patterns(patterns: list[str]) -> re.Pattern[str]:
    """Compile a list of patterns into a single regex with word boundaries."""
    if not patterns:
        return re.compile(r"(?!)")  # Never matches
    # Use word boundaries to avoid matching "error" in "errorReason"
    word_patterns = [rf"\b{re.escape(p)}\b" for p in patterns]
    return re.compile("|".join(word_patterns), re.IGNORECASE)


def _compile_scan_patterns(
    patterns: LogScanPatterns | None,
) -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str] | None]:
    errors = patterns.error if (patterns and patterns.error) else DEFAULT_ERROR_PATTERNS
    warnings = patterns.warning if (patterns and patterns.warning) else DEFAULT_WARNING_PATTERNS
    ignores = patterns.ignore if (patterns and patterns.ignore) else DEFAULT_IGNORE_PATTERNS

    error_re = _compile_patterns(errors)
    warning_re = _compile_patterns(warnings)
    ignore_re = _compile_patterns(ignores) if ignores else None
    return error_re, warning_re, ignore_re


# Regex for logfmt level detection (e.g., "level=error", "level=info")
_LOGFMT_LEVEL_RE = re.compile(r"\blevel=(\w+)", re.IGNORECASE)


def _detect_logfmt_severity(message: str) -> LogSeverity | None:
    """
    Detect severity from logfmt level=<value> format (common in Go apps like Grafana).

    Returns LogSeverity if a level field is found, None otherwise.
    """
    match = _LOGFMT_LEVEL_RE.search(message)
    if not match:
        return None

    level = match.group(1).lower()
    if level in JSON_ERROR_LEVELS:
        return LogSeverity.ERROR
    if level in JSON_WARNING_LEVELS:
        return LogSeverity.WARNING
    # Known level but not error/warning (info, debug, trace)
    return LogSeverity.OK


def _detect_json_severity(message: str) -> tuple[LogSeverity | None, str]:
    """
    Try to detect severity from a JSON-formatted log message.

    Returns (severity, display_message) tuple.
    If the message is not JSON or has no severity field, returns (None, original_message).
    """
    display_msg = message
    severity_value: str | None = None
    level = ""

    try:
        raw = json.loads(message)
    except json.JSONDecodeError:
        raw = None

    if isinstance(raw, dict):
        try:
            entry = _JournalEntryModel.model_validate(raw)
        except ValidationError:
            entry = None
        if entry:
            severity_value = (
                entry.level
                or entry.severity
                or entry.lvl
                or entry.log_level
                or entry.loglevel
            )
            if severity_value:
                level = severity_value.lower()
                display_msg = entry.msg or entry.message or entry.text or message

    if not severity_value:
        return None, message

    if level in JSON_ERROR_LEVELS:
        return LogSeverity.ERROR, display_msg
    if level in JSON_WARNING_LEVELS:
        return LogSeverity.WARNING, display_msg

    # Known level but not error/warning (info, debug, trace)
    return LogSeverity.OK, display_msg


def _normalize_message(msg: str) -> str:
    """Normalize message for deduplication - groups similar errors together."""
    # Remove memory addresses (0x7fb4ef1dda60)
    msg = re.sub(r"0x[0-9a-f]+", "0x...", msg, flags=re.IGNORECASE)
    # Remove UUIDs
    msg = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "<uuid>",
        msg,
        flags=re.IGNORECASE,
    )
    # Remove timestamps within message
    msg = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*Z?", "<timestamp>", msg)
    # Normalize service names in DNS lookups: "lookup grafana:" -> "lookup <service>:"
    msg = re.sub(r"lookup \w+:", "lookup <service>:", msg)
    # Normalize IP addresses
    msg = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?", "<ip>", msg)
    return msg


def _deduplicate_entries(entries: list[LogEntry]) -> list[LogEntry]:
    """Deduplicate log entries by normalized message, preserving first timestamp."""
    if not entries:
        return []

    # Group by normalized message and severity
    groups: dict[tuple[str, LogSeverity], LogEntry] = {}
    for entry in entries:
        key = (_normalize_message(entry.message), entry.severity)
        if key in groups:
            # Increment count, keep first timestamp and original message
            existing = groups[key]
            groups[key] = LogEntry(
                timestamp=existing.timestamp,
                message=existing.message,
                severity=existing.severity,
                count=existing.count + 1,
            )
        else:
            groups[key] = LogEntry(
                timestamp=entry.timestamp,
                message=entry.message,
                severity=entry.severity,
                count=1,
            )

    # Return deduplicated entries sorted by count (most frequent first)
    return sorted(groups.values(), key=lambda e: e.count, reverse=True)


def _classify_message(
    message: str,
    *,
    error_re: re.Pattern[str],
    warning_re: re.Pattern[str],
) -> tuple[LogSeverity | None, str]:
    # First try JSON structured logs
    json_severity, json_message = _detect_json_severity(message)
    if json_severity in (LogSeverity.ERROR, LogSeverity.WARNING):
        return json_severity, json_message
    if json_severity == LogSeverity.OK:
        return None, ""  # Skip OK level logs

    # Then try logfmt (level=info, level=error, etc.)
    logfmt_severity = _detect_logfmt_severity(message)
    if logfmt_severity is not None:
        if logfmt_severity in (LogSeverity.ERROR, LogSeverity.WARNING):
            return logfmt_severity, message
        return None, ""  # Skip OK level logs

    # Fall back to pattern matching (with word boundaries now)
    if error_re.search(message):
        return LogSeverity.ERROR, message
    if warning_re.search(message):
        return LogSeverity.WARNING, message
    return None, ""


def _scan_entries(
    entries: list[JournalEntry],
    *,
    error_re: re.Pattern[str],
    warning_re: re.Pattern[str],
    ignore_re: re.Pattern[str] | None,
) -> tuple[list[LogEntry], list[LogEntry]]:
    error_entries: list[LogEntry] = []
    warning_entries: list[LogEntry] = []

    for entry in entries:
        if ignore_re and ignore_re.search(entry.message):
            continue

        severity, message = _classify_message(
            entry.message, error_re=error_re, warning_re=warning_re
        )
        if severity == LogSeverity.ERROR:
            error_entries.append(
                LogEntry(timestamp=entry.timestamp, message=message, severity=LogSeverity.ERROR)
            )
        elif severity == LogSeverity.WARNING:
            warning_entries.append(
                LogEntry(timestamp=entry.timestamp, message=message, severity=LogSeverity.WARNING)
            )

    return error_entries, warning_entries


def _format_realtime_timestamp(usec: str | None) -> str:
    if not usec:
        return ""
    try:
        dt = datetime.fromtimestamp(int(usec) / 1_000_000).astimezone()
    except (ValueError, OSError):
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_journal_json_lines(text: str) -> list[JournalEntry]:
    entries: list[JournalEntry] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = str(obj.get("MESSAGE", "") or "")
        timestamp = _format_realtime_timestamp(obj.get("__REALTIME_TIMESTAMP"))
        if message:
            entries.append(JournalEntry(timestamp=timestamp, message=message))
    return entries
