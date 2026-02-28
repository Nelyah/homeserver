"""Disk health controller for reading SMART test results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DISK_HEALTH_REPORT = Path("/var/lib/disk-health/status.json")


@dataclass
class TestResult:
    """Result of a single SMART test type."""

    status: str  # healthy, failed, degraded, testing
    last_run: str


@dataclass
class DriveStatus:
    """Status of a single drive with per-test results."""

    device: str
    model: str
    serial: str
    quick: TestResult | None = None
    short: TestResult | None = None
    long: TestResult | None = None

    def has_failure(self) -> bool:
        """Check if any test has a failure status."""
        for test in (self.quick, self.short, self.long):
            if test and test.status in ("failed", "degraded"):
                return True
        return False


def _empty_drives() -> list[DriveStatus]:
    return []


@dataclass
class DiskHealthReport:
    """Report from disk health check."""

    last_update: str
    drives: list[DriveStatus] = field(default_factory=_empty_drives)
    available: bool = True

    @property
    def failed_drives(self) -> int:
        """Count drives with failed/degraded status in any test."""
        return sum(1 for d in self.drives if d.has_failure())


def _parse_test_result(data: dict | None) -> TestResult | None:
    """Parse a test result from JSON."""
    if not data:
        return None
    return TestResult(
        status=data.get("status", "unknown"),
        last_run=data.get("lastRun", ""),
    )


def load_disk_health_report(path: Path = DISK_HEALTH_REPORT) -> DiskHealthReport:
    """Load disk health report from JSON file."""
    if not path.exists():
        return DiskHealthReport(
            last_update="",
            available=False,
        )

    try:
        with path.open() as f:
            data = json.load(f)

        drives = [
            DriveStatus(
                device=d.get("device", ""),
                model=d.get("model", "unknown"),
                serial=d.get("serial", "unknown"),
                quick=_parse_test_result(d.get("quick")),
                short=_parse_test_result(d.get("short")),
                long=_parse_test_result(d.get("long")),
            )
            for d in data.get("drives", [])
        ]

        return DiskHealthReport(
            last_update=data.get("lastUpdate", ""),
            drives=drives,
            available=True,
        )
    except (json.JSONDecodeError, OSError):
        return DiskHealthReport(
            last_update="",
            available=False,
        )
