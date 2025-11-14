#!/usr/bin/env python3
"""Analyze and compare benchmark results from different tools."""

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple


def normalize_path(path: str) -> str:
    """Normalize file paths for comparison."""
    # Remove the base directory prefix
    if 'codebases/flask/' in path:
        return path.split('codebases/flask/')[-1]
    return path


def region_key(file1: str, start1: int, end1: int, file2: str, start2: int, end2: int) -> Tuple:
    """Create a normalized key for comparing regions (order-independent)."""
    f1 = normalize_path(file1)
    f2 = normalize_path(file2)
    # Ensure consistent ordering
    if (f1, start1, end1) <= (f2, start2, end2):
        return (f1, start1, end1, f2, start2, end2)
    else:
        return (f2, start2, end2, f1, start1, end1)


def parse_jscpd_report(jscpd_file: Path) -> List[Dict]:
    """Parse jscpd report and extract duplicate pairs."""
    with open(jscpd_file) as f:
        data = json.load(f)

    duplicates = []
    for dup in data.get('duplicates', []):
        first = dup['firstFile']
        second = dup['secondFile']
        duplicates.append({
            'file1': normalize_path(first['name']),
            'start1': first['start'],
            'end1': first['end'],
            'file2': normalize_path(second['name']),
            'start2': second['start'],
            'end2': second['end'],
            'lines': dup['lines'],
            'key': region_key(first['name'], first['start'], first['end'],
                            second['name'], second['start'], second['end'])
        })
    return duplicates


def parse_tssim_report(tssim_file: Path) -> List[Dict]:
    """Parse tssim report and extract duplicate pairs."""
    with open(tssim_file) as f:
        data = json.load(f)

    duplicates = []
    for pair in data.get('similar_pairs', []):
        r1 = pair['region1']
        r2 = pair['region2']
        duplicates.append({
            'file1': normalize_path(r1['file_path']),
            'start1': r1['start_line'],
            'end1': r1['end_line'],
            'file2': normalize_path(r2['file_path']),
            'start2': r2['start_line'],
            'end2': r2['end_line'],
            'similarity': pair['similarity'],
            'name1': r1.get('name', ''),
            'name2': r2.get('name', ''),
            'type1': r1.get('region_type', ''),
            'type2': r2.get('region_type', ''),
            'key': region_key(r1['file_path'], r1['start_line'], r1['end_line'],
                            r2['file_path'], r2['start_line'], r2['end_line'])
        })
    return duplicates


def regions_overlap(dup1: Dict, dup2: Dict) -> bool:
    """Check if two duplicate pairs represent overlapping or similar regions."""
    # Check if files match
    if dup1['file1'] != dup2['file1'] or dup1['file2'] != dup2['file2']:
        # Try reversed comparison
        if dup1['file1'] != dup2['file2'] or dup1['file2'] != dup2['file1']:
            return False

    # Check if line ranges overlap or are very close
    def ranges_close(start1, end1, start2, end2, tolerance=5):
        """Check if two ranges overlap or are within tolerance."""
        return not (end1 + tolerance < start2 or end2 + tolerance < start1)

    # Try both file orderings
    if dup1['file1'] == dup2['file1'] and dup1['file2'] == dup2['file2']:
        return (ranges_close(dup1['start1'], dup1['end1'], dup2['start1'], dup2['end1']) and
                ranges_close(dup1['start2'], dup1['end2'], dup2['start2'], dup2['end2']))
    elif dup1['file1'] == dup2['file2'] and dup1['file2'] == dup2['file1']:
        return (ranges_close(dup1['start1'], dup1['end1'], dup2['start2'], dup2['end2']) and
                ranges_close(dup1['start2'], dup1['end2'], dup2['start1'], dup2['end1']))

    return False


