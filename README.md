# Code similarity detection

A tool for detecting code duplication and similarity across codebases.

## Dev setup

```bash
make setup
make test
```

## Testing & Benchmarks

tssim includes a comprehensive testing framework for comparing duplication detection tools against real-world codebases.

### Running Benchmarks

```bash
# Run all benchmark tests
make benchmark

# Compare results across tools
make benchmark-compare
```

### What's Included

The testing framework (`testing-framework/`) provides:
- **Comparative benchmarking** against industry-standard tools (jscpd, etc.)
- **Real-world testing** on popular open-source codebases (FastAPI, Django, Flask, React)
- **Standardized reporting** in CSV and JSON formats
- **Extensible framework** for adding new codebases and tools

### Quick Start

```bash
cd testing-framework

# Run all tests
python3 run_tests.py

# Compare tool results
python3 compare_results.py tools

# Add a new codebase to test
python3 add_codebase.py add myproject https://github.com/user/repo.git TypeScript "Description"
```

### Documentation

- [Testing Framework README](testing-framework/README.md) - Complete usage guide
- [Analysis](testing-framework/ANALYSIS.md) - Detailed benchmark analysis
- [Summary](testing-framework/SUMMARY.md) - Results overview

## ADRs

Architecture Decision Records live in docs/adr.
