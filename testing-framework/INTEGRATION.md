# Integrating Duplication Testing Framework into tssim

This document explains how to integrate the comprehensive duplication testing framework into the tssim repository.

## Overview

This testing framework allows tssim to be tested against other duplication detection tools on various real-world codebases. It provides:

- **Comprehensive benchmarking** against industry-standard tools (jscpd, PMD CPD, Simian)
- **Multiple test codebases** in various languages (Python, JavaScript, TypeScript)
- **Standardized reporting** for easy comparison
- **Extensibility** to add more tools and codebases

## Benefits for tssim

1. **Validation**: Compare tssim's results against established tools
2. **Performance**: Benchmark execution time on real codebases
3. **Coverage**: Test against diverse code patterns and languages
4. **Regression Testing**: Detect changes in behavior across versions
5. **Documentation**: Demonstrate tssim's capabilities with concrete examples

## Directory Structure

Add the testing framework to tssim as follows:

```
tssim/
├── src/                    # Existing tssim source
├── tests/                  # Existing tssim tests
└── testing-framework/      # NEW: Duplication testing framework
    ├── README.md           # Framework documentation
    ├── SUMMARY.md          # Results summary
    ├── ANALYSIS.md         # Detailed analysis
    ├── simple_test_runner.py  # Main test runner
    ├── add_codebase.py     # Add new codebases
    ├── compare_results.py  # Compare results
    ├── codebases.json      # Codebase configuration
    ├── codebases/          # Downloaded test repositories
    ├── results/            # Raw tool outputs
    ├── reports/            # Comparison reports (CSV, JSON)
    └── tools/              # Tool installations
```

## Installation Steps

### 1. Copy Framework Files

```bash
# From this repository
cp -r tssim-contrib/duplication-testing /path/to/tssim/testing-framework
```

### 2. Install Dependencies

```bash
cd /path/to/tssim/testing-framework

# Install Node.js tools
npm install -g jscpd

# Verify tssim is built
cd ..
npm run build
```

### 3. Configure tssim Tool

The framework needs to be updated to include tssim as one of the detection tools. This is already prepared in the `simple_test_runner.py` file.

## Running Tests

### Basic Usage

```bash
cd /path/to/tssim/testing-framework
python3 simple_test_runner.py
```

This will:
1. Test tssim alongside other tools
2. Generate comparison reports
3. Show how tssim performs relative to other tools

### Compare tssim Against Other Tools

```bash
python3 compare_results.py tools
```

### Add New Test Codebases

```bash
python3 add_codebase.py add myproject https://github.com/user/project.git TypeScript "My project"
```

## Integration with tssim Development

### As a CI/CD Test

Add to `.github/workflows/benchmarks.yml`:

```yaml
name: Benchmarks

on: [push, pull_request]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      - run: npm run build
      - run: cd testing-framework && python3 simple_test_runner.py
      - uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: testing-framework/reports/
```

### As a Documentation Example

Reference results in `README.md`:

```markdown
## Benchmarks

See [testing-framework/SUMMARY.md](testing-framework/SUMMARY.md) for comparative analysis against other duplication detection tools.
```

### As a Regression Test

Run before releases to ensure tssim's behavior is consistent:

```bash
# Run tests
cd testing-framework
python3 simple_test_runner.py

# Compare with previous release
python3 compare_results.py reports reports/baseline.json reports/current.json
```

## Customizing for tssim

### Update tssim Tool Integration

The `simple_test_runner.py` includes a `run_tssim()` method that needs the correct path to tssim:

```python
def run_tssim(self, repo_path, codebase_name, language):
    """Run tssim on a codebase."""
    tssim_path = Path(__file__).parent.parent / 'dist' / 'index.js'
    if not tssim_path.exists():
        return self._format_error('tssim', codebase_name,
                                 'tssim not built (run npm run build)')

    # ... rest of implementation
```

### Add tssim-specific Test Cases

Create `codebases/tssim-test-cases/` with:
- `exact-duplicates.ts` - Should be detected by all tools
- `value-differences.ts` - tssim should detect with ignore-values mode
- `name-differences.ts` - tssim should detect with ignore-names mode
- `structural-similarity.ts` - Advanced tssim features

### Configure Detection Modes

Test tssim's various modes:

```python
# In simple_test_runner.py
tssim_modes = [
    '--mode=exact',
    '--mode=ignore-values',
    '--mode=ignore-names',
    '--mode=structural'
]

for mode in tssim_modes:
    # Run tssim with each mode
    # Compare results
```

## Expected Results

After integration, you'll be able to:

1. **Quantify tssim's unique capabilities**:
   - "tssim detects 47% more duplicates than jscpd when using ignore-values mode"
   - "tssim is 2.3x faster than PMD CPD on TypeScript codebases"

2. **Identify improvement areas**:
   - Codebases where tssim could perform better
   - Patterns that other tools catch but tssim misses

3. **Track progress**:
   - Run on each commit to see performance changes
   - Compare versions: "v2.0 is 30% faster than v1.5"

4. **Build confidence**:
   - Demonstrate that tssim matches or exceeds other tools
   - Show concrete examples in documentation

## Documentation Integration

### Update tssim README.md

Add a section:

```markdown
## Testing & Benchmarks

tssim includes a comprehensive testing framework that compares it against
other duplication detection tools on real-world codebases.

See [testing-framework/README.md](testing-framework/README.md) for:
- How to run benchmarks
- Comparison with jscpd, PMD CPD, and Simian
- Results on popular open-source projects

Quick results:
- **FastAPI**: 42.3% duplication detected
- **Django**: 2.4% duplication detected
- **React**: 14.8% duplication detected

Run benchmarks yourself:
\`\`\`bash
cd testing-framework
python3 simple_test_runner.py
\`\`\`
```

### Reference in Documentation

In `docs/` directory:

```markdown
# Advanced Usage

## Benchmarking tssim

Use the built-in testing framework to compare tssim with other tools:

[Link to testing-framework/README.md]
```

## Maintenance

### Updating Codebases

```bash
# Refresh cloned repositories
cd testing-framework/codebases
find . -name '.git' -type d -exec sh -c 'cd "{}" && cd .. && git pull' \;
```

### Adding New Tools

Edit `simple_test_runner.py` to add new comparison tools:

```python
def run_newtool(self, repo_path, codebase_name, language):
    # Implementation
    pass
```

### Cleaning Up

```bash
# Remove large codebases to save space
cd testing-framework
rm -rf codebases/django codebases/react

# Keep only essential test cases
python3 add_codebase.py remove django
python3 add_codebase.py remove react
```

## Next Steps

1. **Review the framework files** in `tssim-contrib/duplication-testing/`
2. **Copy to tssim repository** as `testing-framework/`
3. **Run initial tests** to verify tssim integration
4. **Customize** tssim tool runner for your specific needs
5. **Add to CI/CD** for continuous benchmarking
6. **Document results** in tssim README and docs

## Questions?

For issues with the testing framework:
- Open an issue in the tssim repository
- Check `testing-framework/README.md` for troubleshooting
- Review `testing-framework/ANALYSIS.md` for expected results

## License

This testing framework is provided to help test and improve tssim. Feel free to modify it for your needs.
