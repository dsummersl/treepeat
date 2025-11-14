# Duplication Detection Testing Framework - Summary

## Overview

This project provides a comprehensive framework for testing and comparing code duplication detection tools across multiple programming languages and project sizes.

**Total Execution Time**: 116.56 seconds
**Codebases Tested**: 5 (FastAPI, Django, Flask, React, Sample)
**Tools Tested**: 3 (jscpd, hash detector, line detector)
**Total Tests**: 15

## Quick Results

### Tools Performance

| Tool | Avg Time (s) | Total Duplicates Found | Success Rate |
|------|-------------|----------------------|--------------|
| jscpd | 18.21 | 3,762 | 100% |
| hash_detector | 1.12 | 98 | 100% |
| line_detector | 2.60 | 73,317 | 100% |

### Duplication by Codebase (jscpd)

| Project | Files | LOC | Duplication % | Duplicates |
|---------|-------|-----|--------------|------------|
| FastAPI | 1,184 | 99,430 | **42.3%** | 1,151 |
| React | 3,807 | 631,801 | **14.8%** | 1,998 |
| Sample | 5 | 510 | **4.0%** | 2 |
| Django | 2,882 | 504,677 | **2.4%** | 606 |
| Flask | 83 | 18,150 | **0.5%** | 5 |

## Key Findings

### 1. **FastAPI has highest duplication** (42.3%)
   - Likely due to test fixtures and API patterns
   - Demonstrates need for refactoring in rapidly growing projects

### 2. **Flask has lowest duplication** (0.5%)
   - Smallest, most focused codebase
   - Well-maintained over time

### 3. **Tool Variance is High** (114%-137%)
   - Different tools detect different types of duplicates
   - No single "correct" answer
   - Each tool serves different purposes

### 4. **Line Detector finds most duplicates**
   - 73,317 total vs 3,762 (jscpd) vs 98 (hash)
   - High false positive rate
   - Good for initial screening

### 5. **Hash Detector is fastest**
   - 15x faster than jscpd
   - Only finds exact file duplicates
   - Good for quick checks

## Detection Capabilities

### What Tools CAN Detect

✅ **Exact duplicates** (all tools)
- Copy-pasted code blocks
- Identical files

✅ **Similar code blocks** (jscpd, line detector)
- Same logic with minor formatting differences
- Repeated patterns

✅ **Test fixtures** (all tools)
- Duplicated test setup code
- Mock data

### What Tools CANNOT Detect

❌ **Semantic duplicates**
- Same logic, different syntax
- Example: `for` loop vs `map()` function

❌ **Renamed variables**
- Same code with different variable names
- Example: `calculateTotal()` vs `computeSum()`

❌ **Structural similarity**
- Similar algorithms with different implementations
- Example: bubble sort vs insertion sort

### Future Enhancements Needed

To detect advanced scenarios, we would need:

1. **AST-based analysis** - Parse code structure
2. **Token normalization** - Ignore variable names
3. **Semantic analysis** - Compare behavior, not syntax
4. **tssim integration** - User's tool for flexible matching
5. **PMD CPD / Simian** - Industry tools with advanced features

## Usage Guide

### Run Tests

```bash
cd duplication-tests
python3 simple_test_runner.py
```

### Add New Codebase

```bash
python3 add_codebase.py add myproject https://github.com/user/project.git Python "My project"
```

### Compare Results

```bash
# Compare tools
python3 compare_results.py tools

# Compare codebases
python3 compare_results.py codebases

# Compare two test runs
python3 compare_results.py reports reports/run1.json reports/run2.json
```

### View Results

- **Console**: Real-time output during test execution
- **CSV**: `reports/duplication_report_YYYYMMDD_HHMMSS.csv`
- **JSON**: `reports/duplication_report_YYYYMMDD_HHMMSS.json`
- **Tool Output**: `results/<codebase>_<tool>/`

## Project Structure

```
duplication-tests/
├── codebases/              # Downloaded repositories
│   ├── sample-duplicates/  # Test cases with known duplicates
│   ├── fastapi/
│   ├── django/
│   ├── flask/
│   └── react/
├── results/                # Raw tool outputs
├── reports/                # Comparison reports (CSV, JSON)
├── tools/                  # Tool installations
├── codebases.json          # Codebase configuration
├── simple_test_runner.py   # Main test harness
├── add_codebase.py         # Add new codebases
├── compare_results.py      # Compare results
├── README.md               # Documentation
├── ANALYSIS.md             # Detailed analysis
└── SUMMARY.md              # This file
```

