"""Detect command - find similar code regions."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from covey.config import LSHSettings, MinHashSettings, PipelineSettings, RulesSettings, ShingleSettings, set_settings
from covey.formatters import format_as_sarif
from covey.models.similarity import Region, RegionSignature, SimilarRegionGroup, SimilarityResult
from covey.pipeline.pipeline import run_pipeline

console = Console()


def _parse_patterns(pattern_string: str) -> list[str]:
    """Parse comma-separated pattern string into list."""
    return [p.strip() for p in pattern_string.split(",") if p.strip()]


def _create_rules_settings(ruleset: str) -> RulesSettings:
    """Create RulesSettings."""
    return RulesSettings(ruleset=ruleset)


def _configure_settings(
    ruleset: str,
    threshold: float | None,
    min_lines: int,
    ignore: str,
    ignore_files: str,
) -> None:
    """Configure pipeline settings."""
    # Create LSH settings - if threshold is None, use internal defaults
    if threshold is not None:
        lsh_settings = LSHSettings(threshold=threshold, min_lines=min_lines)
    else:
        lsh_settings = LSHSettings(min_lines=min_lines)

    settings = PipelineSettings(
        rules=_create_rules_settings(ruleset),
        shingle=ShingleSettings(),  # Uses default k=3
        minhash=MinHashSettings(),  # Uses default num_perm=128
        lsh=lsh_settings,
        ignore_patterns=_parse_patterns(ignore),
        ignore_file_patterns=_parse_patterns(ignore_files),
    )
    set_settings(settings)


def _write_output(text: str, output_path: Path | None) -> None:
    """Write output text to file or stdout."""
    if output_path:
        output_path.write_text(text)
    else:
        print(text)


def _run_pipeline_with_ui(path: Path, output_format: str) -> SimilarityResult:
    """Run the pipeline with appropriate UI feedback based on output format."""
    if output_format.lower() == "console":
        from covey.config import get_settings
        settings = get_settings()
        console.print(f"\nRuleset: [cyan]{settings.rules.ruleset}[/cyan]")
        console.print(f"Analyzing: [cyan]{path}[/cyan]\n")
        with console.status("[bold green]Running pipeline..."):
            return run_pipeline(path)
    else:
        return run_pipeline(path)


def _group_signatures_by_file(
    signatures: list[RegionSignature],
) -> dict[Path, list[RegionSignature]]:
    """Group region signatures by file path."""
    regions_by_file: dict[Path, list[RegionSignature]] = {}
    for sig in signatures:
        path = sig.region.path
        if path not in regions_by_file:
            regions_by_file[path] = []
        regions_by_file[path].append(sig)
    return regions_by_file


def _get_group_sort_key(group: SimilarRegionGroup) -> tuple[float, float]:
    """Get sort key for a similarity group by similarity and average line count."""
    avg_lines = sum(r.end_line - r.start_line + 1 for r in group.regions) / len(group.regions)
    return (group.similarity, avg_lines)


def _format_region_name(region: Region) -> str:
    """Format region name with type if not lines."""
    if region.region_type == "lines":
        return region.region_name
    return f"{region.region_name}({region.region_type})"


def _display_group(group: SimilarRegionGroup, show_diff: bool = False) -> None:
    """Display a single similarity group with optional diff."""
    from covey.diff import display_diff

    # Display similarity group header
    console.print(f"Similar group found ([bold]{group.similarity:.1%}[/bold] similar, {group.size} regions):")

    # Display all regions in the group
    for i, region in enumerate(group.regions):
        lines = region.end_line - region.start_line + 1
        prefix = "  - " if i == 0 else "    "
        region_display = _format_region_name(region)
        console.print(
            f"{prefix}{region.path} [{region.start_line}:{region.end_line}] "
            f"({lines} lines) {region_display}"
        )

    # Show diff if requested and we have at least 2 regions
    if show_diff and len(group.regions) >= 2:
        console.print()
        display_diff(group.regions[0], group.regions[1])
    else:
        console.print()  # Blank line between groups


def display_similar_groups(result: SimilarityResult, show_diff: bool = False) -> None:
    """Display similar region groups with optional diff."""
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


def _init_language_stats(
    stats_by_format: dict[str, dict[str, int | set[Path]]], language: str
) -> None:
    """Initialize stats entry for a language if not present."""
    if language not in stats_by_format:
        stats_by_format[language] = {"files": set(), "groups": 0, "lines": 0}


def _collect_files_from_signatures(
    signatures: list[RegionSignature],
) -> dict[str, dict[str, int | set[Path]]]:
    """Collect all processed files from signatures."""
    stats_by_format: dict[str, dict[str, int | set[Path]]] = {}

    for signature in signatures:
        region = signature.region
        language = region.language
        _init_language_stats(stats_by_format, language)
        stats = stats_by_format[language]
        stats["files"].add(region.path)  # type: ignore[union-attr]

    return stats_by_format


def _add_duplicate_stats(
    stats_by_format: dict[str, dict[str, int | set[Path]]],
    similar_groups: list[SimilarRegionGroup],
) -> None:
    """Add group counts and duplicate lines from similar groups."""
    for group in similar_groups:
        for region in group.regions:
            language = region.language
            _init_language_stats(stats_by_format, language)
            stats = stats_by_format[language]
            stats["lines"] += region.end_line - region.start_line + 1  # type: ignore[operator]

        # Count group once per language (use first region's language)
        if group.regions:
            first_language = group.regions[0].language
            stats_by_format[first_language]["groups"] += 1  # type: ignore[operator]


def _collect_format_statistics(result: SimilarityResult) -> dict[str, dict[str, int | set[Path]]]:
    """Collect statistics by language/format from all processed files."""
    stats_by_format = _collect_files_from_signatures(result.signatures)
    _add_duplicate_stats(stats_by_format, result.similar_groups)
    return stats_by_format


def _populate_summary_table(
    table: Table,
    stats_by_format: dict[str, dict[str, int | set[Path]]],
) -> tuple[set[Path], int, int]:
    """Populate summary table with format statistics and return totals."""
    total_files: set[Path] = set()
    total_groups = 0
    total_lines = 0

    for language in sorted(stats_by_format.keys()):
        stats = stats_by_format[language]
        files = stats["files"]
        groups = stats["groups"]
        lines = stats["lines"]

        # Type narrowing assertions
        assert isinstance(files, set)
        assert isinstance(groups, int)
        assert isinstance(lines, int)

        table.add_row(
            language,
            str(len(files)),
            str(groups),
            str(lines),
        )

        # Accumulate totals
        total_files.update(files)
        total_groups += groups
        total_lines += lines

    return total_files, total_groups, total_lines


def display_summary_table(result: SimilarityResult) -> None:
    """Display summary table with statistics by format."""
    # Show stats even if no similar groups found (to show all processed files)
    if not result.signatures:
        return

    stats_by_format = _collect_format_statistics(result)

    # Create summary table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Format", style="cyan")
    table.add_column("# Files", justify="right")
    table.add_column("Groups Found", justify="right")
    table.add_column("Lines", justify="right")

    # Populate table and calculate totals
    total_files, total_groups, total_lines = _populate_summary_table(table, stats_by_format)

    # Add totals row
    table.add_row(
        "[bold]Totals[/bold]",
        f"[bold]{len(total_files)}[/bold]",
        f"[bold]{total_groups}[/bold]",
        f"[bold]{total_lines}[/bold]",
        end_section=True,
    )

    console.print("\n")
    console.print(table)


def _handle_output(
    result: SimilarityResult,
    output_format: str,
    output_path: Path | None,
    log_level: str,
    show_diff: bool = False,
) -> None:
    """Handle formatting and outputting results."""
    if output_format.lower() == "sarif":
        output_text = format_as_sarif(result, pretty=True)
        _write_output(output_text, output_path)
    else:  # console
        display_similar_groups(result, show_diff=show_diff)
        display_failed_files(result, show_details=(log_level.upper() == "DEBUG"))
        display_summary_table(result)
        console.print()


def _check_result_errors(result: SimilarityResult, output_format: str) -> None:
    """Check for errors in the result and exit if necessary."""
    if result.success_count == 0 and result.failure_count > 0:
        if output_format.lower() == "console":
            console.print("[bold red]Error:[/bold red] Failed to parse any files")
            display_failed_files(result, show_details=True)
        sys.exit(1)


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
@click.option(
    "--threshold",
    type=float,
    default=None,
    help="Filter threshold for similarity (default: uses ruleset-specific thresholds)",
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
    type=click.Choice(["console", "sarif"], case_sensitive=False),
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
    "--diff",
    is_flag=True,
    default=False,
    help="Show side-by-side diff between the first two files in each similar group (console format only)",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Exit with error code 1 if any similar blocks are detected",
)
def detect(
    ctx: click.Context,
    path: Path,
    threshold: float | None,
    min_lines: int,
    output_format: str,
    output: Path | None,
    ignore: str,
    ignore_files: str,
    diff: bool,
    strict: bool,
) -> None:
    """Detect similar code regions of files in a path."""
    log_level = ctx.obj["log_level"]
    ruleset = ctx.obj["ruleset"]

    _configure_settings(
        ruleset,
        threshold,
        min_lines,
        ignore,
        ignore_files,
    )
    result = _run_pipeline_with_ui(path, output_format)
    _check_result_errors(result, output_format)
    _handle_output(result, output_format, output, log_level, diff)

    # Exit with error code 1 in strict mode if any similar blocks are detected
    if strict and result.similar_groups:
        sys.exit(1)
