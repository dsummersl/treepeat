"""CLI interface for tssim."""

import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from tssim.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from tssim.diff import display_diff
from tssim.formatters import format_as_sarif
from tssim.models.similarity import Region, RegionSignature, SimilarRegionGroup, SimilarityResult
from tssim.pipeline.pipeline import run_pipeline

console = Console()


def setup_logging(log_level: str) -> None:
    """Configure logging with rich handler."""
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


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


def display_summary_table(result: SimilarityResult) -> None:
    """Display summary table with statistics by format."""
    # Show stats even if no similar groups found (to show all processed files)
    if not result.signatures:
        return

    stats_by_format = _collect_format_statistics(result)

    # Create summary table
    table = Table(title="\n[bold cyan]Summary[/bold cyan]", show_header=True, header_style="bold")
    table.add_column("Format", style="cyan")
    table.add_column("# Files", justify="right")
    table.add_column("Groups Found", justify="right")
    table.add_column("Lines", justify="right")

    # Sort by format name
    for language in sorted(stats_by_format.keys()):
        stats = stats_by_format[language]
        table.add_row(
            language,
            str(len(stats["files"])),  # type: ignore[arg-type]
            str(stats["groups"]),
            str(stats["lines"]),
        )

    console.print(table)


def _write_output(text: str, output_path: Path | None) -> None:
    """Write output text to file or stdout."""
    if output_path:
        output_path.write_text(text)
    else:
        print(text)


def _run_pipeline_with_ui(path: Path, output_format: str) -> SimilarityResult:
    """Run the pipeline with appropriate UI feedback based on output format."""
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
    """Handle formatting and outputting results."""
    if output_format.lower() == "sarif":
        output_text = format_as_sarif(result, pretty=True)
        _write_output(output_text, output_path)
    else:  # console
        display_similar_groups(result, show_diff=show_diff)
        display_failed_files(result, show_details=(log_level.upper() == "DEBUG"))
        display_summary_table(result)
        console.print()


def _parse_patterns(pattern_string: str) -> list[str]:
    """Parse comma-separated pattern string into list."""
    return [p.strip() for p in pattern_string.split(",") if p.strip()]


def _print_rule_spec(rule: Any) -> None:
    """Print rule specification."""
    query_preview = rule.query[:60] + "..." if len(rule.query) > 60 else rule.query
    rule_spec = f"languages={','.join(rule.languages)}, action={rule.action.value if rule.action else 'none'}"
    console.print(f"    [dim]{rule_spec}[/dim]")
    console.print(f"    [dim]query: {query_preview}[/dim]\n")


def _print_rulesets(ruleset_name: str) -> None:
    """Print rules in the specified ruleset."""
    from tssim.pipeline.rules_factory import get_ruleset_with_descriptions

    rules_with_descriptions = get_ruleset_with_descriptions(ruleset_name)

    # Display header with ruleset name
    console.print(f"\n[bold blue]Ruleset: {ruleset_name}[/bold blue]\n")

    if not rules_with_descriptions:
        console.print("  [dim]No normalization rules - raw AST comparison[/dim]\n")
        return

    # Display each rule with its description
    console.print(f"[dim]{len(rules_with_descriptions)} rule(s):[/dim]\n")
    for rule, description in rules_with_descriptions:
        console.print(f"  [cyan]•[/cyan] {description}")
        _print_rule_spec(rule)


def _create_rules_settings(ruleset: str) -> RulesSettings:
    """Create RulesSettings."""
    return RulesSettings(ruleset=ruleset)


def _configure_settings(
    ruleset: str,
    threshold: float,
    min_lines: int,
    ignore: str,
    ignore_files: str,
) -> None:
    """Configure pipeline settings."""
    settings = PipelineSettings(
        rules=_create_rules_settings(ruleset),
        shingle=ShingleSettings(),  # Uses default k=3
        minhash=MinHashSettings(),  # Uses default num_perm=128
        lsh=LSHSettings(threshold=threshold, min_lines=min_lines),
        ignore_patterns=_parse_patterns(ignore),
        ignore_file_patterns=_parse_patterns(ignore_files),
    )
    set_settings(settings)


def _check_result_errors(result: SimilarityResult, output_format: str) -> None:
    """Check for errors in the result and exit if necessary."""
    if result.success_count == 0 and result.failure_count > 0:
        if output_format.lower() == "console":
            console.print("[bold red]Error:[/bold red] Failed to parse any files")
            display_failed_files(result, show_details=True)
        sys.exit(1)