## Extensibility

### Adding New Tools

Edit `simple_test_runner.py`:

```python
def run_newtool(self, repo_path, codebase_name, language):
    # Implement tool execution
    return {
        'tool': 'newtool',
        'codebase': codebase_name,
        'duration': elapsed_time,
        'status': 'success',
        'duplicates_found': count
    }

# Add to tools list in run_all_tools()
```

### Adding New Languages

Update language mappings in `simple_test_runner.py`:

```python
ext_map = {
    'Python': ['.py'],
    'JavaScript': ['.js', '.jsx'],
    'TypeScript': ['.ts', '.tsx'],
    'Rust': ['.rs'],  # Add new language
}
```

### Adding Detection Scenarios

To test different detection modes:

1. **Exact Match**: Already implemented (all tools)
2. **Ignore Values**: Requires token normalization (future)
3. **Ignore Names**: Requires AST analysis (future)
4. **Structural**: Requires semantic analysis (future)

Example test matrix:

| Scenario | jscpd | hash | line | tssim | simian | PMD |
|----------|-------|------|------|-------|--------|-----|
| Exact | ✓ | ✓ | ✓ | ? | ? | ? |
| Ignore Values | Partial | ✗ | ✗ | ? | ? | ? |
| Ignore Names | ✗ | ✗ | ✗ | ? | ? | ? |
| Structural | Limited | ✗ | Limited | ? | ? | ? |

## Recommendations

### For Different Use Cases

**1. CI/CD Quality Gates**
- Use: jscpd
- Threshold: < 10% duplication
- Run on: Every commit

**2. Pre-commit Checks**
- Use: hash_detector
- Threshold: 0 exact duplicates
- Run on: Pre-commit hook

**3. Codebase Analysis**
- Use: line_detector first, then jscpd
- Purpose: Identify refactoring opportunities
- Run on: Monthly

**4. Advanced Analysis**
- Use: Multiple tools + manual review
- Purpose: Find subtle duplications
- Run on: Quarterly

### For Different Project Sizes

**Small Projects (<10K LOC)**
- Run all tools
- Review all duplicates manually
- Zero tolerance policy

**Medium Projects (10K-100K LOC)**
- Run jscpd + hash_detector
- Review top 10% duplicates
- Target < 5% duplication

**Large Projects (>100K LOC)**
- Run hash_detector frequently
- Run jscpd weekly
- Focus on changed files only
- Target < 10% duplication

## Limitations

### Current Limitations

1. **No tssim testing** - Repository not accessible
2. **No Simian testing** - Download restricted
3. **No PMD CPD testing** - Download restricted
4. **No AST analysis** - Not implemented
5. **No incremental analysis** - Full scan only
6. **No visualization** - Text reports only

### Known Issues

1. Line detector has high false positive rate
2. Hash detector only finds exact file matches
3. No support for ignoring values or names
4. No semantic similarity detection

## Future Work

### Short Term
- [ ] Add tssim integration
- [ ] Implement incremental scanning
- [ ] Add HTML report generation
- [ ] Create duplication heatmap visualization

### Medium Term
- [ ] Implement AST-based detector
- [ ] Add token normalization
- [ ] Support more languages (Java, C#, Go, Rust)
- [ ] Create VS Code extension

### Long Term
- [ ] ML-based similarity detection
- [ ] Semantic code analysis
- [ ] Auto-refactoring suggestions
- [ ] Integration with code review tools

## Contributing

To add new codebases:
```bash
python3 add_codebase.py add <name> <url> <language> <description>
```

To test with new tools:
1. Install the tool
2. Add detector method to `simple_test_runner.py`
3. Add to tools list in `run_all_tools()`
4. Run tests

## License

This framework is provided as-is for educational and testing purposes.

## Resources

- [jscpd Documentation](https://github.com/kucherenko/jscpd)
- [PMD CPD](https://pmd.github.io/latest/pmd_userdocs_cpd.html)
- [Simian](http://www.harukizaemon.com/simian/)

## Contact

For issues or questions, please open an issue in the repository.

---

**Generated**: 2025-11-11
**Framework Version**: 1.0
**Last Updated**: 2025-11-11
