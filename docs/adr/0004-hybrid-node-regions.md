# 4. Hybrid Node Region Selection

Date: 2025-11-20

## Status

Accepted

## Context

When detecting code clones, we need to determine which treesitter nodes to compare. There are three fundamental approaches to selecting these "regions":

- **Static AST Node Selection** Define a fixed set of node types per language (e.g., always extract `function_definition`, `class_definition`).
- **Line-by-Line Sliding Windows** Create fixed-stride windows (e.g., lines 1-20, 11-30, 21-40) across files.
- **Pure Statistical Discovery** Traverse the entire AST and select nodes based on statistical properties (size, frequency).

Although we may know before hand which nodes are important for a specific language, we likely won't be able to determine this for all 150+ syntaxes supported by treesitter.

## Decision

Use a hybrid approach that combines explicit rule-based extraction with statistical auto-discovery:

For each parsed file:
1. Apply explicit region rules (semantic extraction) if they are defined.
2. Apply statistical auto-chunking (adaptive fallback)
3. Deduplicate overlapping regions (and accept explicit filters from the user)

### Semantic extraction

These are already handled by the system as explicity language rules in the `treepeat/languages` module.

- **Semantic precision**: Explicit rules capture well-understood constructs with proper labels
- **Adaptive coverage**: Statistical discovery handles edge cases, unknown languages, and unconventional code
- **Minimal configuration**: Works out-of-box with sensible defaults while allowing customization

### Statistical Auto-Chunking

Discover regions bottom-up:

1. **Traverse AST depth-first** to find all nodes
2. **Identify leaf chunks**: Nodes meeting minimum size threshold with NO qualifying children
3. **Filter statistically**:
   - Remove node types appearing >40% of time (too granular)
   - Keep only nodes in top 70% by size (avoid tiny fragments)
   - Exclude nodes <5% or >90% of file size

### Deduplication

When explicit and statistical regions overlap at the same location:
- **Prefer explicit regions** - they carry semantic labels
- **Keep statistical regions** only where no explicit region exists

## Consequences

- **Complexity**: Two extraction paths plus deduplication adds implementation complexity
- **Tuning required**: Statistical thresholds (40% frequency, 70% percentile) need empirical validation per codebase
- **Potential gaps**: Regions between explicit and statistical thresholds may be missed
- **Performance overhead**: Full AST traversal for statistical discovery on large files
