#!/usr/bin/env python3
"""Analyze tssim duplicates to categorize false positives and valid duplicates."""

import json
from pathlib import Path

# Load the tssim report
with open('/home/user/tssim/testing-framework/results/flask_tssim/tssim-report.json') as f:
    report = json.load(f)

# Categories for analysis
categories = {
    'containment': [],  # Class containing its own method
    'valid_intentional': [],  # Intentional duplicates (like send_static_file)
    'valid_refactor_candidates': [],  # Real duplicates that could be refactored
    'test_helpers': [],  # Similar test setup code
    'decorator_patterns': [],  # Similar decorator/wrapper patterns
    'property_accessors': [],  # Similar property getter/setter patterns
    'lines_vs_function': [],  # Line region vs function containing it
    'other': []
}

def is_containment_issue(pair):
    """Check if one region contains the other (same file, overlapping lines)."""
    r1 = pair['region1']
    r2 = pair['region2']

    if r1['file_path'] != r2['file_path']:
        return False

    # Check if one region contains the other
    r1_range = set(range(r1['start_line'], r1['end_line'] + 1))
    r2_range = set(range(r2['start_line'], r2['end_line'] + 1))

    # If one is fully contained in the other, it's a containment issue
    if r1_range.issubset(r2_range) or r2_range.issubset(r1_range):
        return True

    return False

def is_test_code(pair):
    """Check if both regions are in test files."""
    return ('test_' in pair['region1']['file_path'] and
            'test_' in pair['region2']['file_path'])

def is_lines_region(pair):
    """Check if either region is a 'lines' type region."""
    return (pair['region1']['region_type'] == 'lines' or
            pair['region2']['region_type'] == 'lines')

def get_function_name_pattern(name):
    """Extract the base pattern from a function name."""
    # Remove common suffixes/prefixes
    patterns = [
        ('test_', ''),
        ('_with_template', ''),
        ('_with_name', ''),
        ('_with_name_and_template', ''),
        ('add_', ''),
        ('app_', ''),
    ]
    base = name
    for prefix, _ in patterns:
        if prefix in base:
            base = base.replace(prefix, '')
    return base

# Analyze each pair
for i, pair in enumerate(report['similar_pairs'], 1):
    r1 = pair['region1']
    r2 = pair['region2']
    similarity = pair['similarity']

    # Check for containment issues
    if is_containment_issue(pair):
        categories['containment'].append({
            'index': i,
            'pair': pair,
            'reason': f"{r1['region_type']} vs {r2['region_type']} in same file with overlap"
        })
    # Check for lines regions
    elif is_lines_region(pair):
        categories['lines_vs_function'].append({
            'index': i,
            'pair': pair,
            'reason': 'Line-based region comparison'
        })
    # Check for known intentional duplicates
    elif 'send_static_file' in r1['name'] or 'send_static_file' in r2['name']:
        categories['valid_intentional'].append({
            'index': i,
            'pair': pair,
            'reason': 'Known intentional duplicate (documented in code)'
        })
    elif '_make_timedelta' in r1['name'] or '_make_timedelta' in r2['name']:
        categories['valid_intentional'].append({
            'index': i,
            'pair': pair,
            'reason': 'Utility function duplicated across modules'
        })
    # Check for test helper patterns
    elif is_test_code(pair) and (r1['name'] == r2['name'] or
                                   ('Index' in r1['name'] and 'Index' in r2['name']) or
                                   ('Module' in r1['name'] and 'Module' in r2['name']) or
                                   ('index' in r1['name'] and 'index' in r2['name'])):
        categories['test_helpers'].append({
            'index': i,
            'pair': pair,
            'reason': 'Similar test fixture setup'
        })
    # Check for decorator/template patterns
    elif (('template_filter' in r1['name'] and 'template_test' in r2['name']) or
          ('template_test' in r1['name'] and 'template_filter' in r2['name']) or
          ('template_filter' in r1['name'] and 'template_filter' in r2['name']) or
          ('template_test' in r1['name'] and 'template_test' in r2['name']) or
          ('template_global' in r1['name'] and 'template_test' in r2['name']) or
          ('context_processor' in r1['name'] and 'url_value_preprocessor' in r2['name'])):
        categories['decorator_patterns'].append({
            'index': i,
            'pair': pair,
            'reason': 'Similar decorator/registration pattern (template filters, tests, globals)'
        })
    # Check for property accessor patterns
    elif (('max_content_length' in r1['name'] or 'max_form_memory_size' in r1['name']) and
          ('max_content_length' in r2['name'] or 'max_form_memory_size' in r2['name'])):
        categories['property_accessors'].append({
            'index': i,
            'pair': pair,
            'reason': 'Similar property accessor pattern'
        })
    elif (('get_cookie_' in r1['name'] or 'get_cookie_' in r2['name'])):
        categories['property_accessors'].append({
            'index': i,
            'pair': pair,
            'reason': 'Similar cookie getter pattern'
        })
    # Valid refactoring candidates
    elif similarity >= 0.95 and not is_test_code(pair):
        categories['valid_refactor_candidates'].append({
            'index': i,
            'pair': pair,
            'reason': f'High similarity ({similarity}) in production code'
        })
    else:
        categories['other'].append({
            'index': i,
            'pair': pair,
            'reason': 'Needs manual review'
        })

