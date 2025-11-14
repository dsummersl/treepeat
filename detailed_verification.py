#!/usr/bin/env python3
"""Detailed verification of benchmark findings."""

import json
from pathlib import Path


def read_file_lines(filepath, start, end):
    """Read specific lines from a file."""
    try:
        with open(filepath) as f:
            lines = f.readlines()
            return ''.join(lines[start-1:end])
    except Exception as e:
        return f"Error reading file: {e}"


def verify_jscpd_findings():
    """Verify each jscpd finding by reading the actual code."""
    base = Path('/home/user/tssim/testing-framework/codebases/flask')

    jscpd_file = Path('/home/user/tssim/testing-framework/results/flask_jscpd/jscpd-report.json')
    with open(jscpd_file) as f:
        data = json.load(f)

    print("=" * 80)
    print("VERIFYING JSCPD FINDINGS (Gold Standard)")
    print("=" * 80)

    for i, dup in enumerate(data['duplicates'], 1):
        first = dup['firstFile']
        second = dup['secondFile']

        file1 = base / first['name'].split('codebases/flask/')[-1]
        file2 = base / second['name'].split('codebases/flask/')[-1]

        print(f"\n{'=' * 80}")
        print(f"Finding #{i}: {dup['lines']} lines")
        print(f"{'=' * 80}")
        print(f"\nRegion 1: {file1.relative_to(base)}:{first['start']}-{first['end']}")
        print("-" * 40)
        code1 = read_file_lines(file1, first['start'], first['end'])
        print(code1)

        print(f"\nRegion 2: {file2.relative_to(base)}:{second['start']}-{second['end']}")
        print("-" * 40)
        code2 = read_file_lines(file2, second['start'], second['end'])
        print(code2)

        # Calculate exact character similarity
        if code1 == code2:
            print(f"\n✓ IDENTICAL (100%)")
        else:
            # Simple similarity check
            lines1 = code1.strip().split('\n')
            lines2 = code2.strip().split('\n')
            matching = sum(1 for l1, l2 in zip(lines1, lines2) if l1.strip() == l2.strip())
            total = max(len(lines1), len(lines2))
            similarity = matching / total if total > 0 else 0
            print(f"\n≈ SIMILAR ({similarity:.1%} line-wise match)")


def verify_tssim_sample():
    """Verify a sample of tssim's findings."""
    base = Path('/home/user/tssim/testing-framework/codebases/flask')

    tssim_file = Path('/home/user/tssim/testing-framework/results/flask_tssim/tssim-report.json')
    with open(tssim_file) as f:
        data = json.load(f)

    print("\n\n" + "=" * 80)
    print("VERIFYING TSSIM FINDINGS (Sample of high-similarity matches)")
    print("=" * 80)

    # Show a few high-similarity examples
    high_sim = [p for p in data['similar_pairs'] if p['similarity'] >= 0.99][:3]

    for i, pair in enumerate(high_sim, 1):
        r1 = pair['region1']
        r2 = pair['region2']

        file1 = base / r1['file_path'].split('codebases/flask/')[-1]
        file2 = base / r2['file_path'].split('codebases/flask/')[-1]

        print(f"\n{'=' * 80}")
        print(f"tssim Finding #{i}: {pair['similarity']:.1%} similarity")
        print(f"Type: {r1['region_type']}, Names: {r1['name']} vs {r2['name']}")
        print(f"{'=' * 80}")
        print(f"\nRegion 1: {file1.relative_to(base)}:{r1['start_line']}-{r1['end_line']}")
        print("-" * 40)
        code1 = read_file_lines(file1, r1['start_line'], r1['end_line'])
        print(code1[:500] + "..." if len(code1) > 500 else code1)

        print(f"\nRegion 2: {file2.relative_to(base)}:{r2['start_line']}-{r2['end_line']}")
        print("-" * 40)
        code2 = read_file_lines(file2, r2['start_line'], r2['end_line'])
        print(code2[:500] + "..." if len(code2) > 500 else code2)


if __name__ == '__main__':
    verify_jscpd_findings()
    verify_tssim_sample()
