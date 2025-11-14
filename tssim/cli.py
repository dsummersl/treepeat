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
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from tssim.diff import display_diff
from tssim.formatters import format_as_sarif
from tssim.models.similarity import RegionSignature, SimilarRegionGroup, SimilarityResult
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


def _display_group(group: SimilarRegionGroup, show_diff: bool = False) -> None:
    """Display a single similarity group with optional diff."""
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
        console.print()


def _parse_patterns(pattern_string: str) -> list[str]:
    """Parse comma-separated pattern string into list."""
    return [p.strip() for p in pattern_string.split(",") if p.strip()]


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
        # Format the rule specification
        params_str = (
            f",{','.join(f'{k}={v}' for k,v in rule.params.items())}"
            if rule.params
            else ""
        )
        node_patterns = "|".join(rule.node_patterns)
        rule_spec = (
            f"{rule.language}:{rule.operation.value}:nodes="
            f"{node_patterns}{params_str}"
        )
        console.print(f"  [cyan]•[/cyan] {description}")
        console.print(f"    [dim]{rule_spec}[/dim]\n")


def _create_rules_settings(rules: str, rules_file: str, ruleset: str) -> RulesSettings:
    """Create RulesSettings with proper None handling."""
    return RulesSettings(
        ruleset=ruleset,
        rules=rules or None,
        rules_file=rules_file or None,
    )


def _configure_settings(
    rules: str,
    rules_file: str,
    ruleset: str,
    threshold: float,
    min_lines: int,
    ignore: str,
    ignore_files: str,
) -> None:
    """Configure pipeline settings."""
    settings = PipelineSettings(
        rules=_create_rules_settings(rules, rules_file, ruleset),
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
    "--list-ruleset",
    type=click.Choice(["none", "default", "loose"], case_sensitive=False),
    default=None,
    help="List rules in the specified ruleset (none/default/loose)",
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
def main(
    path: Path | None,
    log_level: str,
    rules: str,
    rules_file: str,
    ruleset: str,
    list_ruleset: str | None,
    threshold: float,
    min_lines: int,
    output_format: str,
    output: Path | None,
    ignore: str,
    ignore_files: str,
    diff: bool,
    strict: bool,
) -> None:
    """Analyze code similarity in a file or directory."""
    setup_logging(log_level.upper())

    # Handle --list-ruleset option
    if list_ruleset is not None:
        _print_rulesets(list_ruleset)
        sys.exit(0)

    if path is None:
        console.print("[bold red]Error:[/bold red] PATH is required")
        console.print("Try 'tssim --help' for more information.")
        sys.exit(1)

    _configure_settings(
        rules,
        rules_file,
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


if __name__ == "__main__":
    main()