# Print summary
print("=" * 80)
print("TSSIM DUPLICATE ANALYSIS SUMMARY")
print("=" * 80)
print(f"\nTotal duplicates found: {len(report['similar_pairs'])}")
print()

for category, items in categories.items():
    if items:
        print(f"\n{category.upper().replace('_', ' ')} ({len(items)} duplicates):")
        print("-" * 80)
        for item in items:
            pair = item['pair']
            r1 = pair['region1']
            r2 = pair['region2']
            print(f"  #{item['index']} [Similarity: {pair['similarity']:.3f}]")
            print(f"    {r1['file_path'].split('flask/')[-1]}:{r1['start_line']}-{r1['end_line']}")
            print(f"    {r1['region_type']}: {r1['name']}")
            print(f"    vs")
            print(f"    {r2['file_path'].split('flask/')[-1]}:{r2['start_line']}-{r2['end_line']}")
            print(f"    {r2['region_type']}: {r2['name']}")
            print(f"    Reason: {item['reason']}")
            print()

# Print statistics
print("\n" + "=" * 80)
print("STATISTICS")
print("=" * 80)
total = len(report['similar_pairs'])
invalid = len(categories['containment']) + len(categories['lines_vs_function'])
valid_intentional = len(categories['valid_intentional'])
patterns = (len(categories['decorator_patterns']) +
           len(categories['property_accessors']) +
           len(categories['test_helpers']))
refactor = len(categories['valid_refactor_candidates'])
other = len(categories['other'])

print(f"\nInvalid (false positives): {invalid} ({invalid/total*100:.1f}%)")
print(f"  - Containment issues: {len(categories['containment'])}")
print(f"  - Lines vs function: {len(categories['lines_vs_function'])}")
print(f"\nValid but intentional: {valid_intentional} ({valid_intentional/total*100:.1f}%)")
print(f"\nPattern-based (likely valid): {patterns} ({patterns/total*100:.1f}%)")
print(f"  - Decorator patterns: {len(categories['decorator_patterns'])}")
print(f"  - Property accessors: {len(categories['property_accessors'])}")
print(f"  - Test helpers: {len(categories['test_helpers'])}")
print(f"\nRefactor candidates: {refactor} ({refactor/total*100:.1f}%)")
print(f"\nOther (needs review): {other} ({other/total*100:.1f}%)")

print("\n" + "=" * 80)
print("PROBLEM SET CATEGORIES")
print("=" * 80)
print("""
1. CONTAINMENT BUGS: Regions that contain each other shouldn't be compared
   - Class vs its own method
   - Function vs line range containing it

2. LINE REGION MATCHING: Generic line-based regions create noisy matches

3. INTENTIONAL DUPLICATES: Some code is intentionally duplicated
   - Utility functions in different modules
   - Pattern implementations (Flask app vs Blueprint)

4. PATTERN-BASED CODE: Similar code structure is expected
   - Decorator registration patterns (template_filter, template_test, etc.)
   - Property accessor patterns (get_cookie_*, max_*)
   - Test fixture setup code
""")
