"""CLI interface for whorl."""

import logging
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from whorl.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from whorl.diff import display_diff
from whorl.formatters import format_as_sarif
from whorl.models.similarity import Region, RegionSignature, SimilarRegionGroup, SimilarityResult
from whorl.pipeline.pipeline import run_pipeline

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


def _write_output(text: str, output_path: Path | None) -> None:
    """Write output text to file or stdout."""
    if output_path:
        output_path.write_text(text)
    else:
        print(text)


def _run_pipeline_with_ui(path: Path, output_format: str) -> SimilarityResult:
    """Run the pipeline with appropriate UI feedback based on output format."""
    if output_format.lower() == "console":
        from whorl.config import get_settings
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


def _build_ruleset_header(ruleset_name: str, language_filter: str | None) -> str:
    """Build the ruleset header with optional language filter."""
    header = f"Ruleset: {ruleset_name}"
    if language_filter:
        header += f" (language: {language_filter})"
    return header


def _print_empty_ruleset_message(language_filter: str | None) -> None:
    """Print message when no rules are found."""
    if language_filter:
        console.print(f"  [dim]No rules found for language '{language_filter}'[/dim]\n")
    else:
        console.print("  [dim]No normalization rules - raw AST comparison[/dim]\n")


def _filter_rules_by_language(
    rules: list[tuple[Any, str]], language_filter: str | None
) -> list[tuple[Any, str]]:
    """Filter rules by language if specified."""
    if not language_filter:
        return rules
    return [(rule, desc) for rule, desc in rules if language_filter in rule.languages]


def _print_rulesets(ruleset_name: str, language_filter: str | None = None) -> None:
    """Print rules in the specified ruleset, optionally filtered by language."""
    from whorl.pipeline.rules_factory import get_ruleset_with_descriptions

    rules_with_descriptions = get_ruleset_with_descriptions(ruleset_name)
    rules_with_descriptions = _filter_rules_by_language(rules_with_descriptions, language_filter)

    header = _build_ruleset_header(ruleset_name, language_filter)
    console.print(f"\n[bold blue]{header}[/bold blue]\n")

    if not rules_with_descriptions:
        _print_empty_ruleset_message(language_filter)
        return

    console.print(f"[dim]{len(rules_with_descriptions)} rule(s):[/dim]\n")
    for rule, description in rules_with_descriptions:
        console.print(f"  [cyan]•[/cyan] {description}")
        _print_rule_spec(rule)


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


def _check_result_errors(result: SimilarityResult, output_format: str) -> None:
    """Check for errors in the result and exit if necessary."""
    if result.success_count == 0 and result.failure_count > 0:
        if output_format.lower() == "console":
            console.print("[bold red]Error:[/bold red] Failed to parse any files")
            display_failed_files(result, show_details=True)
        sys.exit(1)


@click.group()
@click.pass_context
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
def main(
    ctx: click.Context,
    log_level: str,
    ruleset: str,
) -> None:
    """Tree-sitter based similarity detection tool."""
    setup_logging(log_level.upper())

    # Store common options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["ruleset"] = ruleset


@main.command()
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
        from whorl.pipeline.region_extraction import extract_all_regions

        console.print(f"[bold red]Error:[/bold red] Region '{region}' not found")
        console.print("\nAvailable regions:")
        all_regions = extract_all_regions([parsed_file], rule_engine)
        for r in all_regions:
            console.print(f"  - {r.region.region_name} ({r.region.region_type})")
        sys.exit(1)
    return filtered


def _extract_tokens_from_file(parsed_file: Any, shingler: Any) -> dict[int, list[str]]:
    """Extract individual normalized tokens from a file's AST, grouped by line number.

    Returns a dictionary mapping line numbers (1-indexed) to lists of token representations.
    """
    from whorl.models.normalization import SkipNode

    tokens_by_line: dict[int, list[str]] = {}
    source = parsed_file.source
    language = parsed_file.language
    root = parsed_file.root_node

    # Reset identifiers for consistent output
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(root, language, source)

    def traverse(node: Any) -> None:
        """Traverse AST and collect normalized token representations by line."""
        try:
            node_repr = shingler._get_node_representation(node, language, source, root)
            # Get the line number for this node (1-indexed)
            line_num = node.start_point[0] + 1
            if line_num not in tokens_by_line:
                tokens_by_line[line_num] = []
            tokens_by_line[line_num].append(str(node_repr))
        except SkipNode:
            # Skip this node but continue with children
            pass

        # Recursively traverse children
        for child in node.children:
            traverse(child)

    traverse(root)
    return tokens_by_line


