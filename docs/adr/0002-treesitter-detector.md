# 2. Treesitter Detector

Date: 2025-11-02

## Status

Accepted

## Context

Existing "duplicate code" tools (e.g., Simian, PMD CPD, jscpd) primarily detect textual or token-level duplication. They flag identical or near-identical code, but miss semantically or structurally similar regions that differ in identifiers, literal values, or function names.

The tool's purpose:
- clone detection
- highlight refactoring opportunities: functions or blocks that "do the same thing" despite cosmetic differences.
- Work for many languages.
- Detect similar code across languages (e.g., similar algorithms implemented in Java and Python).

## Decision

We will build a new CLI tool called `treepeat`:
- use Tree-sitter ASTs to identify structurally similar code blocks.
- Implement MinHash and Locality Sensitive Hashing (LSH) to efficiently find similar AST subtrees - use the datasketch library.
- For each supported language, create language specific normalization of ASTs to strip away identifiers, literals, and other non-structural elements (eg, imports, comments).
- Output the format in SARIF for easy integration with existing tools (and support some pretty CLI output as well).

The overall processing pipeline would look like:

```sh
### **Summary Pipeline**
Parse → Normalize → Shingles → MinHash → LSH Bucketing
                                              ↓
                                        Candidate pairs
                                              ↓
                                        PQ-Gram (fast filter)
                                              ↓
                                        TED (exact verification)
                                              ↓
                                        SARIF formated results
```

## Consequences

What becomes easier or more difficult to do and any risks introduced by the change that will need to be mitigated.
