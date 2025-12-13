"""Renderer abstraction for CLI output."""

import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, Optional

from rich.console import Console, RenderableType
from rich.markup import escape as rich_escape
from rich.table import Table
from rich.text import Text

RICH_AVAILABLE: Final[bool] = True


@dataclass
class TableColumn:
    """Definition for a table column."""

    name: str
    style: str = ""
    justify: Literal["default", "left", "center", "right", "full"] = "left"


@dataclass
class TableRow:
    """A single row of table data."""

    cells: Sequence[RenderableType | str]


class Renderer(ABC):
    """Abstract base class for output rendering."""

    @abstractmethod
    def print_heading(self, title: str) -> None:
        """Print a section heading."""
        ...

    @abstractmethod
    def print_ok(self, message: str) -> None:
        """Print a success message."""
        ...

    @abstractmethod
    def print_warn(self, message: str) -> None:
        """Print a warning message."""
        ...

    @abstractmethod
    def print_error(self, message: str) -> None:
        """Print an error message."""
        ...

    @abstractmethod
    def print_info(self, message: str) -> None:
        """Print an informational message."""
        ...

    @abstractmethod
    def render_table(
        self,
        title: str,
        columns: Sequence[TableColumn],
        rows: Sequence[TableRow],
    ) -> None:
        """Render a table with the given columns and rows."""
        ...

    @abstractmethod
    def format_check(self, ok: bool) -> RenderableType | str:
        """Format a boolean as a check mark or dash."""
        ...

    @abstractmethod
    def format_status(self, ok: bool, detail: str) -> RenderableType | str:
        """Format a status indicator with detail text."""
        ...


class RichRenderer(Renderer):
    """Rich library-based renderer with colors and formatting."""

    def __init__(self, console: Optional["Console"] = None):
        self.console = console or Console()

    def _escape(self, text: str) -> str:
        """Escape text for Rich markup."""
        return rich_escape(text)

    def print_heading(self, title: str) -> None:
        self.console.print(f"[bold blue]== {self._escape(title)} ==[/]")

    def print_ok(self, message: str) -> None:
        self.console.print(f"[green]OK[/] {self._escape(message)}")

    def print_warn(self, message: str) -> None:
        self.console.print(f"[yellow]WARN[/] {self._escape(message)}")

    def print_error(self, message: str) -> None:
        self.console.print(f"[red]ERROR[/] {self._escape(message)}")

    def print_info(self, message: str) -> None:
        self.console.print(self._escape(message))

    def render_table(
        self,
        title: str,
        columns: Sequence[TableColumn],
        rows: Sequence[TableRow],
    ) -> None:
        table = Table(title=title, header_style="bold", show_lines=False)

        for col in columns:
            table.add_column(col.name, style=col.style or None, justify=col.justify)

        for row in rows:
            rendered_cells: list[RenderableType | str] = []
            for cell in row.cells:
                if isinstance(cell, str):
                    rendered_cells.append(self._escape(cell))
                else:
                    rendered_cells.append(cell)
            table.add_row(*rendered_cells)

        self.console.print(table)

    def format_check(self, ok: bool) -> RenderableType | str:
        return Text("✓", style="green") if ok else Text("-", style="dim")

    def format_status(self, ok: bool, detail: str) -> RenderableType | str:
        icon = Text("✓", style="green") if ok else Text("✗", style="red")
        message = Text(self._escape(detail))
        return Text.assemble(icon, " ", message)


class PlainRenderer(Renderer):
    """Plain text renderer for non-TTY or fallback output."""

    def print_heading(self, title: str) -> None:
        print(f"== {title} ==")

    def print_ok(self, message: str) -> None:
        print(f"OK: {message}")

    def print_warn(self, message: str) -> None:
        print(f"WARN: {message}")

    def print_error(self, message: str) -> None:
        print(f"ERROR: {message}")

    def print_info(self, message: str) -> None:
        print(message)

    def render_table(
        self,
        title: str,
        columns: Sequence[TableColumn],
        rows: Sequence[TableRow],
    ) -> None:
        print(f"\n{title}")
        print("-" * len(title))

        # Print header
        header = "  ".join(col.name for col in columns)
        print(header)

        # Print rows
        for row in rows:
            print("  ".join(str(cell) for cell in row.cells))

        print()

    def format_check(self, ok: bool) -> RenderableType | str:
        return "✓" if ok else "-"

    def format_status(self, ok: bool, detail: str) -> RenderableType | str:
        status = "OK" if ok else "FAIL"
        return f"{status}: {detail}"


def create_renderer(force_plain: bool = False) -> Renderer:
    """Create the appropriate renderer based on environment."""
    if force_plain:
        return PlainRenderer()

    if RICH_AVAILABLE and sys.stderr.isatty():
        return RichRenderer()

    return PlainRenderer()
