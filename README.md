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
cd testing-framework/duplication-testing

# Run all tests
python3 simple_test_runner.py

# Compare tool results
python3 compare_results.py tools

# Add a new codebase to test
python3 add_codebase.py add myproject https://github.com/user/repo.git TypeScript "Description"
```

### Documentation

- [Testing Framework README](testing-framework/README.md) - Complete usage guide
- [Integration Guide](testing-framework/INTEGRATION.md) - Integration details
- [Analysis](testing-framework/duplication-testing/ANALYSIS.md) - Detailed benchmark analysis
- [Summary](testing-framework/duplication-testing/SUMMARY.md) - Results overview

### CI Integration

The testing framework runs automatically:
- **Weekly** on Sundays (scheduled)
- **Manually** via GitHub Actions workflow dispatch
- **On pull requests** that modify the testing framework

Results are uploaded as artifacts and retained for 90 days.

## ADRs

Architecture Decision Records live in docs/adr.
