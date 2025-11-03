"""CLI interface for tssim."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from tssim.config import (
    NormalizerSettings,
    PipelineSettings,
    PythonNormalizerSettings,
    ShingleSettings,
    set_settings,
)
from tssim.models.shingle import ShingleResult
from tssim.pipeline.pipeline import run_pipeline

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


def display_summary_table(result: ShingleResult) -> None:
    """Display a summary table of pipeline results."""
    table = Table(title="Pipeline Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")

    table.add_row("Total Files", str(result.total_files))
    table.add_row("Successfully Processed", str(result.success_count))
    table.add_row("Failed", str(result.failure_count))

    console.print(table)


def display_shingled_files(result: ShingleResult) -> None:
    """Display successfully shingled files."""
    if not result.shingled_files:
        return

    console.print("\n[bold green]Successfully Processed Files:[/bold green]")
    for shingled_file in result.shingled_files:
        console.print(
            f"  [green]✓[/green] {shingled_file.path} "
            f"([dim]{shingled_file.language}, {shingled_file.shingle_count} shingles[/dim])"
        )


def display_failed_files(result: ShingleResult, show_details: bool) -> None:
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
# TODO we'll need a generic solution here since they'll be so many to disable (maybe just take a list of values rather than explicit tags for each one)
@click.option(
    "--python-no-ignore-imports",
    is_flag=True,
    default=False,
    help="Include import statements in Python files (by default they are ignored)",
)
@click.option(
    "--shingle-k",
    type=int,
    default=3,
    help="Length of k-grams for shingling (default: 3)",
)
@click.option(
    "--shingle-include-text",
    is_flag=True,
    default=False,
    help="Include node text in shingles for more specificity",
)
def main(
    path: Path,
    log_level: str,
    python_no_ignore_imports: bool,
    shingle_k: int,
    shingle_include_text: bool,
) -> None:
    """
    Analyze code similarity in PATH.

    PATH can be a file or directory containing source code files.
    """
    setup_logging(log_level.upper())

    # Initialize pipeline settings
    settings = PipelineSettings(
        normalizer=NormalizerSettings(
            python=PythonNormalizerSettings(ignore_imports=not python_no_ignore_imports)
        ),
        shingle=ShingleSettings(k=shingle_k, include_text=shingle_include_text),
    )
    set_settings(settings)

    console.print("\n[bold blue]tssim - Code Similarity Detection[/bold blue]")
    console.print(f"Analyzing: [cyan]{path}[/cyan]\n")

    # Run the full pipeline
    with console.status("[bold green]Running pipeline..."):
        result = run_pipeline(path)

    # Check for complete failure
    if result.success_count == 0 and result.failure_count > 0:
        console.print("[bold red]Error:[/bold red] Failed to parse any files")
        display_failed_files(result, show_details=True)
        sys.exit(1)

    # Display results
    display_summary_table(result)
    display_shingled_files(result)
    display_failed_files(result, show_details=(log_level.upper() == "DEBUG"))

    console.print()


if __name__ == "__main__":
    main()
