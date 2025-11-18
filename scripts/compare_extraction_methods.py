#!/usr/bin/env python3
"""Compare explicit region extraction vs auto-chunking.

This script runs both extraction methods on the same files and
compares the results to help evaluate the trade-offs.
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from covey.pipeline.parse import parse_files
from covey.pipeline.region_extraction import extract_regions
from covey.pipeline.auto_chunk_extraction import extract_chunks
from covey.pipeline.statistical_chunk_extraction import extract_chunks_statistical
from covey.pipeline.rules.engine import RuleEngine, build_default_rules
from covey.models.ast import ParseResult


def compare_extractions(file_paths: list[str], min_lines: int = 5):
    """Compare explicit and auto-chunking extraction on given files."""
    console = Console()

    # Parse files
    console.print("\n[bold cyan]Parsing files...[/bold cyan]")
    paths = [Path(p) for p in file_paths]
    parse_result = ParseResult()
    parse_files(paths, parse_result)

    if parse_result.failed_files:
        console.print("[red]Failed to parse some files:[/red]")
        for path, error in parse_result.failed_files.items():
            console.print(f"  {path}: {error}")
        return

    console.print(f"[green]Successfully parsed {len(parse_result.parsed_files)} file(s)[/green]\n")

    # Initialize rule engine for explicit extraction
    rules = [rule for rule, _ in build_default_rules()]
    rule_engine = RuleEngine(rules)

    # Process each file
    for parsed_file in parse_result.parsed_files:
        console.print(f"\n[bold magenta]{'=' * 80}[/bold magenta]")
        console.print(f"[bold magenta]File: {parsed_file.path}[/bold magenta]")
        console.print(f"[bold magenta]Language: {parsed_file.language}[/bold magenta]")
        console.print(f"[bold magenta]{'=' * 80}[/bold magenta]\n")

        # Extract using explicit rules
        console.print("[bold cyan]Explicit Region Extraction (Current Approach):[/bold cyan]")
        explicit_regions = extract_regions(parsed_file, rule_engine)

        # Filter by min_lines for fair comparison
        explicit_regions = [
            r for r in explicit_regions
            if r.region.end_line - r.region.start_line + 1 >= min_lines
        ]

        if explicit_regions:
            table = Table(title="Explicit Regions", show_header=True)
            table.add_column("Type", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Lines", style="yellow")
            table.add_column("Range", style="blue")

            for region in explicit_regions:
                lines = region.region.end_line - region.region.start_line + 1
                table.add_row(
                    region.region.region_type,
                    region.region.region_name,
                    str(lines),
                    f"{region.region.start_line}-{region.region.end_line}",
                )

            console.print(table)
            console.print(f"Total: {len(explicit_regions)} regions\n")
        else:
            console.print("[yellow]No explicit regions found (or language not supported)[/yellow]\n")

        # Extract using auto-chunking (naive)
        console.print("[bold cyan]Auto-Chunk Extraction (Naive - No Filtering):[/bold cyan]")
        auto_regions = extract_chunks(parsed_file, min_lines=min_lines)

        if auto_regions:
            table = Table(title="Naive Auto-Chunks", show_header=True)
            table.add_column("Node Type", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Lines", style="yellow")
            table.add_column("Range", style="blue")

            for region in auto_regions[:15]:  # Show first 15
                lines = region.region.end_line - region.region.start_line + 1
                table.add_row(
                    region.region.region_type,
                    region.region.region_name[:50],  # Truncate long names
                    str(lines),
                    f"{region.region.start_line}-{region.region.end_line}",
                )

            console.print(table)
            if len(auto_regions) > 15:
                console.print(f"[dim](showing 15 of {len(auto_regions)} chunks)[/dim]")
            console.print(f"Total: {len(auto_regions)} chunks\n")
        else:
            console.print("[yellow]No chunks found[/yellow]\n")

        # Extract using statistical filtering
        console.print("[bold cyan]Statistical Auto-Chunk Extraction (With Smart Filtering):[/bold cyan]")
        stat_regions = extract_chunks_statistical(parsed_file, min_lines=min_lines)

        if stat_regions:
            table = Table(title="Statistical Auto-Chunks", show_header=True)
            table.add_column("Node Type", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Lines", style="yellow")
            table.add_column("Range", style="blue")

            for region in stat_regions:
                lines = region.region.end_line - region.region.start_line + 1
                table.add_row(
                    region.region.region_type,
                    region.region.region_name[:50],
                    str(lines),
                    f"{region.region.start_line}-{region.region.end_line}",
                )

            console.print(table)
            console.print(f"Total: {len(stat_regions)} chunks\n")
        else:
            console.print("[yellow]No chunks found[/yellow]\n")

        # Comparison summary
        console.print("[bold cyan]Three-Way Comparison:[/bold cyan]")

        comparison = Table(show_header=True)
        comparison.add_column("Metric", style="cyan")
        comparison.add_column("Explicit", style="green")
        comparison.add_column("Naive Auto", style="yellow")
        comparison.add_column("Statistical", style="magenta")

        comparison.add_row(
            "Region Count",
            str(len(explicit_regions)),
            str(len(auto_regions)),
            str(len(stat_regions)),
        )

        # Count unique region types
        explicit_types = set(r.region.region_type for r in explicit_regions)
        auto_types = set(r.region.region_type for r in auto_regions)
        stat_types = set(r.region.region_type for r in stat_regions)

        comparison.add_row(
            "Unique Types",
            str(len(explicit_types)),
            str(len(auto_types)),
            str(len(stat_types)),
        )

        console.print(comparison)

        # Show types found by each method
        if explicit_types or auto_types or stat_types:
            console.print("\n[bold cyan]Node Types Found:[/bold cyan]")

            # Count by type for each method
            from collections import Counter
            explicit_counts = Counter(r.region.region_type for r in explicit_regions)
            auto_counts = Counter(r.region.region_type for r in auto_regions)
            stat_counts = Counter(r.region.region_type for r in stat_regions)

            all_types = explicit_types | auto_types | stat_types

            type_table = Table(show_header=True)
            type_table.add_column("Type", style="cyan")
            type_table.add_column("Explicit", style="green")
            type_table.add_column("Naive", style="yellow")
            type_table.add_column("Statistical", style="magenta")

            for node_type in sorted(all_types):
                type_table.add_row(
                    node_type,
                    str(explicit_counts.get(node_type, 0)) if node_type in explicit_types else "-",
                    str(auto_counts.get(node_type, 0)) if node_type in auto_types else "-",
                    str(stat_counts.get(node_type, 0)) if node_type in stat_types else "-",
                )

            console.print(type_table)

        console.print()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare explicit region extraction vs auto-chunking"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Files to analyze",
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=5,
        help="Minimum lines for a region/chunk (default: 5)",
    )

    args = parser.parse_args()

    compare_extractions(args.files, min_lines=args.min_lines)


if __name__ == "__main__":
    main()
