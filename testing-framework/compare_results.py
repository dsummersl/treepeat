#!/usr/bin/env python3
"""
Script to compare duplication detection results across different runs or tools
"""

import json
import sys
from pathlib import Path


def load_report(report_file: Path):
    """Load a JSON report."""
    with open(report_file, 'r') as f:
        return json.load(f)


def compare_tools(report_file: Path):
    """Compare results across different tools."""
    report = load_report(report_file)

    print("="*100)
    print("Tool Comparison Report")
    print(f"Report: {report_file.name}")
    print(f"Timestamp: {report['timestamp']}")
    print("="*100)

    # Group by codebase
    codebases = {}
    for result in report['results']:
        codebase = result['codebase']
        if codebase not in codebases:
            codebases[codebase] = {}
        tool = result['tool']
        codebases[codebase][tool] = result

    # Compare tools for each codebase
    for codebase_name, tools in codebases.items():
        print(f"\n{codebase_name}")
        print("-"*100)

        # Get all unique tools
        tool_names = list(tools.keys())

        # Compare duplicates found
        print("\nDuplicates Found:")
        for tool in tool_names:
            duplicates = tools[tool].get('duplicates_found', 0)
            duration = tools[tool].get('duration', 0)
            status = tools[tool].get('status', 'unknown')
            print(f"  {tool:20s}: {duplicates:8d} duplicates in {duration:6.2f}s ({status})")

        # Show percentage if available
        if 'jscpd' in tools and 'percentage' in tools['jscpd']:
            print(f"\n  jscpd duplication percentage: {tools['jscpd']['percentage']:.1f}%")

        # Agreement analysis
        if len(tool_names) >= 2:
            values = [tools[t].get('duplicates_found', 0) for t in tool_names]
            avg = sum(values) / len(values)
            std_dev = (sum((x - avg) ** 2 for x in values) / len(values)) ** 0.5
            print(f"\n  Average duplicates: {avg:.1f}")
            print(f"  Standard deviation: {std_dev:.1f}")
            print(f"  Variance: {std_dev/avg*100:.1f}%" if avg > 0 else "  Variance: N/A")


def compare_codebases(report_file: Path):
    """Compare duplication rates across codebases."""
    report = load_report(report_file)

    print("="*100)
    print("Codebase Comparison Report")
    print(f"Report: {report_file.name}")
    print("="*100)

    # Group by tool
    tools = {}
    for result in report['results']:
        tool = result['tool']
        if tool not in tools:
            tools[tool] = {}
        codebase = result['codebase']
        tools[tool][codebase] = result

    # For each tool, compare codebases
    for tool_name, codebases in tools.items():
        print(f"\n{tool_name.upper()}")
        print("-"*100)

        # Sort by duplication count
        sorted_codebases = sorted(
            codebases.items(),
            key=lambda x: x[1].get('duplicates_found', 0),
            reverse=True
        )

        print(f"\n{'Codebase':<25} {'Files':<10} {'LOC':<10} {'Duplicates':<15} {'Duration (s)':<15}")
        print("-"*100)

        for codebase_name, result in sorted_codebases:
            files = result.get('files', 0)
            loc = result.get('lines_of_code', 0)
            duplicates = result.get('duplicates_found', 0)
            duration = result.get('duration', 0)

            print(f"{codebase_name:<25} {files:<10} {loc:<10} {duplicates:<15} {duration:<15.2f}")

        # Show percentage if available (for jscpd)
        if tool_name == 'jscpd':
            print("\nDuplication Percentage:")
            sorted_by_pct = sorted(
                [(name, result) for name, result in codebases.items() if 'percentage' in result],
                key=lambda x: x[1]['percentage'],
                reverse=True
            )
            for codebase_name, result in sorted_by_pct:
                pct = result['percentage']
                print(f"  {codebase_name:<25} {pct:>6.1f}%")


def compare_reports(report1: Path, report2: Path):
    """Compare two different reports."""
    r1 = load_report(report1)
    r2 = load_report(report2)

    print("="*100)
    print("Report Comparison")
    print(f"Report 1: {report1.name} ({r1['timestamp']})")
    print(f"Report 2: {report2.name} ({r2['timestamp']})")
    print("="*100)

    # Index by codebase+tool
    def index_results(report):
        index = {}
        for result in report['results']:
            key = (result['codebase'], result['tool'])
            index[key] = result
        return index

    idx1 = index_results(r1)
    idx2 = index_results(r2)

    # Find common keys
    common_keys = set(idx1.keys()) & set(idx2.keys())

    if not common_keys:
        print("\nNo common codebase+tool combinations found")
        return

    print(f"\nComparing {len(common_keys)} common test cases:")
    print("\n{'Codebase':<25} {'Tool':<20} {'Run 1':<15} {'Run 2':<15} {'Difference':<15}")
    print("-"*100)

    for codebase, tool in sorted(common_keys):
        dup1 = idx1[(codebase, tool)].get('duplicates_found', 0)
        dup2 = idx2[(codebase, tool)].get('duplicates_found', 0)
        diff = dup2 - dup1
        diff_str = f"{diff:+d}" if diff != 0 else "same"

        print(f"{codebase:<25} {tool:<20} {dup1:<15} {dup2:<15} {diff_str:<15}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 compare_results.py tools <report.json>          # Compare tools")
        print("  python3 compare_results.py codebases <report.json>      # Compare codebases")
        print("  python3 compare_results.py reports <report1> <report2>  # Compare two reports")
        print("\nExample:")
        print("  python3 compare_results.py tools reports/duplication_report_20251111_234706.json")
        sys.exit(1)

    mode = sys.argv[1]
    reports_dir = Path(__file__).parent / 'reports'

    if mode == 'tools':
        if len(sys.argv) < 3:
            # Find latest report
            reports = sorted(reports_dir.glob('duplication_report_*.json'))
            if not reports:
                print("No reports found")
                sys.exit(1)
            report_file = reports[-1]
            print(f"Using latest report: {report_file.name}\n")
        else:
            report_file = Path(sys.argv[2])

        compare_tools(report_file)

    elif mode == 'codebases':
        if len(sys.argv) < 3:
            reports = sorted(reports_dir.glob('duplication_report_*.json'))
            if not reports:
                print("No reports found")
                sys.exit(1)
            report_file = reports[-1]
            print(f"Using latest report: {report_file.name}\n")
        else:
            report_file = Path(sys.argv[2])

        compare_codebases(report_file)

    elif mode == 'reports':
        if len(sys.argv) < 4:
            print("Error: Need two report files to compare")
            sys.exit(1)

        report1 = Path(sys.argv[2])
        report2 = Path(sys.argv[3])
        compare_reports(report1, report2)

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == '__main__':
    main()
