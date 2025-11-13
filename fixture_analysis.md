# Test Fixtures Analysis - Comparison with Flask Benchmark Issues

## Summary

Found **5 duplicates** in tests/fixtures, including **1 false positive** that illustrates the containment issue identified in the Flask benchmark.

---

## Issue #1: CONTAINMENT BUG ✓ ILLUSTRATED

**tssim Report:**
- **nested_functions.py:35-49** (class: ClassWithMethods) vs **38-45** (function: method_with_nested)
- Similarity: 82.8%
- Lines: 15 vs 8

**Code Example:**
```python
# Lines 35-49: Class region
class ClassWithMethods:
    """A class with methods."""

    def method_with_nested(self):  # Lines 38-45: Function region
        """A method containing a nested function."""

        def helper():
            """Helper function nested in method."""
            return 42

        return helper() * 2

    def simple_method(self):
        """A simple method without nesting."""
        return 100
```

**Why it's a false positive:**
- The function region (38-45) is **fully contained** within the class region (35-49)
- Lines 38-45 are a **subset** of lines 35-49 in the same file
- This is a parent-child relationship, not code duplication

**Matches Flask issue:**
- ✅ **Yes!** Same as Flask's `TestGreenletContextCopying` class vs `test_greenlet_context_copying` method
- Same as Flask's `DebugFilesKeyError` class vs `__init__` method
- Same containment pattern with overlapping line ranges

---

## Valid Duplicates (4 cases)

### 1. Intentional Cross-File Duplicate
**small_functions.py:9-18** vs **small_functions_b.py:9-18** (98.4% similar)

```python
# Both files have identical large_duplicate() function
def large_duplicate():
    """Large function - should pass min_lines threshold."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = []
    for item in data:
        if item % 2 == 0:
            result.append(item * 2)
        else:
            result.append(item)
    return result
```

**Purpose:** Test fixture to verify tssim detects cross-file duplicates

---

### 2 & 3. Intentional Method Duplicates
**class_with_methods.py**
- **ClassA.method2** (13-19) vs **ClassB.method2** (40-46) - 96.1% similar
- **ClassA.method3** (21-27) vs **ClassB.method3** (48-54) - 94.5% similar

```python
class ClassA:
    def method2(self):
        """Second method - will be duplicated in ClassB."""
        data = [1, 2, 3, 4, 5]
        total = 0
        for item in data:
            total += item
        return total

class ClassB:
    def method2(self):
        """Second method - duplicate of ClassA.method2."""
        data = [1, 2, 3, 4, 5]  # Identical implementation
        total = 0
        for item in data:
            total += item
        return total
```

**Purpose:** Test fixture showing intentional same-file duplicates across classes

---

### 4. Similar Logic Functions
**dataclass2.py:one()** (2-7) vs **dataclass1.py:my_adapted_one()** (21-26) - 93.8% similar

```python
# dataclass2.py
def one():
    """ A funtion that computes the sum of first ten natural numbers """
    total = 0
    for i in range(1, 11):
        total += i
    return total

# dataclass1.py
def my_adapted_one():
    """ A function that computes the sum of first ten natural numbers """
    total = 0
    for i in range(1, 11):
        total += i
    return total
```

**Purpose:** Test fixture showing high-similarity functions with same logic

---

## Issues from Flask Benchmark NOT Illustrated

### ❌ Line Region Matching
**Not present** in fixtures. Would need:
```python
# Example that would trigger it:
# Region 1: file.py:1-50 (lines region - imports/headers)
# Region 2: file.py:1-45 (lines region - similar imports)
```

The fixtures don't have any "lines" type regions that aren't associated with functions/classes.

---

### ❌ Pattern-Based Code (Decorators, Properties, etc.)
**Not present** in fixtures. Flask had:
- `template_filter` vs `template_test` (decorator patterns)
- `get_cookie_domain` vs `get_cookie_samesite` (property accessors)
- HTTP method decorators (`get`, `post`, `put`, etc.)

The fixtures don't include Flask-style decorator registration patterns.

---

### ❌ Test Helper/Fixture Similarity
**Not present** in fixtures. Flask had:
- Multiple identical `Index` class definitions in test files
- Multiple identical `Module` class definitions
- Test setup code with similar structure

The fixtures don't have test-specific patterns with repeated setup code.

---

## Recommendations for Test Fixtures

To better test all identified issues, consider adding:

1. **✅ Already covered:** Containment issue (nested_functions.py)

2. **Missing:** Line region fixtures
   ```python
   # file_with_imports_a.py
   from __future__ import annotations
   import os
   import sys
   # ... many similar imports

   # file_with_imports_b.py
   from __future__ import annotations
   import os
   import sys
   # ... many similar imports
   ```

3. **Missing:** Decorator pattern fixtures
   ```python
   def register_filter(name):
       """Register template filter."""
       def decorator(f):
           filters[name] = f
           return f
       return decorator

   def register_test(name):  # Intentionally similar pattern
       """Register template test."""
       def decorator(f):
           tests[name] = f
           return f
       return decorator
   ```

4. **Missing:** Property accessor fixtures
   ```python
   @property
   def max_content_length(self):
       return self.config.get('MAX_CONTENT_LENGTH')

   @property
   def max_form_memory_size(self):  # Similar pattern
       return self.config.get('MAX_FORM_MEMORY_SIZE')
   ```

---

## Conclusion

**Test fixtures successfully demonstrate 1 of 4 false positive patterns:**
- ✅ **Containment issue** (nested_functions.py)
- ❌ Line region matching
- ❌ Pattern-based code (decorators, properties)
- ❌ Test helper similarity

**All 4 remaining duplicates are intentional** and serve as valid test cases for duplicate detection functionality.
