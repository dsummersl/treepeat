#!/usr/bin/env python3
"""
Analyze why jscpd and hash_detector missed the 100% similar duplicates found by tssim
"""

import json

# Load tssim report
with open('/home/user/tssim/testing-framework/results/flask_tssim/tssim-report.json', 'r') as f:
    tssim_data = json.load(f)

# Load jscpd report
with open('/home/user/tssim/testing-framework/results/flask_jscpd/jscpd-report.json', 'r') as f:
    jscpd_data = json.load(f)

print("=" * 80)
print("100% SIMILARITY CASES IN TSSIM")
print("=" * 80)
print()

perfect_matches = [dup for dup in tssim_data['similar_pairs'] if dup['similarity'] == 1.0]

print(f"Found {len(perfect_matches)} cases with 100% similarity\n")

for i, dup in enumerate(perfect_matches, 1):
    file1 = dup['region1']['file_path'].replace('/home/user/tssim/testing-framework/codebases/flask/', '')
    file2 = dup['region2']['file_path'].replace('/home/user/tssim/testing-framework/codebases/flask/', '')
    name1 = dup['region1']['name']
    name2 = dup['region2']['name']
    region_type = dup['region1']['region_type']
    lines1 = f"{dup['region1']['start_line']}-{dup['region1']['end_line']}"
    lines2 = f"{dup['region2']['start_line']}-{dup['region2']['end_line']}"
    size1 = dup['region1']['end_line'] - dup['region1']['start_line'] + 1
    size2 = dup['region2']['end_line'] - dup['region2']['start_line'] + 1

    print(f"{i}. {region_type.upper()}: '{name1}' vs '{name2}'")
    print(f"   File 1: {file1}:{lines1} ({size1} lines)")
    print(f"   File 2: {file2}:{lines2} ({size2} lines)")
    print(f"   Same file: {'YES' if file1 == file2 else 'NO'}")
    print()

print("=" * 80)
print("JSCPD CONFIGURATION ANALYSIS")
print("=" * 80)
print()

# Check jscpd defaults
print("jscpd likely uses these defaults:")
print("  - Minimum tokens: 50 (default)")
print("  - Minimum lines: 5 (default)")
print("  - Files scanned: All Python files")
print()

print("jscpd found only 5 duplicates:")
for i, dup in enumerate(jscpd_data['duplicates'], 1):
    print(f"  {i}. {dup['lines']} lines, {dup['tokens']} tokens (estimated)")
    print(f"     {dup['firstFile']['name'].replace('codebases/flask/', '')}")

print()
print("=" * 80)
print("SIZE COMPARISON")
print("=" * 80)
print()

print("Let's look at the size of 100% matches that jscpd missed:\n")

for i, dup in enumerate(perfect_matches, 1):
    size = dup['region1']['end_line'] - dup['region1']['start_line'] + 1
    name1 = dup['region1']['name']
    name2 = dup['region2']['name']

    print(f"{i}. {name1} vs {name2}: {size} lines")