@click.group(invoke_without_command=True)
@click.pass_context
@click.argument("path", type=click.Path(exists=True, path_type=Path), required=False)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="WARNING",
    help="Set the logging level",
)
@click.option(
    "--ruleset",
    type=click.Choice(["none", "default", "loose"], case_sensitive=False),
    default="default",
    help="Built-in ruleset profile to use (default: default)",
)
@click.option(
    "--list-ruleset",
    type=click.Choice(["none", "default", "loose"], case_sensitive=False),
    default=None,
    help="List rules in the specified ruleset (none/default/loose)",
)
def main(
    ctx: click.Context,
    path: Path | None,
    log_level: str,
    ruleset: str,
    list_ruleset: str | None,
) -> None:
    """Tree-sitter based similarity detection tool."""
    setup_logging(log_level.upper())

    # Store common options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["ruleset"] = ruleset
    ctx.obj["path"] = path

    # Handle --list-ruleset option
    if list_ruleset is not None:
        _print_rulesets(list_ruleset)
        sys.exit(0)

    # If no subcommand specified but path provided, invoke detect by default
    if ctx.invoked_subcommand is None and path is not None:
        ctx.invoke(detect, path=path)


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
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
    threshold: float,
    min_lines: int,
    output_format: str,
    output: Path | None,
    ignore: str,
    ignore_files: str,
    diff: bool,
    strict: bool,
) -> None:
    """Detect similar code regions (default command)."""
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


def _filter_regions_by_name(
    extracted_regions: list[Any],
    region: str,
    parsed_file: Any,
    rule_engine: Any,
) -> list[Any]:
    """Filter regions by name and show error if not found."""
    filtered = [r for r in extracted_regions if r.region.region_name == region]
    if not filtered:
        from tssim.pipeline.region_extraction import extract_all_regions

        console.print(f"[bold red]Error:[/bold red] Region '{region}' not found")
        console.print("\nAvailable regions:")
        all_regions = extract_all_regions([parsed_file], rule_engine, include_sections=False)
        for r in all_regions:
            console.print(f"  - {r.region.region_name} ({r.region.region_type})")
        sys.exit(1)
    return filtered


def _display_region_shingles(
    extracted_region: Any, shingler: Any, source: bytes
) -> None:
    """Display shingles for a single region."""
    region_info = extracted_region.region
    console.print(
        f"\n[bold cyan]Region:[/bold cyan] {region_info.region_name} ({region_info.region_type})"
    )
    console.print(f"[dim]File: {region_info.path}[/dim]")
    console.print(f"[dim]Lines: {region_info.start_line}-{region_info.end_line}[/dim]")

    # Reset identifiers for consistent output
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(extracted_region.node, region_info.language)

    # Extract shingles
    shingled_region = shingler.shingle_region(extracted_region, source)

    console.print(f"\n[bold green]Shingles ({len(shingled_region.shingles.shingles)}):[/bold green]")
    for i, shingle in enumerate(shingled_region.shingles.shingles, 1):
        console.print(f"  {i:3d}. {shingle}")

    console.print()


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
@click.option(
    "--region",
    type=str,
    default=None,
    help="Specific region name to show tree-sitter output for (e.g., function name). If not specified, shows all regions.",
)
def treesitter(
    ctx: click.Context,
    file: Path,
    region: str | None,
) -> None:
    """Show file after tree-sitter normalization rules are applied.

    This command shows how the code looks after all normalization rules
    are applied, which is what gets compared during similarity detection.
    """
    from tssim.config import get_settings
    from tssim.pipeline.parse import parse_file
    from tssim.pipeline.region_extraction import extract_all_regions
    from tssim.pipeline.shingle import ASTShingler
    from tssim.pipeline.rules_factory import build_rule_engine

    ruleset = ctx.obj["ruleset"]
    _configure_settings(ruleset, 1.0, 5, "", "**/.*ignore")

    # Parse the file
    try:
        parsed_file = parse_file(file)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to parse file: {e}")
        sys.exit(1)

    # Extract and filter regions
    rule_engine = build_rule_engine(get_settings())
    extracted_regions = extract_all_regions([parsed_file], rule_engine, include_sections=False)

    if not extracted_regions:
        console.print("[yellow]No regions found in file[/yellow]")
        sys.exit(0)

    if region:
        extracted_regions = _filter_regions_by_name(
            extracted_regions, region, parsed_file, rule_engine
        )

    # Display shingles for each region
    shingler = ASTShingler(rule_engine=rule_engine, k=3)
    for extracted_region in extracted_regions:
        _display_region_shingles(extracted_region, shingler, parsed_file.source)


if __name__ == "__main__":
    main()
