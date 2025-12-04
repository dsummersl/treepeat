"""Detect command - find similar code regions."""

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from treepeat.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
    get_settings,
)
from treepeat.formatters.sarif import format_as_sarif
from treepeat.models.similarity import Region, RegionSignature, SimilarityResult, SimilarRegionGroup
from treepeat.pipeline.pipeline import run_pipeline
from treepeat.pipeline.verbose_metrics import get_verbose_metrics, reset_verbose_metrics

console = Console()


def _parse_patterns(pattern_string: str) -> list[str]:
    """Parse comma-separated pattern string into list."""
    return [p.strip() for p in pattern_string.split(",") if p.strip()]


def _parse_add_region_arg(region_spec: str) -> tuple[str, set[str]]:
    """Parse '<language>:node1,node2,...' for additional regions."""
    import re

    m = re.match(r"^\s*([\w+\-]+)\s*:(.+)$", region_spec)
    if not m:
        raise click.ClickException(
            f"Invalid --add-regions value '{region_spec}'. Expected '<language>:node1,node2,...'"
        )

    language = m.group(1).lower()
    nodes_str = m.group(2)
    node_types = {n.strip() for n in nodes_str.split(",") if n.strip()}
    if not node_types:
        raise click.ClickException(
            f"Invalid --add-regions value '{region_spec}'. Must include at least one node type"
        )
    return language, node_types


def _parse_exclude_region_arg(region_spec: str) -> tuple[str, set[str]]:
    """Parse '<language>:label1,label2,...' for excluding regions."""
    import re

    m = re.match(r"^\s*([\w+\-]+)\s*:(.+)$", region_spec)
    if not m:
        raise click.ClickException(
            f"Invalid --exclude-regions value '{region_spec}'. Expected '<language>:label1,label2,...'"
        )

    language = m.group(1).lower()
    labels_str = m.group(2)
    labels = {l.strip() for l in labels_str.split(",") if l.strip()}
    if not labels:
        raise click.ClickException(
            f"Invalid --exclude-regions value '{region_spec}'. Must include at least one label"
        )
    return language, labels


def _build_additional_region_rules(region_specs: tuple[str, ...]) -> dict[str, set[str]]:
    """Build a language -> node types mapping from repeated --add-regions args."""
    rules: dict[str, set[str]] = {}
    for spec in region_specs:
        lang, nodes = _parse_add_region_arg(spec)
        if lang not in rules:
            rules[lang] = set()
        rules[lang].update(nodes)
    return rules


def _build_excluded_region_rules(region_specs: tuple[str, ...]) -> dict[str, set[str]]:
    """Build a language -> labels mapping from repeated --exclude-regions args."""
    rules: dict[str, set[str]] = {}
    for spec in region_specs:
        lang, labels = _parse_exclude_region_arg(spec)
        if lang not in rules:
            rules[lang] = set()
        rules[lang].update(labels)
    return rules


def _merge_region_mappings(
    base: dict[str, set[str]] | None,
    extra: dict[str, set[str]],
) -> dict[str, set[str]]:
    """Merge two region mapping dictionaries without mutating the originals."""
    merged: dict[str, set[str]] = {lang: set(nodes) for lang, nodes in (base or {}).items()}
    for lang, nodes in extra.items():
        if lang not in merged:
            merged[lang] = set()
        merged[lang].update(nodes)
    return merged


def _create_rules_settings(ruleset: str) -> RulesSettings:
    """Create RulesSettings."""
    return RulesSettings(ruleset=ruleset)


def _configure_settings(
    ruleset: str,
    similarity_percent: float,
    min_lines: int,
    ignore: str,
    ignore_files: str,
    ignore_node_types: str,
) -> None:
    """Configure pipeline settings."""
    lsh_settings = LSHSettings(
        similarity_percent=similarity_percent / 100.0,
        min_lines=min_lines,
        ignore_node_types=_parse_patterns(ignore_node_types),
    )

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
    if output_format.lower() != "console":
        return run_pipeline(path)

    from treepeat.config import get_settings
    settings = get_settings()
    console.print(f"\nRuleset: [cyan]{settings.rules.ruleset}[/cyan]")
    console.print(f"Analyzing: [cyan]{path}[/cyan]\n")
    with console.status("[bold green]Running pipeline..."):
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
    from treepeat.diff import display_diff

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
        display_summary_table(result)
        console.print()


def _check_result_errors(result: SimilarityResult, output_format: str) -> None:
    """Check for errors in the result and exit if necessary."""
    if result.success_count != 0:
        return

    if output_format.lower() == "console":
        console.print("[bold red]Error:[/bold red] Failed to parse any files")

    sys.exit(1)


