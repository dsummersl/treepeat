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
from tssim.formatters import format_as_json, format_as_sarif
from tssim.models.similarity import RegionSignature, SimilarityResult
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


def _group_signatures_by_file(signatures: list[RegionSignature]) -> dict[Path, list[RegionSignature]]:
    """Group region signatures by file path.

    Args:
        signatures: List of region signatures

    Returns:
        Dictionary mapping file paths to lists of signatures
    """
    regions_by_file: dict[Path, list[RegionSignature]] = {}
    for sig in signatures:
        path = sig.region.path
        if path not in regions_by_file:
            regions_by_file[path] = []
        regions_by_file[path].append(sig)
    return regions_by_file


def display_processed_regions(result: SimilarityResult) -> None:
    """Display successfully processed regions grouped by file."""
    if not result.signatures:
        return

    regions_by_file = _group_signatures_by_file(result.signatures)

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

        # Display similarity group header (jscpd-style)
        console.print(f"Clone found ([bold]{pair.similarity:.1%}[/bold] similar):")

        # Display first region with leading dash (jscpd-style)
        console.print(
            f"  - {pair.region1.path} [{pair.region1.start_line} - {pair.region1.end_line}] "
            f"({lines1} lines) {pair.region1.region_name}"
        )

        # Display second region with indentation only (jscpd-style)
        console.print(
            f"    {pair.region2.path} [{pair.region2.start_line} - {pair.region2.end_line}] "
            f"({lines2} lines) {pair.region2.region_name}"
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


def _handle_list_normalizers() -> None:
    """Display available normalizers and exit."""
    console.print("\n[bold blue]Available Normalizers:[/bold blue]\n")
    for spec in get_available_normalizers():
        console.print(f"  [cyan]{spec.name}[/cyan]")
        console.print(f"    {spec.description}")
        console.print()


def _parse_normalizer_list(disable_normalizers: str) -> list[str]:
    """Parse comma-separated normalizer list.

    Args:
        disable_normalizers: Comma-separated list of normalizer names

    Returns:
        List of normalizer names
    """
    return [n.strip() for n in disable_normalizers.split(",") if n.strip()]


def _validate_normalizer_names(disabled_list: list[str]) -> None:
    """Validate normalizer names against available normalizers.

    Args:
        disabled_list: List of normalizer names to validate

    Raises:
        SystemExit: If any normalizer name is invalid
    """
    available_names = {spec.name for spec in get_available_normalizers()}
    for name in disabled_list:
        if name not in available_names:
            console.print(f"[bold red]Error:[/bold red] Unknown normalizer '{name}'")
            console.print(f"Available normalizers: {', '.join(sorted(available_names))}")
            console.print("Use --list-normalizers to see all available normalizers")
            sys.exit(1)


def _validate_and_parse_normalizers(disable_normalizers: str) -> list[str]:
    """Parse and validate normalizer names.

    Args:
        disable_normalizers: Comma-separated list of normalizer names

    Returns:
        List of validated normalizer names

    Raises:
        SystemExit: If any normalizer name is invalid
    """
    disabled_list = _parse_normalizer_list(disable_normalizers)
    if disabled_list:
        _validate_normalizer_names(disabled_list)
    return disabled_list


def _write_output(text: str, output_path: Path | None) -> None:
    """Write output text to file or stdout.

    Args:
        text: The text to write
        output_path: Path to output file, or None for stdout
    """
    if output_path:
        output_path.write_text(text)
    else:
        print(text)


def _run_pipeline_with_ui(path: Path, output_format: str) -> SimilarityResult:
    """Run the pipeline with appropriate UI feedback based on output format.

    Args:
        path: Path to analyze
        output_format: Output format (console, json, sarif)

    Returns:
        The similarity result
    """
    if output_format.lower() == "console":
        console.print("\n[bold blue]tssim - Code Similarity Detection[/bold blue]")
        console.print(f"Analyzing: [cyan]{path}[/cyan]\n")
        with console.status("[bold green]Running pipeline..."):
            return run_pipeline(path)
    else:
        return run_pipeline(path)


def _handle_output(result: SimilarityResult, output_format: str, output_path: Path | None, log_level: str) -> None:
    """Handle formatting and outputting results.

    Args:
        result: The similarity result
        output_format: Output format (console, json, sarif)
        output_path: Path to output file, or None for stdout
        log_level: Logging level for debug output
    """
    if output_format.lower() == "json":
        output_text = format_as_json(result, pretty=True)
        _write_output(output_text, output_path)
    elif output_format.lower() == "sarif":
        output_text = format_as_sarif(result, pretty=True)
        _write_output(output_text, output_path)
    else:  # console
        display_similar_pairs(result)
        display_failed_files(result, show_details=(log_level.upper() == "DEBUG"))
        console.print()


def _configure_settings(
    disable_normalizers: str,
    shingle_k: int,
    minhash_num_perm: int,
    lsh_threshold: float,
    min_lines: int,
    ignore: str,
    ignore_files: str,
) -> None:
    """Configure pipeline settings.

    Args:
        disable_normalizers: Comma-separated list of normalizers to disable
        shingle_k: Length of k-grams for shingling
        minhash_num_perm: Number of MinHash permutations
        lsh_threshold: LSH similarity threshold
        min_lines: Minimum number of lines for a match
        ignore: Comma-separated list of glob patterns to ignore files
        ignore_files: Comma-separated list of glob patterns to find ignore files
    """
    disabled_list = _validate_and_parse_normalizers(disable_normalizers)

    # Parse ignore patterns
    ignore_patterns = [p.strip() for p in ignore.split(",") if p.strip()]
    ignore_file_patterns = [p.strip() for p in ignore_files.split(",") if p.strip()]

    settings = PipelineSettings(
        normalizer=NormalizerSettings(disabled_normalizers=disabled_list),
        shingle=ShingleSettings(k=shingle_k),
        minhash=MinHashSettings(num_perm=minhash_num_perm),
        lsh=LSHSettings(threshold=lsh_threshold, min_lines=min_lines),
        ignore_patterns=ignore_patterns,
        ignore_file_patterns=ignore_file_patterns,
    )
    set_settings(settings)


def _check_result_errors(result: SimilarityResult, output_format: str) -> None:
    """Check for errors in the result and exit if necessary.

    Args:
        result: The similarity result
        output_format: Output format (console, json, sarif)
    """
    if result.success_count == 0 and result.failure_count > 0:
        if output_format.lower() == "console":
            console.print("[bold red]Error:[/bold red] Failed to parse any files")
            display_failed_files(result, show_details=True)
        sys.exit(1)


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
@click.option(
    "--min-lines",
    type=int,
    default=5,
    help="Minimum number of lines for a match to be considered valid (default: 5)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["console", "json", "sarif"], case_sensitive=False),
    default="console",
    help="Output format (default: console)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: stdout)",
)
@click.option(
    "--ignore",
    type=str,
    default="",
    help="Comma-separated list of glob patterns to ignore files (e.g., '*.test.py,**/node_modules/**')",
)
@click.option(
    "--ignore-files",
    type=str,
    default="**/.*ignore",
    help="Comma-separated list of glob patterns to find ignore files (default: '**/.*ignore')",
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
    min_lines: int,
    output_format: str,
    output: Path | None,
    ignore: str,
    ignore_files: str,
) -> None:
    """
    Analyze code similarity in PATH.

    PATH can be a file or directory containing source code files.
    """
    setup_logging(log_level.upper())

    if list_normalizers:
        _handle_list_normalizers()
        return

    if path is None:
        console.print("[bold red]Error:[/bold red] PATH is required")
        console.print("Try 'tssim --help' for more information.")
        sys.exit(1)

    _configure_settings(disable_normalizers, shingle_k, minhash_num_perm, lsh_threshold, min_lines, ignore, ignore_files)
    result = _run_pipeline_with_ui(path, output_format)
    _check_result_errors(result, output_format)
    _handle_output(result, output_format, output, log_level)


if __name__ == "__main__":
    main()
