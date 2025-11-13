#!/usr/bin/env python3
"""
Analyze token counts for the 100% duplicates to understand why jscpd missed them
"""

import tokenize
import io
from pathlib import Path

# The 100% duplicates that jscpd missed
duplicates_to_analyze = [
    {
        'name': 'send_static_file',
        'file': 'src/flask/blueprints.py',
        'start': 82,
        'end': 102,
        'size': 21
    },
    {
        'name': 'test_teardown_request_handler',
        'file': 'tests/test_basic.py',
        'start': 755,
        'end': 770,
        'size': 16
    },
    {
        'name': 'teardown_request1',
        'file': 'tests/test_basic.py',
        'start': 796,
        'end': 805,
        'size': 10
    },
    {
        'name': 'index (test_helpers)',
        'file': 'tests/test_helpers.py',
        'start': 297,
        'end': 304,
        'size': 8
    },
    {
        'name': 'Index class',
        'file': 'tests/test_views.py',
        'start': 29,
        'end': 34,
        'size': 6
    },
    {
        'name': '_make_timedelta',
        'file': 'src/flask/app.py',
        'start': 69,
        'end': 73,
        'size': 5
    },
]

base_path = Path('/home/user/tssim/testing-framework/codebases/flask')

print("=" * 80)
print("TOKEN COUNT ANALYSIS FOR 100% DUPLICATES")
print("=" * 80)
print()

def count_tokens(code: str) -> int:
    """Count Python tokens in a code snippet."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
        # Filter out ENDMARKER, NEWLINE, NL, and INDENT/DEDENT tokens
        # as they're typically not counted by clone detectors
        meaningful_tokens = [
            t for t in tokens
            if t.type not in (tokenize.ENDMARKER, tokenize.NEWLINE,
                             tokenize.NL, tokenize.INDENT, tokenize.DEDENT,
                             tokenize.ENCODING)
        ]
        return len(meaningful_tokens)
    except:
        # Fallback: simple whitespace-based counting
        return len(code.split())

for dup in duplicates_to_analyze:
    file_path = base_path / dup['file']

    with open(file_path, 'r') as f:
        lines = f.readlines()
        # Extract the lines (1-indexed to 0-indexed)
        code_lines = lines[dup['start']-1:dup['end']]
        code = ''.join(code_lines)

    token_count = count_tokens(code)

    print(f"Name: {dup['name']}")
    print(f"File: {dup['file']}:{dup['start']}-{dup['end']}")
    print(f"Lines: {dup['size']}")
    print(f"Tokens: {token_count}")
    print(f"Meets jscpd threshold? Lines: {'✓' if dup['size'] >= 5 else '✗'}, Tokens: {'✓' if token_count >= 50 else '✗'}")

    if dup['size'] >= 5 and token_count < 50:
        print(f"⚠️  LIKELY REASON FOR MISS: Below 50 token threshold!")

    print()

print("=" * 80)
print("JSCPD CONFIGURATION")
print("=" * 80)
print()
print("jscpd is run with:")
print("  --min-lines 5")
print("  --min-tokens 50")
print()
print("Both conditions must be met:")
print("  1. At least 5 lines")
print("  2. At least 50 tokens")
print()
print("If either condition fails, the duplicate is NOT reported.")
