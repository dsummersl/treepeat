"""CLI interface for tssim."""

import difflib
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.syntax import Syntax

from tssim.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from tssim.formatters import format_as_json, format_as_sarif
from tssim.models.similarity import RegionSignature, SimilarRegionGroup, SimilarityResult
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


def _group_signatures_by_file(
    signatures: list[RegionSignature],
) -> dict[Path, list[RegionSignature]]:
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

    console.print(
        f"\n[bold green]Processed {len(regions_by_file)} file(s) with {len(result.signatures)} region(s):[/bold green]"
    )
    for path, sigs in sorted(regions_by_file.items()):
        console.print(f"\n  [green]✓[/green] {path} ([dim]{len(sigs)} region(s)[/dim])")
        for sig in sigs:
            console.print(
                f"    • {sig.region.region_name} ({sig.region.region_type}) "
                f"[dim]lines {sig.region.start_line}-{sig.region.end_line}, "
                f"{sig.shingle_count} shingles[/dim]"
            )


def _get_group_sort_key(group: SimilarRegionGroup) -> tuple[float, float]:
    """Get sort key for a similarity group.

    Args:
        group: SimilarRegionGroup to sort

    Returns:
        Tuple of (similarity, average line count)
    """
    avg_lines = sum(r.end_line - r.start_line + 1 for r in group.regions) / len(group.regions)
    return (group.similarity, avg_lines)


def _read_region_lines(region: "Region") -> list[str]:  # type: ignore[name-defined]
    """Read lines from a file for a specific region.

    Args:
        region: Region to read lines from

    Returns:
        List of lines from the region
    """
    try:
        with open(region.path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Extract lines for this region (1-indexed to 0-indexed)
            return lines[region.start_line - 1 : region.end_line]
    except Exception as e:
        logging.warning(f"Failed to read region from {region.path}: {e}")
        return []


def _display_diff(region1: "Region", region2: "Region") -> None:  # type: ignore[name-defined]
    """Display a unified diff between two regions.

    Args:
        region1: First region to compare
        region2: Second region to compare
    """
    lines1 = _read_region_lines(region1)
    lines2 = _read_region_lines(region2)

    if not lines1 or not lines2:
        console.print("  [yellow]Unable to generate diff (failed to read file content)[/yellow]\n")
        return

    # Generate unified diff
    diff_lines = difflib.unified_diff(
        lines1,
        lines2,
        fromfile=f"{region1.path}:{region1.start_line}-{region1.end_line}",
        tofile=f"{region2.path}:{region2.start_line}-{region2.end_line}",
        lineterm="",
    )

    diff_text = "\n".join(diff_lines)

    if not diff_text:
        console.print("  [green]No differences found (regions are identical)[/green]\n")
        return

    # Display diff with syntax highlighting using Rich
    console.print("  [bold]Diff:[/bold]")
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False, word_wrap=True)
    console.print(syntax)
    console.print()


def _display_group(group: SimilarRegionGroup, show_diff: bool = False) -> None:
    """Display a single similarity group.

    Args:
        group: SimilarRegionGroup to display
        show_diff: If True, show diff between first two regions in the group
    """
    # Display similarity group header
    console.print(f"Similar group found ([bold]{group.similarity:.1%}[/bold] similar, {group.size} regions):")

    # Display all regions in the group
    for i, region in enumerate(group.regions):
        lines = region.end_line - region.start_line + 1
        prefix = "  - " if i == 0 else "    "
        console.print(
            f"{prefix}{region.path} [{region.start_line}:{region.end_line}] "
            f"({lines} lines) {region.region_name}"
        )

    # Show diff if requested and we have at least 2 regions
    if show_diff and len(group.regions) >= 2:
        console.print()
        _display_diff(group.regions[0], group.regions[1])
    else:
        console.print()  # Blank line between groups


def display_similar_groups(result: SimilarityResult, show_diff: bool = False) -> None:
    """Display similar region groups.

    Args:
        result: Similarity result to display
        show_diff: If True, show diff between first two regions in each group
    """
    if not result.similar_groups:
        console.print("\n[yellow]No similar regions found above threshold.[/yellow]")
        return

    console.print("\n[bold cyan]Similar Regions:[/bold cyan]")
    sorted_groups = sorted(result.similar_groups, key=_get_group_sort_key)

    for group in sorted_groups:
        _display_group(group, show_diff=show_diff)


def display_failed_files(result: SimilarityResult, show_details: bool) -> None:
    """Display failed files with optional error details."""
    if not result.failed_files:
        return

    console.print("\n[bold red]Failed Files:[/bold red]")
    for file_path, error in result.failed_files.items():
        console.print(f"  [red]✗[/red] {file_path}")
        if show_details:
            console.print(f"    [dim]{error}[/dim]")


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
        from tssim.config import get_settings
        settings = get_settings()
        console.print(f"\nRuleset: [cyan]{settings.rules.ruleset}[/cyan]")
        console.print(f"Analyzing: [cyan]{path}[/cyan]\n")
        with console.status("[bold green]Running pipeline..."):
            return run_pipeline(path)
    else:
        return run_pipeline(path)


