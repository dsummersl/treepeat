# 4. Hybrid Node Region Selection

Date: 2025-11-20

## Status

Accepted

## Context

When detecting code clones, we need to determine which parts of source files to compare. There are three fundamental approaches to selecting these "regions":

**1. Static AST Node Selection**
Define a fixed set of node types per language (e.g., always extract `function_definition`, `class_definition`). Simple and predictable, but:
- Misses meaningful code outside defined node types
- Requires manual configuration for each language
- No coverage for unknown languages
- Cannot adapt to codebases with unconventional structures

**2. Line-by-Line Sliding Windows**
Create fixed-stride windows (e.g., lines 1-20, 11-30, 21-40) across files. Language-agnostic and complete coverage, but:
- Ignores semantic boundaries (splits functions mid-body)
- Produces poor-quality matches that cross logical units
- Window alignment breaks when files have insertions/deletions
- High false-positive rate from arbitrary text chunks

**3. Pure Statistical Discovery**
Traverse the entire AST and select nodes based on statistical properties (size, frequency). Adaptive but:
- No semantic understanding of what constitutes a meaningful unit
- May select overly granular nodes (individual statements)
- Inconsistent results across similar files

None of these approaches alone provides both semantic awareness and adaptive coverage.

## Decision

We will use a **hybrid approach** that combines explicit rule-based extraction with statistical auto-discovery:

### Algorithm Overview

```
for each parsed file:
    1. Apply explicit region rules (semantic extraction)
    2. Apply statistical auto-chunking (adaptive fallback)
    3. Deduplicate overlapping regions (prefer explicit)
```

### Step 1: Explicit Region Extraction

Use Tree-sitter queries to extract semantically meaningful regions defined per language:

- **Python**: `function_definition`, `class_definition`
- **JavaScript**: `function_declaration`, `arrow_function`, `class_declaration`, `method_definition`
- **Markdown**: `atx_heading`, `fenced_code_block`

These provide labeled regions with semantic context (type="function", name="calculate_total").

### Step 2: Statistical Auto-Chunking

For code not covered by explicit rules, discover regions bottom-up:

1. **Traverse AST depth-first** to find all nodes
2. **Identify leaf chunks**: Nodes meeting minimum size threshold with NO qualifying children
3. **Filter statistically**:
   - Remove node types appearing >40% of time (too granular)
   - Keep only nodes in top 70% by size (avoid tiny fragments)
   - Exclude nodes <5% or >90% of file size

### Step 3: Deduplication

When explicit and statistical regions overlap at the same location:
- **Prefer explicit regions** - they carry semantic labels
- **Keep statistical regions** only where no explicit region exists

### Heuristic Rationale

The hybrid approach optimizes for:

- **Semantic precision**: Explicit rules capture well-understood constructs with proper labels
- **Adaptive coverage**: Statistical discovery handles edge cases, unknown languages, and unconventional code
- **Minimal configuration**: Works out-of-box with sensible defaults while allowing customization

## Consequences

### Benefits

- **Best of both worlds**: Semantic awareness where available, automatic discovery elsewhere
- **Language extensibility**: New languages get automatic coverage; explicit rules can be added incrementally
- **Consistent quality**: Explicit rules ensure high-quality matches for common patterns; statistical filtering prevents noise
- **Graceful degradation**: Unknown file types still get reasonable region extraction

### Drawbacks

- **Complexity**: Two extraction paths plus deduplication adds implementation complexity
- **Tuning required**: Statistical thresholds (40% frequency, 70% percentile) need empirical validation per codebase
- **Potential gaps**: Regions between explicit and statistical thresholds may be missed
- **Performance overhead**: Full AST traversal for statistical discovery on large files

### Trade-offs vs. Alternatives

| Approach | Semantic Quality | Coverage | Adaptability | Complexity |
|----------|-----------------|----------|--------------|------------|
| Static AST only | High | Low | None | Low |
| Line-by-line windows | None | Complete | None | Low |
| Pure statistical | Medium | High | High | Medium |
| **Hybrid** | **High** | **High** | **Medium** | **High** |

The hybrid approach accepts higher implementation complexity in exchange for both semantic quality and broad coverage—the combination that produces the most useful clone detection results.