def _process_leaf_node(
    node: Any, node_repr: Any, line_parts: dict[int, list[tuple[int, str]]]
) -> None:
    """Process a leaf node and add its representation to line_parts."""
    line_num = node.start_point[0] + 1
    col_num = node.start_point[1]

    # Use the normalized representation
    if node_repr.value:
        text = f"{node_repr.name}:{node_repr.value}"
    else:
        text = node_repr.name

    if line_num not in line_parts:
        line_parts[line_num] = []
    line_parts[line_num].append((col_num, text))


def _process_internal_node(
    node: Any, shingler: Any, language: str, source: bytes, root: Any,
    line_parts: dict[int, list[tuple[int, str]]]
) -> None:
    """Process an internal node where all children were skipped."""
    from whorl.models.normalization import SkipNode

    line_num = node.start_point[0] + 1
    col_num = node.start_point[1]
    try:
        node_repr = shingler._get_node_representation(node, language, source, root)
        if line_num not in line_parts:
            line_parts[line_num] = []
        line_parts[line_num].append((col_num, f"<{node_repr.name}>"))
    except SkipNode:
        pass


def _reconstruct_lines_from_parts(line_parts: dict[int, list[tuple[int, str]]]) -> dict[int, str]:
    """Reconstruct source lines from collected node parts."""
    reconstructed_lines: dict[int, str] = {}
    for line_num, parts in sorted(line_parts.items()):
        sorted_parts = sorted(parts, key=lambda x: x[0])
        reconstructed_lines[line_num] = " ".join(text for _, text in sorted_parts)
    return reconstructed_lines


def _reconstruct_transformed_source(parsed_file: Any, shingler: Any) -> dict[int, str]:
    """Reconstruct source code from normalized AST nodes, grouped by line number.

    Returns a dictionary mapping line numbers (1-indexed) to reconstructed source lines.
    """
    from whorl.models.normalization import SkipNode

    source = parsed_file.source
    language = parsed_file.language
    root = parsed_file.root_node

    # Reset identifiers for consistent output
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(root, language, source)

    # Track which source bytes have been covered by nodes
    line_parts: dict[int, list[tuple[int, str]]] = {}

    def traverse(node: Any, parent_skipped: bool = False) -> bool:
        """Traverse AST and reconstruct source from normalized nodes."""
        node_skipped = False
        try:
            node_repr = shingler._get_node_representation(node, language, source, root)
            if len(node.children) == 0:
                _process_leaf_node(node, node_repr, line_parts)
        except SkipNode:
            node_skipped = True

        # Process children
        any_child_processed = False
        for child in node.children:
            child_skipped = traverse(child, node_skipped)
            if not child_skipped:
                any_child_processed = True

        # For nodes with children that weren't skipped, add structural info if needed
        if not node_skipped and not any_child_processed and len(node.children) > 0:
            _process_internal_node(node, shingler, language, source, root, line_parts)

        return node_skipped

    traverse(root)
    return _reconstruct_lines_from_parts(line_parts)


def _truncate_if_needed(text: str, max_width: int) -> str:
    """Truncate text if it exceeds max_width."""
    if len(text) > max_width - 1:
        return text[:max_width - 4] + "..."
    return text


def _print_side_by_side_header(file_path: Any, language: str, col_width: int, show_transformed: bool = False) -> None:
    """Print the header for side-by-side display."""
    console.print("\n[bold]TreeSitter Side-by-Side View:[/bold]")
    console.print(f"[bold cyan]File:[/bold cyan] {file_path}")
    console.print(f"[dim]Language: {language}[/dim]")
    header_left = "Original Source"
    header_right = "Transformed Source" if show_transformed else "TreeSitter Tokens"
    console.print(f"\n[bold]{header_left:<{col_width}}[/bold]│[bold]{header_right:<{col_width}}[/bold]")
    console.print(f"{'-' * col_width}│{'-' * col_width}")


