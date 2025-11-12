# Duplication Detection Testing Framework

A comprehensive framework for testing and comparing code duplication detection tools, including **tssim**, across multiple open-source codebases.

## 🎯 Quick Start

```bash
# Run all tests
python3 run_tests.py

# View results comparison
python3 compare_results.py tools

# Add new codebase
python3 add_codebase.py add myproject https://github.com/user/project.git Python "Description"
```

## 📊 What This Tests

This framework compares multiple duplication detection tools:

- **tssim** ⭐ - Tree-sitter based similarity detection (from this repo!)
- **jscpd** - Industry-standard token-based copy-paste detector
- **hash_detector** - Fast exact duplicate finder
- **line_detector** - Line-sequence matcher (planned)

## 🚀 Usage

### Run Tests

From the project root:
```bash
make benchmark
```

Or directly:
```bash
cd testing-framework
python3 run_tests.py
```

This will:
1. Clone all configured codebases (if not already present)
2. Run each duplication detection tool on each codebase
3. Measure execution time
4. Count duplicates found
5. Generate comparison reports

### View Results

```bash
# Compare tools
make benchmark-compare

# Or directly
cd testing-framework
python3 compare_results.py tools
```

### Add New Codebases

```bash
python3 add_codebase.py add myproject https://github.com/user/project.git Python "My project description"
```

Or edit `codebases.json` manually:

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

## 📁 Structure

```
testing-framework/
├── codebases/          # Cloned repositories (git-ignored)
├── results/            # Raw tool outputs (git-ignored)
├── reports/            # CSV/JSON comparison reports (git-ignored)
│   ├── latest.csv      # Symlink to most recent CSV
│   └── latest.json     # Symlink to most recent JSON
├── tools/              # Tool installations (empty, git-ignored)
├── codebases.json      # Configuration of codebases to test
├── run_tests.py        # Main test runner
├── compare_results.py  # Compare results across tools
└── add_codebase.py     # Add/remove codebases
```

## 🔧 Tools Tested

### tssim ⭐
- Tree-sitter based AST analysis
- Supports Python, JavaScript, TypeScript
- MinHash + LSH for similarity detection
- Configurable similarity thresholds
- **Automatically runs from this repository!**

### jscpd
- Language-agnostic token-based detector
- Industry standard for copy-paste detection
- Supports multiple output formats
- Fast execution

### hash_detector
- Built-in exact file duplicate finder
- MD5-based comparison
- Very fast
- Only finds identical files

## 📄 Output

The framework generates:

1. **Console Output**: Real-time progress and summary
2. **CSV Report**: `reports/comparison_YYYYMMDD_HHMMSS.csv`
3. **JSON Report**: `reports/results_YYYYMMDD_HHMMSS.json`
4. **Symlinks**: `reports/latest.csv` and `reports/latest.json`

### Report Columns

- **tool**: Duplication detection tool used
- **codebase**: Name of the tested repository
- **language**: Primary programming language
- **status**: success, timeout, error
- **duration**: Execution time in seconds
- **duplicates_found**: Number of duplicate code blocks detected
- **file_count**: Number of files analyzed
- **line_count**: Total lines of code

## 🧪 Codebases Tested

Current configuration includes:

1. **FastAPI** (Python) - Modern Python web framework
2. **Django** (Python) - Django web framework
3. **Flask** (Python) - Flask micro-framework
4. **React** (JavaScript) - React library

You can add more with `add_codebase.py` or by editing `codebases.json`.

## 🎓 Prerequisites

### Required
- Python 3.7+
- Git

### For tssim
Already included! Tests will run `uv run tssim` from the parent directory.

### For jscpd
```bash
npm install -g jscpd
```

## 📊 Example Results

From a typical run:

| Tool | Avg Duration | Total Duplicates |
|------|--------------|-----------------|
| tssim | ~30s | Varies by threshold |
| jscpd | ~18s | 1000s on large codebases |
| hash_detector | ~1s | Only exact matches |

See [SUMMARY.md](SUMMARY.md) and [ANALYSIS.md](ANALYSIS.md) for detailed analysis.

## 🔌 Extending the Framework

### Adding New Tools

Edit `run_tests.py` and add a new method:

```python
def run_newtool(self, repo_path: Path, codebase_name: str, language: str) -> Dict[str, Any]:
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

Then add it to the `tools` list in `test_codebase()`.

## 🐛 Known Issues

- Large repositories may timeout (default: 300s per tool)
- Some tools require specific versions of dependencies
- Results may vary based on tool configuration

## 📝 License

This framework is provided as-is for testing and comparison purposes.
