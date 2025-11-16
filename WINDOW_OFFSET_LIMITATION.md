# Window Matching Offset Limitation

## Issue

When comparing files with insertions/deletions, the window-based matching approach fails to detect similar regions after the insertion/deletion point.

## Root Cause

### How Window Matching Works

1. Creates sliding windows at fixed line numbers in each file (e.g., lines 1-20, 11-30, 21-40, ...)
2. Computes MinHash signatures for each window
3. Uses LSH to find windows with similar signatures
4. Merges overlapping windows to find region boundaries

### The Problem with Line Offsets

When files have insertions/deletions:

1. **Before the insertion**: Windows are aligned and match correctly
   - comprehensive.css[1-20] ↔ comprehensive-slight-mod.css[1-20] ✓

2. **At the insertion point**: Windows contain different content
   - comprehensive.css[41-60] includes lines 58-61 (4 extra lines)
   - comprehensive-slight-mod.css[41-60] is missing those 4 lines
   - Content is genuinely different, windows don't match ✓

3. **After the insertion**: Windows are misaligned by the offset
   - comprehensive.css[62-81] should match comprehensive-slight-mod.css[58-77]
   - But the system compares comprehensive.css[62-81] with comprehensive-slight-mod.css[62-81]
   - These are DIFFERENT content (offset by 4 lines), so they don't match ✗

## Example

```css
/* comprehensive.css */
.button {
    display: inline-block;      /* line 58 - EXTRA */
    padding: 10px 20px;         /* line 59 - EXTRA */
    border: none;               /* line 60 - EXTRA */
    border-radius: var(...);    /* line 61 - EXTRA */
    background-color: var(...); /* line 62 */
    color: white;               /* line 63 */
}
```

```css
/* comprehensive-slight-mod.css */
.button {
    background-color: var(...); /* line 58 (same content as line 62 above) */
    color: white;               /* line 59 (same content as line 63 above) */
}
```

After line 62 in comprehensive.css, the content is identical to comprehensive-slight-mod.css starting from line 58, but windows don't account for this 4-line offset.

## Current Behavior

```
Similar group found (100.0% similar, 2 regions):
  - comprehensive.css [1:50] (50 lines)
    comprehensive-slight-mod.css [1:50] (50 lines)
```

Only detects the first 50 lines (before divergence).

## Expected Behavior

Should detect TWO similar regions:

```
Similar group found (>90% similar, 2 regions):
  - comprehensive.css [1:57] (57 lines)
    comprehensive-slight-mod.css [1:57] (57 lines)

Similar group found (>90% similar, 2 regions):
  - comprehensive.css [62:210] (149 lines)
    comprehensive-slight-mod.css [58:206] (149 lines)
```

## Potential Solutions

### 1. Cross-line-number matching (expensive)
Compare ALL windows against ALL windows, not just windows at the same line numbers.
- **Pros**: Would find all similar regions regardless of offset
- **Cons**: O(n²) complexity, much slower

### 2. Adaptive offset detection
After finding initial matches, detect gaps and try different offsets for remaining windows.
- **Pros**: More efficient than full cross-matching
- **Cons**: Complex to implement, might miss some matches

### 3. Sequence alignment preprocessing
Use diff-like algorithm to align files first, then apply window matching.
- **Pros**: Handles all types of insertions/deletions
- **Cons**: Requires major architectural change

### 4. Denser window stride
Reduce stride (e.g., stride=5 instead of 10) to create more overlapping windows.
- **Pros**: Simple configuration change
- **Cons**: More windows = slower, still won't handle large offsets

## Recommendation

For now, the limitation is documented. Future work could implement solution #2 (adaptive offset detection) as it provides a good balance between accuracy and performance.

The current behavior is correct for the design: it finds regions that match at the same line numbers. The limitation is inherent to the window-based approach when files have structural differences.