def main():
    base_dir = Path('/home/user/tssim/testing-framework/results')

    jscpd_file = base_dir / 'flask_jscpd' / 'jscpd-report.json'
    tssim_file = base_dir / 'flask_tssim' / 'tssim-report.json'

    print("=" * 80)
    print("BENCHMARK ANALYSIS: jscpd (gold standard) vs tssim")
    print("=" * 80)

    jscpd_dups = parse_jscpd_report(jscpd_file)
    tssim_dups = parse_tssim_report(tssim_file)

    print(f"\nTotal duplicates found:")
    print(f"  jscpd (gold standard): {len(jscpd_dups)}")
    print(f"  tssim:                 {len(tssim_dups)}")

    # Find overlaps
    print("\n" + "=" * 80)
    print("ANALYZING OVERLAPS")
    print("=" * 80)

    jscpd_matched = set()
    tssim_matched = set()
    matches = []

    for i, jscpd_dup in enumerate(jscpd_dups):
        for j, tssim_dup in enumerate(tssim_dups):
            if regions_overlap(jscpd_dup, tssim_dup):
                jscpd_matched.add(i)
                tssim_matched.add(j)
                matches.append((i, j, jscpd_dup, tssim_dup))

    print(f"\nFound {len(matches)} overlapping duplicates between tools")
    print(f"jscpd duplicates matched by tssim: {len(jscpd_matched)}/{len(jscpd_dups)}")
    print(f"tssim duplicates matching jscpd: {len(tssim_matched)}/{len(tssim_dups)}")

    # Show matched duplicates
    if matches:
        print("\n" + "-" * 80)
        print("MATCHED DUPLICATES (found by both tools):")
        print("-" * 80)
        for jscpd_idx, tssim_idx, jscpd_dup, tssim_dup in matches:
            print(f"\nMatch #{len([m for m in matches if m[0] <= jscpd_idx])}:")
            print(f"  jscpd: {jscpd_dup['file1']}:{jscpd_dup['start1']}-{jscpd_dup['end1']} <-> "
                  f"{jscpd_dup['file2']}:{jscpd_dup['start2']}-{jscpd_dup['end2']}")
            print(f"  tssim: {tssim_dup['file1']}:{tssim_dup['start1']}-{tssim_dup['end1']} <-> "
                  f"{tssim_dup['file2']}:{tssim_dup['start2']}-{tssim_dup['end2']}")
            print(f"         similarity={tssim_dup['similarity']:.2%}, "
                  f"type={tssim_dup['type1']}, name={tssim_dup['name1']}")

    # Show jscpd duplicates NOT found by tssim
    jscpd_only = [dup for i, dup in enumerate(jscpd_dups) if i not in jscpd_matched]
    if jscpd_only:
        print("\n" + "-" * 80)
        print(f"JSCPD DUPLICATES NOT FOUND BY TSSIM ({len(jscpd_only)}):")
        print("-" * 80)
        for dup in jscpd_only:
            print(f"\n  {dup['file1']}:{dup['start1']}-{dup['end1']} <-> "
                  f"{dup['file2']}:{dup['start2']}-{dup['end2']}")
            print(f"  ({dup['lines']} lines)")

    # Show tssim duplicates NOT in jscpd
    tssim_only = [dup for i, dup in enumerate(tssim_dups) if i not in tssim_matched]
    if tssim_only:
        print("\n" + "-" * 80)
        print(f"TSSIM DUPLICATES NOT IN JSCPD ({len(tssim_only)}):")
        print("-" * 80)
        print("\nThese need verification - they may be false positives!")

        # Group by similarity threshold
        high_sim = [d for d in tssim_only if d['similarity'] >= 0.95]
        med_sim = [d for d in tssim_only if 0.85 <= d['similarity'] < 0.95]
        low_sim = [d for d in tssim_only if d['similarity'] < 0.85]

        print(f"\nSimilarity breakdown:")
        print(f"  High (>= 95%): {len(high_sim)}")
        print(f"  Med (85-95%):  {len(med_sim)}")
        print(f"  Low (< 85%):   {len(low_sim)}")

        # Show a few examples
        print(f"\nShowing first 10 high-similarity tssim-only duplicates:")
        for i, dup in enumerate(high_sim[:10]):
            print(f"\n  {i+1}. {dup['file1']}:{dup['start1']}-{dup['end1']} <-> "
                  f"{dup['file2']}:{dup['start2']}-{dup['end2']}")
            print(f"     similarity={dup['similarity']:.2%}, type={dup['type1']}, "
                  f"name={dup['name1']} vs {dup['name2']}")


if __name__ == '__main__':
    main()