def _handle_output(
    result: SimilarityResult,
    output_format: str,
    output_path: Path | None,
    log_level: str,
    show_diff: bool = False,
) -> None:
    """Handle formatting and outputting results.

    Args:
        result: The similarity result
        output_format: Output format (console, json, sarif)
        output_path: Path to output file, or None for stdout
        log_level: Logging level for debug output
        show_diff: If True, show diff between first two regions in each group
    """
    if output_format.lower() == "json":
        output_text = format_as_json(result, pretty=True)
        _write_output(output_text, output_path)
    elif output_format.lower() == "sarif":
        output_text = format_as_sarif(result, pretty=True)
        _write_output(output_text, output_path)
    else:  # console
        display_similar_groups(result, show_diff=show_diff)
        display_failed_files(result, show_details=(log_level.upper() == "DEBUG"))
        console.print()


def _parse_patterns(pattern_string: str) -> list[str]:
    """Parse comma-separated pattern string into list.

    Args:
        pattern_string: Comma-separated patterns

    Returns:
        List of stripped non-empty patterns
    """
    return [p.strip() for p in pattern_string.split(",") if p.strip()]


def _create_rules_settings(rules: str, rules_file: str, ruleset: str) -> RulesSettings:
    """Create RulesSettings with proper None handling.

    Args:
        rules: Comma-separated list of rule specifications
        rules_file: Path to file containing rule specifications
        ruleset: Ruleset profile to use (none, default, loose)

    Returns:
        RulesSettings object
    """
    return RulesSettings(
        ruleset=ruleset,
        rules=rules or None,
        rules_file=rules_file or None,
    )


def _configure_settings(
    rules: str,
    rules_file: str,
    ruleset: str,
    shingle_k: int,
    minhash_num_perm: int,
    threshold: float,
    min_lines: int,
    ignore: str,
    ignore_files: str,
) -> None:
    """Configure pipeline settings.

    Args:
        rules: Comma-separated list of rule specifications
        rules_file: Path to file containing rule specifications (one per line)
        ruleset: Ruleset profile to use (none, default, loose)
        shingle_k: Length of k-grams for shingling
        minhash_num_perm: Number of MinHash permutations
        threshold: LSH similarity threshold
        min_lines: Minimum number of lines for a match
        ignore: Comma-separated list of glob patterns to ignore files
        ignore_files: Comma-separated list of glob patterns to find ignore files
    """
    settings = PipelineSettings(
        rules=_create_rules_settings(rules, rules_file, ruleset),
        shingle=ShingleSettings(k=shingle_k),
        minhash=MinHashSettings(num_perm=minhash_num_perm),
        lsh=LSHSettings(threshold=threshold, min_lines=min_lines),
        ignore_patterns=_parse_patterns(ignore),
        ignore_file_patterns=_parse_patterns(ignore_files),
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
    "--rules",
    type=str,
    default="",
    help="Comma-separated list of rule specifications (e.g., 'python:skip:nodes=import_statement')",
)
@click.option(
    "--rules-file",
    type=str,
    default="",
    help="Path to file containing rule specifications (one per line)",
)
@click.option(
    "--ruleset",
    type=click.Choice(["none", "default", "loose"], case_sensitive=False),
    default="default",
    help="Ruleset profile to use (default: default)",
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
    "--threshold",
    type=float,
    default=1.0,
    help="Filter threshold for similarity (default: 1.0)",
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
@click.option(
    "--show-diff",
    is_flag=True,
    default=False,
    help="Show inline diff between the first two files in each similar group (console format only)",
)
def main(
    path: Path | None,
    log_level: str,
    rules: str,
    rules_file: str,
    ruleset: str,
    shingle_k: int,
    shingle_include_text: bool,
    minhash_num_perm: int,
    threshold: float,
    min_lines: int,
    output_format: str,
    output: Path | None,
    ignore: str,
    ignore_files: str,
    show_diff: bool,
) -> None:
    """
    Analyze code similarity in PATH.

    PATH can be a file or directory containing source code files.
    """
    setup_logging(log_level.upper())

    if path is None:
        console.print("[bold red]Error:[/bold red] PATH is required")
        console.print("Try 'tssim --help' for more information.")
        sys.exit(1)

    _configure_settings(
        rules,
        rules_file,
        ruleset,
        shingle_k,
        minhash_num_perm,
        threshold,
        min_lines,
        ignore,
        ignore_files,
    )
    result = _run_pipeline_with_ui(path, output_format)
    _check_result_errors(result, output_format)
    _handle_output(result, output_format, output, log_level, show_diff)


if __name__ == "__main__":
    main()
