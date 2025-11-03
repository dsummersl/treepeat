"""CLI interface for tssim."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from tssim.models import ParseResult
from tssim.pipeline import parse_path

console = Console()


def setup_logging(log_level: str) -> None:
    """
    Configure logging with rich handler.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def display_summary_table(result: ParseResult) -> None:
    """Display a summary table of parse results."""
    table = Table(title="Parse Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")

    table.add_row("Total Files", str(result.total_files))
    table.add_row("Successfully Parsed", str(result.success_count))
    table.add_row("Failed", str(result.failure_count))

    console.print(table)


def display_parsed_files(result: ParseResult) -> None:
    """Display successfully parsed files."""
    if not result.parsed_files:
        return

    console.print("\n[bold green]Successfully Parsed Files:[/bold green]")
    for parsed_file in result.parsed_files:
        console.print(
            f"  [green]✓[/green] {parsed_file.path} " f"([dim]{parsed_file.language}[/dim])"
        )


def display_failed_files(result: ParseResult, show_details: bool) -> None:
    """Display failed files with optional error details."""
    if not result.failed_files:
        return

    console.print("\n[bold red]Failed Files:[/bold red]")
    for file_path, error in result.failed_files.items():
        console.print(f"  [red]✗[/red] {file_path}")
        if show_details:
            console.print(f"    [dim]{error}[/dim]")


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    help="Set the logging level",
)
def main(path: Path, log_level: str) -> None:
    """
    Analyze code similarity in PATH.

    PATH can be a file or directory containing source code files.
    """
    setup_logging(log_level.upper())

    console.print("\n[bold blue]tssim - Code Similarity Detection[/bold blue]")
    console.print(f"Analyzing: [cyan]{path}[/cyan]\n")

    # Parse stage
    with console.status("[bold green]Parsing files..."):
        result = parse_path(path)

    # Check for complete failure
    if result.success_count == 0 and result.failure_count > 0:
        console.print("[bold red]Error:[/bold red] Failed to parse any files")
        display_failed_files(result, show_details=True)
        sys.exit(1)

    # Display results
    display_summary_table(result)
    display_parsed_files(result)
    display_failed_files(result, show_details=(log_level == "DEBUG"))

    console.print()


if __name__ == "__main__":
    main()
