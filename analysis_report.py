#!/usr/bin/env python3
"""
Analysis script to compare tssim, jscpd, and hash_detector findings
"""

import json

# Load tssim report
with open('/home/user/tssim/testing-framework/results/flask_tssim/tssim-report.json', 'r') as f:
    tssim_data = json.load(f)

# Load jscpd report
with open('/home/user/tssim/testing-framework/results/flask_jscpd/jscpd-report.json', 'r') as f:
    jscpd_data = json.load(f)

print("=" * 80)
print("COMPARISON ANALYSIS: tssim vs jscpd vs hash_detector")
print("=" * 80)
print()

print(f"Total duplicates found:")
print(f"  - tssim: {len(tssim_data['similar_pairs'])}")
print(f"  - jscpd: {len(jscpd_data['duplicates'])}")
print(f"  - hash_detector: 1")
print()

print("=" * 80)
print("JSCPD DUPLICATES (5 total)")
print("=" * 80)
print()

jscpd_matches = []
for i, dup in enumerate(jscpd_data['duplicates'], 1):
    file1 = dup['firstFile']['name'].replace('codebases/flask/', '')
    file2 = dup['secondFile']['name'].replace('codebases/flask/', '')
    lines1 = f"{dup['firstFile']['start']}-{dup['firstFile']['end']}"
    lines2 = f"{dup['secondFile']['start']}-{dup['secondFile']['end']}"

    print(f"{i}. {file1} [{lines1}] <-> {file2} [{lines2}]")
    print(f"   Lines: {dup['lines']}, Fragment preview: {dup['fragment'][:80]}...")

    jscpd_matches.append({
        'file1': file1,
        'file2': file2,
        'lines1': (dup['firstFile']['start'], dup['firstFile']['end']),
        'lines2': (dup['secondFile']['start'], dup['secondFile']['end'])
    })
    print()

print("=" * 80)
print("CHECKING IF JSCPD DUPLICATES ARE IN TSSIM RESULTS")
print("=" * 80)
print()

def normalize_path(path):
    """Normalize file paths for comparison"""
    return path.replace('codebases/flask/', '').replace('/home/user/tssim/testing-framework/codebases/flask/', '')

def ranges_overlap(range1, range2, tolerance=5):
    """Check if two line ranges overlap with some tolerance"""
    start1, end1 = range1
    start2, end2 = range2
    return (abs(start1 - start2) <= tolerance and abs(end1 - end2) <= tolerance) or \
           (start1 <= end2 and end1 >= start2)

matches_found = []
for i, jscpd_dup in enumerate(jscpd_matches, 1):
    found = False
    for tssim_dup in tssim_data['similar_pairs']:
        tssim_file1 = normalize_path(tssim_dup['region1']['file_path'])
        tssim_file2 = normalize_path(tssim_dup['region2']['file_path'])
        tssim_range1 = (tssim_dup['region1']['start_line'], tssim_dup['region1']['end_line'])
        tssim_range2 = (tssim_dup['region2']['start_line'], tssim_dup['region2']['end_line'])

        # Check if files match (in either order)
        files_match = (
            (jscpd_dup['file1'] in tssim_file1 and jscpd_dup['file2'] in tssim_file2) or
            (jscpd_dup['file1'] in tssim_file2 and jscpd_dup['file2'] in tssim_file1)
        )

        if files_match:
            # Check if line ranges overlap
            if ranges_overlap(jscpd_dup['lines1'], tssim_range1) or \
               ranges_overlap(jscpd_dup['lines1'], tssim_range2):
                found = True
                matches_found.append(i)
                print(f"✓ jscpd duplicate #{i} FOUND in tssim:")
                print(f"  {tssim_dup['region1']['name']} [{tssim_range1[0]}-{tssim_range1[1]}] <-> "
                      f"{tssim_dup['region2']['name']} [{tssim_range2[0]}-{tssim_range2[1]}]")
                print(f"  Similarity: {tssim_dup['similarity']:.2%}")
                print()
                break

    if not found:
        print(f"✗ jscpd duplicate #{i} NOT FOUND in tssim")
        print(f"  {jscpd_dup['file1']} <-> {jscpd_dup['file2']}")
        print()

print("=" * 80)
print(f"SUMMARY: {len(matches_found)}/5 jscpd duplicates matched in tssim")
print("=" * 80)
print()

print("=" * 80)
print("TSSIM DUPLICATES CATEGORIZATION")
print("=" * 80)
print()

# Categorize tssim duplicates
categories = {
    'very_high_similarity': [],  # >= 0.98
    'high_similarity': [],        # 0.90-0.97
    'medium_similarity': [],      # 0.83-0.89
    'test_code': [],             # test files
    'production_code': []        # non-test files
}

for dup in tssim_data['similar_pairs']:
    sim = dup['similarity']
    file1 = normalize_path(dup['region1']['file_path'])
    file2 = normalize_path(dup['region2']['file_path'])

    if sim >= 0.98:
        categories['very_high_similarity'].append(dup)
    elif sim >= 0.90:
        categories['high_similarity'].append(dup)
    elif sim >= 0.83:
        categories['medium_similarity'].append(dup)

    if 'test' in file1 or 'test' in file2:
        categories['test_code'].append(dup)
    else:
        categories['production_code'].append(dup)

print(f"By similarity threshold:")
print(f"  - Very high (≥98%): {len(categories['very_high_similarity'])}")
print(f"  - High (90-97%): {len(categories['high_similarity'])}")
print(f"  - Medium (83-89%): {len(categories['medium_similarity'])}")
print()
print(f"By code type:")
print(f"  - Test code: {len(categories['test_code'])}")
print(f"  - Production code: {len(categories['production_code'])}")
print()

print("=" * 80)
print("VERY HIGH SIMILARITY DUPLICATES (≥98%) - Likely True Positives")
print("=" * 80)
print()

for i, dup in enumerate(categories['very_high_similarity'], 1):
    file1 = normalize_path(dup['region1']['file_path'])
    file2 = normalize_path(dup['region2']['file_path'])
    name1 = dup['region1']['name']
    name2 = dup['region2']['name']
    region_type = dup['region1']['region_type']
    lines1 = f"{dup['region1']['start_line']}-{dup['region1']['end_line']}"
    lines2 = f"{dup['region2']['start_line']}-{dup['region2']['end_line']}"

    print(f"{i}. Similarity: {dup['similarity']:.2%}")
    print(f"   {file1}:{lines1} {region_type} '{name1}'")
    print(f"   {file2}:{lines2} {region_type} '{name2}'")
    print()

print("=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
