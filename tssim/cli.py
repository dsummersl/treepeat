"""CLI interface for tssim."""

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from tssim.config import (
    LSHSettings,
    MinHashSettings,
    NormalizerSettings,
    PipelineSettings,
    ShingleSettings,
    set_settings,
)
from tssim.models.similarity import SimilarityResult
from tssim.pipeline.normalizer_factory import get_available_normalizers
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

    console.print("\n[bold cyan]Similar Regions:[/bold cyan]")
    for pair in result.similar_pairs:
        # Calculate line counts for each region
        lines1 = pair.region1.end_line - pair.region1.start_line + 1
        lines2 = pair.region2.end_line - pair.region2.start_line + 1

        # Display similarity group header
        console.print(
            f"  2 regions, [bold]{pair.similarity:.1%}[/bold] similar, {lines1}-{lines2} lines:"
        )

        # Display each region in the group
        console.print(
            f"    • {pair.region1.path}:{pair.region1.start_line}-{pair.region1.end_line} ({pair.region1.region_name})"
        )
        console.print(
            f"    • {pair.region2.path}:{pair.region2.start_line}-{pair.region2.end_line} ({pair.region2.region_name})"
        )
        console.print()  # Blank line between groups


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
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="WARNING",
    help="Set the logging level",
)
@click.option(
    "--list-normalizers",
    is_flag=True,
    default=False,
    help="List all available normalizers and exit",
)
@click.option(
    "--disable-normalizers",
    type=str,
    default="",
    help="Comma-separated list of normalizers to disable (e.g., 'python-imports')",
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
    default=0.8,
    help="LSH similarity threshold 0.0-1.0 (default: 0.5)",
)
def main(
    path: Path | None,
    log_level: str,
    list_normalizers: bool,
    disable_normalizers: str,
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

    # Handle --list-normalizers
    if list_normalizers:
        console.print("\n[bold blue]Available Normalizers:[/bold blue]\n")
        for spec in get_available_normalizers():
            console.print(f"  [cyan]{spec.name}[/cyan]")
            console.print(f"    {spec.description}")
            console.print()
        return

    # PATH is required for normal operation
    if path is None:
        console.print("[bold red]Error:[/bold red] PATH is required")
        console.print("Try 'tssim --help' for more information.")
        sys.exit(1)

    # Parse disabled normalizers
    disabled_list = [n.strip() for n in disable_normalizers.split(",") if n.strip()]

    # Validate normalizer names
    available_names = {spec.name for spec in get_available_normalizers()}
    for name in disabled_list:
        if name not in available_names:
            console.print(f"[bold red]Error:[/bold red] Unknown normalizer '{name}'")
            console.print(f"Available normalizers: {', '.join(sorted(available_names))}")
            console.print("Use --list-normalizers to see all available normalizers")
            sys.exit(1)

    # Initialize pipeline settings
    settings = PipelineSettings(
        normalizer=NormalizerSettings(disabled_normalizers=disabled_list),
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
    display_similar_pairs(result)
    display_failed_files(result, show_details=(log_level.upper() == "DEBUG"))

    console.print()


if __name__ == "__main__":
    main()
