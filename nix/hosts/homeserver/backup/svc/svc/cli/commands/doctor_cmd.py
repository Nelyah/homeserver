"""Doctor command for health checks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ...controllers import (
    DiskHealthReport,
    LogScanOptions,
    LogScanPatterns,
    LogScanResult,
    LogSeverity,
    TestResult,
    TimerStatus,
    load_disk_health_report,
)
from ...exceptions import EXIT_SUCCESS
from ..args import DoctorArgs
from .base import AppContext, Command

if TYPE_CHECKING:
    from ...config import ServiceConfig, TimerConfig


@dataclass
class DoctorResults:
    """Collected results from doctor checks."""

    timer_statuses: list[TimerStatus]
    log_results: list[LogScanResult]
    disk_health: DiskHealthReport

    @property
    def timer_failures(self) -> int:
        """Count timers that failed."""
        return sum(1 for t in self.timer_statuses if not t.is_ok)

    @property
    def services_with_errors(self) -> int:
        """Count services with log errors."""
        return sum(1 for r in self.log_results if r.has_errors)

    @property
    def services_with_warnings(self) -> int:
        """Count services with only warnings (no errors)."""
        return sum(1 for r in self.log_results if r.has_warnings)

    @property
    def disk_failures(self) -> int:
        """Count drives with failures."""
        return self.disk_health.failed_drives


class DoctorCommand(Command[DoctorArgs]):
    """Run comprehensive health checks on timers and service logs."""

    async def execute(self, args: DoctorArgs, ctx: AppContext) -> int:
        """Execute doctor checks asynchronously, print synchronously."""
        console = Console()

        # Print header
        console.print(
            Panel.fit(
                "[bold]svc doctor[/bold]",
                border_style="blue",
            )
        )
        console.print()

        # Collect timer tasks
        timer_tasks = [
            self._check_timer(ctx, timer) for timer in ctx.config.timers
        ]

        # Collect log tasks only in full mode
        log_tasks: list = []
        if args.full:
            all_containers = await ctx.docker.list_containers()
            containers_by_project: dict[str, list[str]] = {}
            for container in all_containers:
                if container.project:
                    containers_by_project.setdefault(container.project, []).append(container.name)

            log_tasks = [
                self._scan_logs(
                    ctx,
                    name,
                    svc,
                    args.since,
                    containers_by_project.get(name, []),
                )
                for name, svc in ctx.config.services.items()
            ]

        # Run all tasks concurrently and collect results
        timer_results: list[TimerStatus] = []
        log_results: list[LogScanResult] = []

        # Process timer results
        for coro in asyncio.as_completed(timer_tasks):
            result = await coro
            timer_results.append(result)

        # Process log results (only if full mode)
        for coro in asyncio.as_completed(log_tasks):
            result = await coro
            log_results.append(result)

        # Sort results for consistent output
        timer_results.sort(key=lambda t: t.name)
        if log_results:
            log_results.sort(key=lambda r: (r.severity != LogSeverity.ERROR, r.service))

        # Load disk health report (sync, just reads a file)
        disk_health = load_disk_health_report()

        results = DoctorResults(
            timer_statuses=timer_results,
            log_results=log_results,
            disk_health=disk_health,
        )

        # Render all sections
        self._render_timers_section(console, results.timer_statuses)
        console.print()
        self._render_disk_health_section(console, results.disk_health)
        if args.full:
            console.print()
            self._render_logs_section(console, results.log_results, args.since)
            console.print()
            self._render_details_section(console, results)
        else:
            console.print()
        self._render_summary(console, results, full_mode=args.full)

        return EXIT_SUCCESS

    async def _check_timer(self, ctx: AppContext, timer: TimerConfig) -> TimerStatus:
        """Check a single timer's status."""
        return await ctx.systemctl.get_timer_status(timer)

    async def _scan_logs(
        self,
        ctx: AppContext,
        name: str,
        svc: ServiceConfig,
        since: str,
        container_names: list[str],
    ) -> LogScanResult:
        """Scan logs for a single service."""
        # Use service-specific patterns if configured, otherwise defaults
        monitoring = svc.monitoring
        error_patterns = monitoring.error_patterns if monitoring else None
        warning_patterns = monitoring.warning_patterns if monitoring else None
        ignore_patterns = monitoring.ignore_patterns if monitoring else None

        patterns = (
            LogScanPatterns(
                error=error_patterns,
                warning=warning_patterns,
                ignore=ignore_patterns,
            )
            if error_patterns or warning_patterns or ignore_patterns
            else None
        )

        options = LogScanOptions(
            patterns=patterns,
            since=since,
            container_names=container_names or None,
        )

        return await ctx.logs.scan_service_logs(
            name,
            options=options,
        )

    def _render_timers_section(
        self, console: Console, timers: list[TimerStatus]
    ) -> None:
        """Render the timers status table."""
        console.print("[bold]\u23f1\ufe0f  Timers[/bold]")
        console.print("\u2501" * 70)

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Timer", style="bold")
        table.add_column("Last Run")
        table.add_column("Next Run")
        table.add_column("Status", justify="center")

        for timer in timers:
            # Determine row style based on status
            if timer.is_ok:
                status = Text("\u2713", style="green")
                row_style = "not bold bright_black"
            else:
                status = Text("\u2717", style="red")
                row_style = "red"

            table.add_row(
                Text(timer.name, style=row_style),
                Text(timer.last_run or "-", style=row_style),
                Text(timer.next_run or "-", style=row_style),
                status,
            )

        console.print(table)

    def _format_test_status(self, result: TestResult | None) -> Text:
        """Format a test result as a status indicator."""
        if result is None:
            return Text("-", style="dim")

        status = result.status
        if status == "healthy":
            return Text("\u2713", style="green")
        if status == "testing":
            return Text("\u2026", style="yellow")  # ellipsis
        if status in ("failed", "degraded"):
            return Text("\u2717", style="red")
        return Text("?", style="dim")

    def _render_disk_health_section(
        self, console: Console, report: DiskHealthReport
    ) -> None:
        """Render the disk health status table with per-test columns."""
        if not report.available:
            console.print("[bold]\U0001f4be Disk Health[/bold]")
            console.print("\u2501" * 70)
            console.print("[dim]No disk health report available. Run disk-health-quick.service first.[/dim]")
            return

        # Parse timestamp for display
        last_update = report.last_update[:16].replace("T", " ") if report.last_update else "-"
        console.print(f"[bold]\U0001f4be Disk Health (updated: {last_update})[/bold]")
        console.print("\u2501" * 70)

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Device", style="bold")
        table.add_column("Model")
        table.add_column("Quick", justify="center")
        table.add_column("Short", justify="center")
        table.add_column("Long", justify="center")

        for drive in report.drives:
            # Determine row style based on whether any test failed
            if drive.has_failure():
                row_style = "red"
            else:
                row_style = "not bold bright_black"

            table.add_row(
                Text(drive.device, style=row_style),
                Text(drive.model, style=row_style),
                self._format_test_status(drive.quick),
                self._format_test_status(drive.short),
                self._format_test_status(drive.long),
            )

        console.print(table)

    def _render_logs_section(
        self, console: Console, results: list[LogScanResult], since: str
    ) -> None:
        """Render the service logs summary table."""
        console.print(f"[bold]\U0001f4cb Service Logs (last {since})[/bold]")
        console.print("\u2501" * 70)

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Service", style="bold")
        table.add_column("Errors", justify="right")  # Shows "total (unique)" when deduplicated
        table.add_column("Warnings", justify="right")
        table.add_column("Status", justify="center")

        for result in results:
            if result.severity == LogSeverity.ERROR:
                row_style = "red"
                status = Text("\u2717", style="red")
            elif result.severity == LogSeverity.WARNING:
                row_style = "yellow"
                status = Text("\u26a0", style="yellow")
            else:
                row_style = "not bold bright_black"
                status = Text("\u2713", style="green")

            # Format counts with unique info when there's deduplication
            if result.error_count > 0 and result.unique_errors < result.error_count:
                error_text = f"{result.error_count} ({result.unique_errors})"
            else:
                error_text = str(result.error_count)

            if result.warning_count > 0 and result.unique_warnings < result.warning_count:
                warning_text = f"{result.warning_count} ({result.unique_warnings})"
            else:
                warning_text = str(result.warning_count)

            table.add_row(
                Text(result.service, style=row_style),
                Text(error_text, style=row_style),
                Text(warning_text, style=row_style),
                status,
            )

        console.print(table)

    def _render_details_section(self, console: Console, results: DoctorResults) -> None:
        """Render detailed error/warning entries for services with issues."""
        # Find services with issues
        services_with_issues = [
            r for r in results.log_results if r.error_count > 0 or r.warning_count > 0
        ]
        failed_timers = [t for t in results.timer_statuses if not t.is_ok]

        if not services_with_issues and not failed_timers:
            return

        console.print()

        # Render service log details
        for result in services_with_issues:
            if result.error_count > 0:
                header_style = "red"
                if result.unique_errors < result.error_count:
                    label = f"{result.error_count} error{'s' if result.error_count != 1 else ''} ({result.unique_errors} unique)"
                else:
                    label = f"{result.error_count} error{'s' if result.error_count != 1 else ''}"
            else:
                header_style = "yellow"
                if result.unique_warnings < result.warning_count:
                    label = f"{result.warning_count} warning{'s' if result.warning_count != 1 else ''} ({result.unique_warnings} unique)"
                else:
                    label = f"{result.warning_count} warning{'s' if result.warning_count != 1 else ''}"

            console.print("\u2501" * 70)
            console.print(f"[{header_style}]\U0001f4cd {result.service} \u2014 {label}[/{header_style}]")
            console.print("\u2501" * 70)

            for entry in result.entries:
                style = "red" if entry.severity == LogSeverity.ERROR else "yellow"
                # Show occurrence count for deduplicated entries
                if entry.count > 1:
                    count_suffix = f" [dim](x{entry.count})[/dim]"
                else:
                    count_suffix = ""
                console.print(f"  [{style}][{entry.timestamp}] {entry.message}{count_suffix}[/{style}]")

            console.print()

        # Render failed timer details
        for timer in failed_timers:
            console.print("\u2501" * 70)
            console.print(f"[red]\U0001f4cd {timer.name} \u2014 timer failed[/red]")
            console.print("\u2501" * 70)
            console.print(f"  Last result: {timer.last_result.value}")
            console.print(
                f"  Use `journalctl -u {timer.unit.replace('.timer', '.service')}` to investigate"
            )
            console.print()

    def _render_summary(
        self, console: Console, results: DoctorResults, *, full_mode: bool
    ) -> None:
        """Render the final summary line."""
        issues: list[str] = []
        if results.disk_failures > 0:
            issues.append(f"{results.disk_failures} drive(s) failing")
        if full_mode:
            if results.services_with_errors > 0:
                issues.append(f"{results.services_with_errors} service(s) with errors")
            if results.services_with_warnings > 0:
                issues.append(f"{results.services_with_warnings} service(s) with warnings")
        if results.timer_failures > 0:
            issues.append(f"{results.timer_failures} timer(s) failed")

        if issues:
            summary = ", ".join(issues)
            console.print(f"[bold]Summary:[/bold] [yellow]{summary}[/yellow]")
        else:
            console.print("[bold]Summary:[/bold] [green]All systems healthy \u2713[/green]")
