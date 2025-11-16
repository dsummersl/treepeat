# Whorl - where branches and flowers spring forth

`whorl` is a CLI tool that detects similar code using treesitter AST analysis with locality-sensitive hashing:
- Find **duplicate** code blocks meaningful to the language (classes/functions), not just lines.
- near-duplicates
- structurally similar text.

Helpers: This is very much an proof of concept - I'm happy with it, but I haven't supported very many languages at present. PRs welcome!

## Usage

### detect

Scan a codebase for similar or duplicate code blocks using tree-sitter AST analysis and locality-sensitive hashing.

Key flags:
- `--ruleset`: Normalization ruleset to use (`none`, `default`, `loose`) - controls how code is normalized before comparison
- `--threshold`: Similarity threshold from 0.0-1.0 (default: 1.0 for exact duplicates)
- `--min-lines`: Minimum number of lines for a match (default: 5)
- `--diff`: Show side-by-side comparisons of similar blocks
- `--format`: Output format - `console` (default) or `sarif` for CI integration

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

### Other sub commands

#### list-ruleset

List all rules in a ruleset, along with their descriptions. Use `--language` to see which rules apply to a specific language.

#### treesitter

Display how whorl normalizes source code into tree-sitter tokens for similarity detection -- helpful for debugging why a certain section of a file might be similar to another. Shows the original source code side-by-side with the normalized token representation.

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
