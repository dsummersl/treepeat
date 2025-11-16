# Code similarity detection

A tool for detecting code duplication and similarity across codebases.

## Usage

### detect

Scan a codebase for similar or duplicate code blocks using tree-sitter AST analysis and locality-sensitive hashing. The `--threshold` option controls similarity matching (0.0-1.0, default 1.0 for exact duplicates), while `--min-lines` sets the minimum block size to consider. Use `--diff` to see side-by-side comparisons of similar blocks, and `--format sarif` to output results in SARIF format for CI integration.

```bash
# Find exact duplicates (default threshold=1.0)
whorl detect /path/to/codebase

# Find near-duplicates with 80% similarity threshold
whorl detect --threshold 0.8 /path/to/codebase

# Show diffs between similar blocks and use loose ruleset
whorl --ruleset loose detect --diff --min-lines 10 /path/to/codebase

# Output results in SARIF format for CI tools
whorl detect --format sarif -o results.sarif /path/to/codebase
```

### treesitter

Display how whorl normalizes source code into tree-sitter tokens for similarity detection. Shows the original source code side-by-side with the normalized token representation, useful for understanding why certain blocks are or aren't detected as similar.

```bash
# View how a file is tokenized
whorl treesitter src/main.py

# Use different normalization ruleset
whorl --ruleset loose treesitter src/main.py

# See raw AST without normalization
whorl --ruleset none treesitter src/main.py
```

## Dev setup

```bash
make setup
make test
```

## Benchmarks

whorl includes a testing framework for comparing duplication detection tools against real-world codebases.

```bash
# Run all benchmark tests
make benchmark

# Compare results across tools
make benchmark-compare
```

## ADRs

Architecture Decision Records live in docs/adr.
