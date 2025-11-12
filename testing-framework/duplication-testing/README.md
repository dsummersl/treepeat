# Duplication Detection Testing Framework

A comprehensive framework for testing and comparing code duplication detection tools across multiple open-source codebases.

## 🎯 Quick Start

```bash
# Run all tests
python3 simple_test_runner.py

# View results comparison
python3 compare_results.py tools

# Add new codebase
python3 add_codebase.py add myproject https://github.com/user/project.git Python "Description"
```

## 📊 Results Summary

**Total Execution Time**: 116.56 seconds | **Codebases**: 5 | **Tools**: 3 | **Tests**: 15

| Project | Files | LOC | Duplication | Tool |
|---------|-------|-----|------------|------|
| FastAPI | 1,184 | 99K | **42.3%** | jscpd |
| React | 3,807 | 632K | **14.8%** | jscpd |
| Django | 2,882 | 505K | **2.4%** | jscpd |
| Flask | 83 | 18K | **0.5%** | jscpd |

📄 **See [SUMMARY.md](SUMMARY.md) for quick overview**
📄 **See [ANALYSIS.md](ANALYSIS.md) for detailed analysis**

## Overview

This framework tests multiple duplication detection tools against various codebases:

- **Languages Tested**: Python, JavaScript, TypeScript
- **Tools Implemented**: jscpd, hash detector, line detector, **tssim**
- **Tools Planned**: PMD CPD, Simian

## Structure

```
duplication-tests/
├── codebases/          # Cloned repositories to test
├── tools/              # Duplication detection tool installations
├── results/            # Raw output from each tool
├── reports/            # Comparison reports (CSV, JSON)
├── codebases.json      # Configuration of codebases to test
└── run_duplication_tests.py  # Main test runner
```

## Codebases Tested

1. **tssim** (TypeScript) - Similarity detection tool
2. **FastAPI** (Python) - Modern Python web framework
3. **TypeScript** (TypeScript) - TypeScript compiler
4. **React** (JavaScript) - React library
5. **Spring Framework** (Java) - Spring Framework
6. **Roslyn** (C#) - C# compiler
7. **Kubernetes** (Go) - Container orchestration

## Tools

### jscpd
- Language-agnostic copy-paste detector
- Supports multiple output formats
- Fast execution

### PMD CPD (Copy/Paste Detector)
- Part of the PMD static analyzer
- Supports multiple languages
- Token-based detection

### Simian
- Similarity analyzer
- Configurable thresholds
- Multiple language support

### tssim ⭐ NEW
- TypeScript/JavaScript similarity detection
- Designed for flexible matching (ignore values, names, etc.)
- **Now integrated!** Tests run automatically when available
- Ideal for TypeScript and JavaScript codebases
- Supports advanced similarity detection modes

## Usage

### Basic Usage

```bash
python3 run_duplication_tests.py
```

This will:
1. Clone all configured codebases (if not already present)
2. Run each duplication detection tool on each codebase
3. Measure execution time
4. Count duplicates found
5. Generate comparison reports

### Adding New Codebases

Edit `codebases.json`:

```json
{
  "codebases": [
    {
      "name": "my-project",
      "url": "https://github.com/user/project.git",
      "language": "Python",
      "description": "Description of project"
    }
  ]
}
```

Then run the test suite again.

### Output

The framework generates:

1. **Console Output**: Real-time progress and summary table
2. **CSV Report**: `reports/duplication_report_YYYYMMDD_HHMMSS.csv`
3. **JSON Report**: `reports/duplication_report_YYYYMMDD_HHMMSS.json`
4. **Tool-specific Output**: Individual result files in `results/`

### Report Columns

- **codebase**: Name of the tested repository
- **language**: Primary programming language
- **tool**: Duplication detection tool used
- **status**: success, timeout, error, not_installed
- **duration**: Execution time in seconds
- **duplicates_found**: Number of duplicate code blocks detected
- **files**: Number of files in the codebase
- **lines_of_code**: Total lines of code
- **output_file**: Path to detailed output

## Detection Scenarios

### What We Can Detect Now

| Scenario | jscpd | hash_detector | line_detector | Status |
|----------|-------|---------------|---------------|--------|
| **Exact duplicates** | ✅ | ✅ | ✅ | Working |
| **Similar code blocks** | ✅ | ❌ | ✅ | Partial |
| **Different formatting** | ✅ | ❌ | ✅ | Working |

### What We Need Advanced Tools For

| Scenario | Example | Required Tool | Status |
|----------|---------|---------------|--------|
| **Ignore values** | `if (x > 100)` vs `if (x > 200)` | tssim, Simian | ⏳ Planned |
| **Ignore names** | `calcTotal()` vs `computeSum()` | AST analyzer | ⏳ Planned |
| **Structural similarity** | Bubble sort vs Insertion sort | Semantic analysis | ⏳ Future |

### Sample Test Cases

The `sample-duplicates/` directory contains intentional duplications:
- `exact_duplicate.py` - Identical code blocks
- `value_differences.py` - Same logic, different values
- `name_differences.py` - Same logic, different names
- `exact_duplicate.js` - JavaScript duplicates
- `structural_similarity.ts` - TypeScript structural patterns

**Current Detection**:
- jscpd: 2 duplicates (4.0%)
- line_detector: 13 sequences (26 occurrences)
- hash_detector: 0 (no exact file matches)

## Prerequisites

### System Requirements
- Python 3.7+
- Node.js 14+ (for jscpd and tssim)
- Java 11+ (for Simian and PMD)
- Git

### Tool Installation

#### jscpd
```bash
npm install -g jscpd
```

#### PMD CPD
```bash
# Download PMD from https://pmd.github.io/
# Extract to /opt/pmd or set PMD_HOME environment variable
```

#### Simian
```bash
# Download from http://www.harukizaemon.com/simian/
# Place simian.jar in the tools/ directory
```

#### tssim
```bash
cd tools/
git clone https://github.com/dsummersl/tssim.git
cd tssim
npm install
npm run build
```

## Extending the Framework

### Adding New Tools

Edit `run_duplication_tests.py` and add a new method:

```python
def run_newtool(self, repo_path: Path, codebase_name: str) -> Dict[str, Any]:
    """Run newtool on a codebase."""
    # Implementation here
    return {
        'tool': 'newtool',
        'codebase': codebase_name,
        'duration': elapsed_time,
        'status': 'success',
        'duplicates_found': count
    }
```

Then add it to the `tools` list in `run_all_tools()`.

### Customizing Reports

Modify the `generate_report()` method to add custom metrics, charts, or analysis.

## Known Issues

- Some large repositories may timeout (default: 300s per tool)
- Simian requires Java and has command-line length limits
- PMD CPD language detection may vary by file extension

## License

This framework is provided as-is for testing and comparison purposes.
