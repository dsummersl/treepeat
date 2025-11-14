# tssim Improvement Analysis After Threshold Update

## Summary of Changes

After merging main branch with `--threshold` updates:

### Performance Improvements
- **Duplicates reported**: 55 → **9** (83.6% reduction)
- **Execution time**: 22.93s → **7.50s** (67.3% faster)
- **All matches at 100% similarity** (threshold=1.0)

### Code Changes
1. `--lsh-threshold` renamed to `--threshold`
2. Default threshold changed from 0.8 to 1.0
3. LSH stage now caps internal threshold at 0.98 (while filter threshold stays at 1.0)

---

## Detailed Analysis of the 9 Duplicates Found

### ✅ Legitimate 100% Duplicates (8 out of 9)

1. **`send_static_file()` function**
   - app.py:303-323 ↔ blueprints.py:82-102
   - Truly identical, even has comment noting it's a duplicate
   - ✅ Valid

2. **`test_teardown_request_handler` vs `test_teardown_request_handler_debug_mode`**
   - test_basic.py:755-770 ↔ test_basic.py:773-788
   - Identical except for function name
   - ✅ Valid (legitimate test duplication)

3. **`teardown_request1` vs `teardown_request2`**
   - test_basic.py:796-805 ↔ test_basic.py:808-817
   - Identical except for function name
   - ✅ Valid

4. **`index()` functions in test_helpers.py**
   - test_helpers.py:297-304 ↔ test_helpers.py:311-318
   - Identical test helper functions
   - ✅ Valid

5. **`Index` class in test_views.py (pair 1)**
   - test_views.py:29-34 ↔ test_views.py:63-68
   - Identical test classes
   - ✅ Valid

6. **`Module` class in test_cli.py**
   - test_cli.py:91-96 ↔ test_cli.py:100-105
   - Identical test classes
   - ✅ Valid

7. **`_make_timedelta()` function**
   - app.py:69-73 ↔ sansio/app.py:52-56
   - Identical helper function
   - ✅ Valid

8. **`Index` class in test_views.py (pair 2)**
   - test_views.py:18-22 ↔ test_views.py:174-178
   - Identical test classes
   - ✅ Valid

### ⚠️ FALSE POSITIVE (1 out of 9)

9. **Import sections NOT 100% similar**
   - app.py:1-68 ↔ sansio/app.py:1-51
   - Reported as 100% similar but imports are very different
   - They share the same TypeVar definitions at the end, but imports differ significantly
   - ❌ **False positive** - should not be 100% similarity

---

## Issue Found: Line-Based Regions Can Be Misleading

The last finding reveals a problem with how tssim handles "lines" regions:

### The Problem

When tssim creates a "lines" region (for code that doesn't fit into functions/classes), it's comparing:
- app.py lines 1-68 (imports + TypeVars)
- sansio/app.py lines 1-51 (different imports + same TypeVars)

These have **very different imports** but share the same TypeVar definitions at the end. The similarity calculation is somehow reporting 100% which is incorrect.

### Expected Behavior

This should report much lower similarity (maybe 30-40%) because:
- Lines 1-40 in app.py: Flask-specific imports
- Lines 1-34 in sansio/app.py: Different (sansio-specific) imports
- Lines 42-48 in sansio/app.py: TypeVar definitions (similar to app.py:59-65)
- Lines 35-41 in sansio/app.py: TYPE_CHECKING block (similar to app.py:51-57)

### Actual Comparison

**app.py imports:**
```python
import collections.abc as cabc
import os
import sys
import typing as t
import weakref
from datetime import timedelta
from inspect import iscoroutinefunction
from itertools import chain
from types import TracebackType
from urllib.parse import quote as _url_quote

import click
from werkzeug.datastructures import Headers
from werkzeug.datastructures import ImmutableDict
# ... many more Flask-specific imports
```

**sansio/app.py imports:**
```python
import logging
import os
import sys
import typing as t
from datetime import timedelta
from itertools import chain

from werkzeug.exceptions import Aborter
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import BadRequestKeyError
# ... different sansio-specific imports
```

These are **NOT the same** - only about 30% of imports overlap.

---

## Overlap with jscpd

Still **ZERO overlap** between jscpd and tssim, which is expected because:
- jscpd finds line-level clones (including partial duplicates within functions)
- tssim finds function/class-level semantic duplicates

### What jscpd found that tssim didn't:
1. TypeVar definitions (lines 18-25 vs 28-35) - partial overlap
2. Form validation logic within functions (blog.py)
3. Constructor signatures (partial overlap)
4. Test patterns (partial overlap)
5. Template filter test code (partial overlap)

### What tssim found that jscpd didn't:
1. Complete duplicate functions (`send_static_file`, `_make_timedelta`)
2. Duplicate test functions (same logic, different names)
3. Duplicate test classes

---

## Comparison: Before vs After Threshold Update

| Metric | Before (threshold=0.8) | After (threshold=1.0) | Change |
|--------|------------------------|----------------------|---------|
| Duplicates | 55 | 9 | -83.6% |
| Execution time | 22.93s | 7.50s | -67.3% |
| False positives | ~0 (all were real) | 1 (11%) | Worse |
| Precision | Very high | Lower | Worse |

### Analysis

The threshold update **improved performance but introduced a precision issue**:

**Pros:**
- Much faster execution (67% improvement)
- Drastically reduced output (easier to review)
- Only reports "very similar" code

**Cons:**
- The "lines" region comparison has a bug that reports 100% when it's not
- Less comprehensive detection (misses 85-99% similar functions)

---

## Recommendations

### 1. Fix the "lines" Region Comparison Bug

The import sections are being reported as 100% similar when they're clearly not. This needs investigation:
- Check how similarity is calculated for "lines" regions
- May be only comparing a subset of lines (the TypeVar section)
- May have normalization issues (ignoring import differences)

### 2. Consider Re-evaluating Default Threshold

A threshold of 1.0 is very strict. Consider:
- **0.95** - Catches near-duplicates that are refactoring opportunities
- **0.90** - Catches similar patterns worth reviewing
- **1.0** - Only catches exact duplicates (current default)

The previous threshold of 0.8 found 55 legitimate duplicates. Many were valuable findings (85-95% similar functions).

### 3. Add Validation Tests

Create tests that verify:
- Known identical functions report 100%
- Known different code reports <50%
- Edge cases like the import sections

### 4. Keep Both Tools in Your Workflow

- **jscpd**: Find copy-pasted code blocks for cleanup
- **tssim**: Find duplicate functions/classes for refactoring

---

## Conclusion

The threshold update to 1.0 was **partially successful**:

✅ **Improved**:
- Much faster (7.5s vs 23s)
- Cleaner output (9 vs 55 matches)
- Focus on near-identical code

❌ **Issues**:
- Found 1 false positive (11% of results)
- Import sections incorrectly reported as 100% similar
- May miss valuable refactoring opportunities (85-95% similar code)

**Recommendation**: Fix the "lines" region bug, then consider a default threshold of 0.95 instead of 1.0 for a better balance between precision and recall.