def _display_transformed_view(
    source_lines: list[str], parsed_file: Any, shingler: Any, col_width: int
) -> None:
    """Display transformed source view."""
    transformed_lines = _reconstruct_transformed_source(parsed_file, shingler)

    for line_num in range(1, len(source_lines) + 1):
        source_line = source_lines[line_num - 1] if line_num <= len(source_lines) else ""
        left_line = _truncate_if_needed(source_line, col_width)
        transformed_line = transformed_lines.get(line_num, "")
        right_line = _truncate_if_needed(transformed_line, col_width)
        console.print(f"{left_line:<{col_width}}│{right_line:<{col_width}}")

    console.print(f"\n[dim]Total source lines: {len(source_lines)}[/dim]")
    console.print(f"[dim]Transformed lines: {len(transformed_lines)}[/dim]")


def _display_tokens_view(
    source_lines: list[str], parsed_file: Any, shingler: Any, col_width: int
) -> None:
    """Display tree-sitter tokens view."""
    tokens_by_line = _extract_tokens_from_file(parsed_file, shingler)
    total_tokens = 0

    for line_num in range(1, len(source_lines) + 1):
        source_line = source_lines[line_num - 1] if line_num <= len(source_lines) else ""
        left_line = _truncate_if_needed(source_line, col_width)
        line_tokens = tokens_by_line.get(line_num, [])
        total_tokens += len(line_tokens)
        tokens_str = " ".join(line_tokens)
        right_line = _truncate_if_needed(tokens_str, col_width)
        console.print(f"{left_line:<{col_width}}│{right_line:<{col_width}}")

    console.print(f"\n[dim]Total source lines: {len(source_lines)}[/dim]")
    console.print(f"[dim]Total tokens: {total_tokens}[/dim]")


def _display_file_side_by_side(parsed_file: Any, shingler: Any, show_transformed: bool = False) -> None:
    """Display original file content side-by-side with treesitter tokens or transformed source."""
    try:
        source_lines = parsed_file.source.decode("utf-8", errors="ignore").splitlines()
    except Exception:
        console.print("[bold red]Error:[/bold red] Failed to decode file content")
        return

    col_width = console.width // 2
    _print_side_by_side_header(parsed_file.path, parsed_file.language, col_width, show_transformed)

    if show_transformed:
        _display_transformed_view(source_lines, parsed_file, shingler, col_width)
    else:
        _display_tokens_view(source_lines, parsed_file, shingler, col_width)

    console.print()


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--transformed",
    is_flag=True,
    default=False,
    help="Show transformed source instead of tree-sitter tokens on the right side",
)
@click.pass_context
def treesitter(
    ctx: click.Context,
    file: Path,
    transformed: bool,
) -> None:
    """Show file with side-by-side view of original source and tree-sitter tokens.

    This command displays the original source code on the left and the normalized
    tree-sitter token representations on the right (or transformed source with --transformed),
    showing how the code is transformed during similarity detection.
    """
    from whorl.config import get_settings
    from whorl.pipeline.parse import parse_file
    from whorl.pipeline.shingle import ASTShingler
    from whorl.pipeline.rules_factory import build_rule_engine

    ruleset = ctx.obj["ruleset"]
    _configure_settings(ruleset, 1.0, 5, "", "**/.*ignore")

    # Parse the file
    try:
        parsed_file = parse_file(file)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Failed to parse file: {e}")
        sys.exit(1)

    # Build rule engine and shingler
    rule_engine = build_rule_engine(get_settings())
    shingler = ASTShingler(rule_engine=rule_engine, k=3)

    # Display side-by-side view
    _display_file_side_by_side(parsed_file, shingler, show_transformed=transformed)


@main.command(name="list-ruleset")
@click.argument(
    "ruleset",
    type=click.Choice(["none", "default", "loose"], case_sensitive=False),
)
@click.option(
    "--language",
    "-l",
    type=str,
    default=None,
    help="Filter rules by language (e.g., python, java, javascript)",
)
def list_ruleset(ruleset: str, language: str | None) -> None:
    """List rules in the specified ruleset.

    Display all rules in a given ruleset (none/default/loose), optionally
    filtered by a specific programming language.
    """
    _print_rulesets(ruleset, language)


if __name__ == "__main__":
    main()