def _format_language_node_types(
    language: str,
    node_types: set[str],
    excluded: set[str],
) -> str:
    """Format node types for a language with exclusions."""
    sorted_types = ", ".join(sorted(node_types))
    if excluded:
        excluded_str = ", ".join(sorted(excluded))
        return f"{language}: {sorted_types} (excluded: {excluded_str})"
    return f"{language}: {sorted_types}"


def _display_verbose_metrics(elapsed_time: float) -> None:
    """Display verbose metrics about the pipeline run."""
    metrics = get_verbose_metrics()

    if metrics.used_node_types_by_language:
        console.print("\nNodes analyzed by region:")
        for language in sorted(metrics.used_node_types_by_language.keys()):
            node_types = metrics.used_node_types_by_language[language]
            excluded = metrics.excluded_node_types_by_language.get(language, set())
            line = _format_language_node_types(language, node_types, excluded)
            console.print(f"  {line}")

    console.print(f"\nTotal time: [green]{elapsed_time:.2f}s[/green]\n")


@click.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
@click.option(
    "--similarity",
    "-s",
    type=click.IntRange(5, 100),
    default=100,
    help="Percent similarity threshold (default: 100)",
)
@click.option(
    "--min-lines",
    "-ml",
    type=click.IntRange(1),
    default=5,
    help="Minimum number of lines to be considered similar (default: 5)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["console", "sarif"], case_sensitive=False),
    default="console",
    help="Output format (default: console)",
)
@click.option(
    "--add-regions",
    "-ar",
    "add_regions",
    multiple=True,
    default=(),
    help="Add region extraction rules as '<language>:node1,node2,...' (e.g., 'python:function_definition,class_definition')",
)
@click.option(
    "--exclude-regions",
    "-er",
    "exclude_regions",
    multiple=True,
    default=(),
    help="Exclude region extraction rules by label as '<language>:label1,label2,...' (e.g., 'python:function_definition,class_definition')",
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
    "-i",
    type=str,
    default="",
    help="Comma-separated list of glob patterns to ignore files (e.g., '*.test.py,**/node_modules/**')",
)
@click.option(
    "--ignore-files",
    "-if",
    type=str,
    default="**/.*ignore",
    help="Comma-separated list of glob patterns to find ignore files (default: '**/.*ignore')",
)
@click.option(
    "--diff",
    "-d",
    is_flag=True,
    default=False,
    help="Show side-by-side diff between the first two files in each similar group (console format only)",
)
@click.option(
    "--fail",
    is_flag=True,
    default=False,
    help="Exit with error code 1 if any similar blocks are detected",
)
@click.option(
    "--ignore-node-types",
    "-int",
    type=str,
    default="",
    help="Comma-separated list of AST node types to ignore during region extraction (e.g., 'parameters,argument_list')",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show verbose output including timing, ignored nodes, and used node types per language",
)
def detect(
    ctx: click.Context,
    path: Path,
    similarity: float,
    min_lines: int,
    output_format: str,
    output: Path | None,
    ignore: str,
    ignore_files: str,
    diff: bool,
    fail: bool,
    ignore_node_types: str,
    verbose: bool,
    add_regions: tuple[str, ...],
    exclude_regions: tuple[str, ...],
) -> None:
    """Detect similar code regions of files in a path."""
    log_level = ctx.obj["log_level"]
    ruleset = ctx.obj["ruleset"]

    _configure_settings(
        ruleset,
        similarity,
        min_lines,
        ignore,
        ignore_files,
        ignore_node_types,
    )

    settings = get_settings()
    additional_regions = _build_additional_region_rules(add_regions)
    if additional_regions:
        settings.rules.additional_regions = _merge_region_mappings(
            getattr(settings.rules, "additional_regions", {}),
            additional_regions,
        )

    excluded_regions = _build_excluded_region_rules(exclude_regions)
    if excluded_regions:
        settings.rules.excluded_regions = _merge_region_mappings(
            getattr(settings.rules, "excluded_regions", {}),
            excluded_regions,
        )

    # Reset and track timing for verbose output
    reset_verbose_metrics()
    start_time = time.time()

    result = _run_pipeline_with_ui(path, output_format)

    elapsed_time = time.time() - start_time

    _check_result_errors(result, output_format)
    _handle_output(result, output_format, output, log_level, diff)

    # Display verbose metrics if requested
    if verbose and output_format.lower() == "console":
        _display_verbose_metrics(elapsed_time)

    # Exit with error code 1 in strict mode if any similar blocks are detected
    if fail and result.similar_groups:
        sys.exit(1)
