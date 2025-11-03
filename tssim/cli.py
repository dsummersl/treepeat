"""CLI interface for tssim."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from tssim.config import (
    LSHSettings,
    MinHashSettings,
    NormalizerSettings,
    PipelineSettings,
    PythonNormalizerSettings,
    ShingleSettings,
    set_settings,
)
from tssim.models.similarity import SimilarityResult
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


def display_summary_table(result: SimilarityResult) -> None:
    """Display a summary table of pipeline results."""
    table = Table(title="Pipeline Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="green")

    table.add_row("Total Files", str(result.total_files))
    table.add_row("Total Regions", str(result.total_regions))
    table.add_row("Failed Files", str(result.failure_count))
    table.add_row("Similar Pairs Found", str(result.pair_count))
    table.add_row("Self-Similar Regions", str(result.self_similarity_count))

    console.print(table)


def display_processed_regions(result: SimilarityResult) -> None:
    """Display successfully processed regions grouped by file."""
    if not result.signatures:
        return

    # Group regions by file
    from tssim.models.similarity import RegionSignature

    regions_by_file: dict[Path, list[RegionSignature]] = {}
    for sig in result.signatures:
        path = sig.region.path
        if path not in regions_by_file:
            regions_by_file[path] = []
        regions_by_file[path].append(sig)

    console.print(f"\n[bold green]Processed {len(regions_by_file)} file(s) with {len(result.signatures)} region(s):[/bold green]")
    for path, sigs in sorted(regions_by_file.items()):
        console.print(f"\n  [green]✓[/green] {path} ([dim]{len(sigs)} region(s)[/dim])")
        for sig in sigs:
            console.print(
                f"    • {sig.region.region_name} ({sig.region.region_type}) "
                f"[dim]lines {sig.region.start_line}-{sig.region.end_line}, "
                f"{sig.shingle_count} shingles[/dim]"
            )


def display_similar_pairs(result: SimilarityResult) -> None:
    """Display similar region pairs."""
    if not result.similar_pairs:
        console.print("\n[yellow]No similar regions found above threshold.[/yellow]")
        return

    # Separate cross-file and self-similarity
    cross_file_pairs = [p for p in result.similar_pairs if not p.is_self_similarity]
    self_similar_pairs = [p for p in result.similar_pairs if p.is_self_similarity]

    if cross_file_pairs:
        console.print("\n[bold cyan]Similar Regions Across Files:[/bold cyan]")
        for pair in cross_file_pairs:
            console.print(
                f"  [cyan]↔[/cyan] {pair.region1.region_name} in {pair.region1.path}:{pair.region1.start_line}-{pair.region1.end_line}\n"
                f"     [dim]↔[/dim] {pair.region2.region_name} in {pair.region2.path}:{pair.region2.start_line}-{pair.region2.end_line}\n"
                f"     ([bold]{pair.similarity:.1%}[/bold] similar)"
            )

    if self_similar_pairs:
        console.print("\n[bold yellow]Self-Similar Regions (within same file):[/bold yellow]")
        for pair in self_similar_pairs:
            console.print(
                f"  [yellow]⚠[/yellow] {pair.region1.path}\n"
                f"     • {pair.region1.region_name} (lines {pair.region1.start_line}-{pair.region1.end_line})\n"
                f"     • {pair.region2.region_name} (lines {pair.region2.start_line}-{pair.region2.end_line})\n"
                f"     ([bold]{pair.similarity:.1%}[/bold] similar)"
            )


def display_failed_files(result: SimilarityResult, show_details: bool) -> None:
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
@click.option(
    "--minhash-num-perm",
    type=int,
    default=128,
    help="Number of MinHash permutations (default: 128, higher = more accurate)",
)
@click.option(
    "--lsh-threshold",
    type=float,
    default=0.5,
    help="LSH similarity threshold 0.0-1.0 (default: 0.5)",
)
def main(
    path: Path,
    log_level: str,
    python_no_ignore_imports: bool,
    shingle_k: int,
    shingle_include_text: bool,
    minhash_num_perm: int,
    lsh_threshold: float,
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
        minhash=MinHashSettings(num_perm=minhash_num_perm),
        lsh=LSHSettings(threshold=lsh_threshold),
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
    display_similar_pairs(result)
    display_processed_regions(result)
    display_failed_files(result, show_details=(log_level.upper() == "DEBUG"))

    console.print()


if __name__ == "__main__":
    main()
