# Code similarity detection

A tool for detecting code duplication and similarity across codebases.

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
