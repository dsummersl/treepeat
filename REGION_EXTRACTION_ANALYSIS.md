# Region Extraction: Explicit Rules vs. Bottom-Up Auto-Chunking

## Question
Can we replace explicit `RegionExtractionRule` classes with a language-agnostic depth-first approach that automatically discovers chunks based on `min_lines`?

## Current Approach (Explicit Regions)

### How it Works
```
1. Define queries per language (e.g., "(function_definition) @region")
2. Execute queries to find ALL matching nodes (recursive, finds nested matches)
3. Extract each matched node as a region
4. Filter by min_lines
5. Shingle each region independently
6. Compare via MinHash/LSH
```

### Example: Python Class
```python
class UserService:           # Lines 1-50
    def __init__(self):      # Lines 2-5 (4 lines)
        pass

    def get_user(self):      # Lines 7-15 (9 lines)
        # implementation
        pass

    def save_user(self):     # Lines 17-50 (34 lines)
        # implementation
        pass
```

**Extracted Regions:**
- Class: `UserService` (lines 1-50, type="class")
- Method: `get_user` (lines 7-15, type="method")  [__init__ filtered, too small]
- Method: `save_user` (lines 17-50, type="method")

**Strengths:**
- ✅ Semantic labels ("similar classes", "similar methods")
- ✅ Targeted extraction (only meaningful constructs)
- ✅ Clear boundaries aligned with language constructs
- ✅ User-friendly results

**Weaknesses:**
- ❌ Requires per-language RegionExtractionRule definitions
- ❌ Manual maintenance for each language
- ❌ May miss non-traditional similarities
- ❌ Rigid structure

---

## Proposed Approach (Bottom-Up Auto-Chunking)

### Algorithm Sketch

```python
def extract_chunks_bottom_up(root: Node, min_lines: int) -> list[Node]:
    """
    Find the SMALLEST nodes that still meet min_lines.
    These are the 'atomic' comparable units.
    """
    chunks = []

    def traverse(node: Node) -> bool:
        """
        Returns True if this node should be considered a chunk.
        """
        node_lines = node.end_point[0] - node.start_point[0] + 1

        # Too small to be a chunk
        if node_lines < min_lines:
            return False

        # Check if any child is large enough to be its own chunk
        has_large_children = False
        for child in node.children:
            if traverse(child):  # Child is a chunk
                has_large_children = True

        # If no children are large enough, this is a "leaf" chunk
        if not has_large_children:
            chunks.append(node)
            return True

        # Otherwise, we've already processed children, don't add this node
        return False

    traverse(root)
    return chunks
```

### Same Example: Python Class

**Auto-Extracted Chunks (min_lines=5):**
1. `get_user` method (lines 7-15, 9 lines) - leaf chunk
2. `save_user` method (lines 17-50, 34 lines) - leaf chunk

**Note:** The class itself (lines 1-50) is NOT extracted because it HAS large children.

**If `get_user` were smaller (3 lines):**
- `get_user` wouldn't be a chunk (too small)
- `__init__` wouldn't be a chunk (too small)
- `save_user` would still be a chunk (34 lines, no large children)
- The ENTIRE class might become a chunk (has no large children anymore)

### Compositional Bottom-Up

```python
def compare_hierarchically(chunks: list[Node]) -> SimilarityGroups:
    """
    1. Compare all leaf chunks using MinHash/LSH
    2. Group similar chunks
    3. For groups, check if their parents are similar
    4. Recursively build up hierarchy of matches
    """
    # Phase 1: Find similar leaf chunks
    leaf_matches = find_similar_chunks(chunks)

    # Phase 2: Compositional grouping
    # If chunk A matches chunk A', and chunk B matches B',
    # and A and B share a parent P, and A' and B' share parent P',
    # then compare P to P' (they might be similar at a higher level)

    hierarchical_groups = build_hierarchy(leaf_matches)
    return hierarchical_groups
```

---

## Comparison

| Aspect | Explicit Rules | Bottom-Up Auto |
|--------|---------------|----------------|
| **Language Agnostic** | ❌ Need rules per language | ✅ Works for any tree-sitter grammar |
| **Semantic Labels** | ✅ "similar functions" | ❌ "similar 23-line blocks" |
| **Maintenance** | ❌ Manual rule updates | ✅ Zero maintenance |
| **Flexibility** | ❌ Fixed to predefined constructs | ✅ Adapts to code structure |
| **User Experience** | ✅ Clear, meaningful results | ⚠️ Harder to explain |
| **Boundary Quality** | ✅ Aligned with language semantics | ⚠️ May create arbitrary splits |
| **Handles Edge Cases** | ⚠️ May miss unusual patterns | ✅ Handles anything |
| **Comparison Scope** | Fixed (functions, classes, etc.) | Dynamic (whatever meets min_lines) |

---

## Hybrid Approach?

Could we support BOTH modes?

```python
class RegionExtractionMode(Enum):
    EXPLICIT = "explicit"      # Current approach
    AUTO_BOTTOM_UP = "auto"    # Proposed approach
    HYBRID = "hybrid"          # Both!
```

**Hybrid Strategy:**
1. Use explicit rules when available (Python, JS, etc.)
2. Fall back to auto-chunking for unsupported languages
3. OR: Use auto-chunking but label chunks based on node type

---

## Key Questions to Explore

1. **Granularity Control**:
   - Would auto-chunking create too many small chunks?
   - Or too few large chunks?

2. **Hierarchical Comparison**:
   - How do we efficiently compare at multiple levels?
   - Current system compares each region independently

3. **User Communication**:
   - How do we explain "similar blocks" without semantic labels?
   - "Similar 23-line statement_block" vs "similar functions"?

4. **Performance**:
   - Would auto-chunking create more regions to compare?
   - Could filtering be more effective?

5. **Overlap Handling**:
   - Current system can extract overlapping regions (class + its methods)
   - Auto-chunking would create disjoint chunks
   - Is this better or worse?

---

## Implementation Path

If we wanted to prototype this:

1. **Create `AutoChunkExtractor`** alongside current `extract_regions()`
2. **Add configuration option** to switch modes
3. **Test on real codebases** and compare results
4. **Evaluate**:
   - Do we find more/fewer similarities?
   - Are results more/less actionable?
   - Is performance better/worse?

---

## Bottom Line

Your intuition is **architecturally sound**. The bottom-up approach would:
- ✅ Eliminate language-specific region rules
- ✅ Work universally for any tree-sitter grammar
- ✅ Adapt to unusual code structures
- ✅ Reduce maintenance burden

The main trade-off is **semantic clarity** - users understand "similar functions" better than "similar 47-line blocks".

**Recommendation**: Prototype both approaches and compare on real codebases. The auto-chunking might reveal similarities that explicit rules miss, or it might create too many spurious matches. Empirical testing would answer this definitively.
