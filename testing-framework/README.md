# Duplication Detection Testing Framework for tssim

This directory contains a comprehensive testing framework ready to be contributed to the [tssim](https://github.com/dsummersl/tssim) repository.

## 📦 What's Included

### Main Framework (`duplication-testing/`)

A complete testing framework that:
- ✅ Tests tssim alongside other duplication detection tools
- ✅ Runs on multiple real-world codebases (FastAPI, Django, Flask, React)
- ✅ Generates standardized CSV/JSON reports for comparison
- ✅ Provides extensible architecture for adding tools and codebases
- ✅ Includes comprehensive documentation and analysis

### Documentation

- **`INTEGRATION.md`** - Detailed guide for integrating into tssim
- **`CONTRIBUTING_TO_TSSIM.md`** - Step-by-step PR creation guide
- **`duplication-testing/README.md`** - Framework usage documentation
- **`duplication-testing/SUMMARY.md`** - Results overview
- **`duplication-testing/ANALYSIS.md`** - In-depth findings

## 🚀 Quick Start

### Option 1: Create a Pull Request to tssim

Follow the comprehensive guide in `CONTRIBUTING_TO_TSSIM.md`:

```bash
# 1. Fork and clone tssim
git clone https://github.com/YOUR_USERNAME/tssim.git
cd tssim

# 2. Create feature branch
git checkout -b feature/testing-framework

# 3. Copy this framework
cp -r /path/to/tssim-contrib/duplication-testing ./testing-framework

# 4. Commit and push
git add testing-framework/
git commit -m "Add duplication detection testing framework"
git push origin feature/testing-framework

# 5. Create PR on GitHub
```

See `CONTRIBUTING_TO_TSSIM.md` for complete instructions.

### Option 2: Test Locally First

```bash
cd duplication-testing

# Run all tests
python3 simple_test_runner.py

# Compare results
python3 compare_results.py tools

# Add a new codebase
python3 add_codebase.py add myproject https://github.com/user/repo.git TypeScript "Description"
```

## 📊 What This Provides for tssim

### 1. Comparative Benchmarking

Compare tssim against industry-standard tools:
- **jscpd** - Token-based detection
- **PMD CPD** - Multi-language analyzer
- **Simian** - Similarity analyzer
- Custom detectors (hash-based, line-based)

### 2. Real-World Testing

Test on popular open-source codebases:
- **FastAPI** (Python, 99K LOC) - 42.3% duplication
- **Django** (Python, 505K LOC) - 2.4% duplication
- **Flask** (Python, 18K LOC) - 0.5% duplication
- **React** (JavaScript, 632K LOC) - 14.8% duplication

### 3. Standardized Reports

Generate professional reports:
- CSV format for spreadsheet analysis
- JSON format for programmatic access
- Console output for quick review
- Comparative analysis across tools

### 4. Extensibility

Easy to extend:
- Add new codebases with single command
- Integrate new tools with simple Python method
- Configure detection parameters
- Customize report formats

### 5. CI/CD Integration

Ready for automation:
- GitHub Actions workflow included
- Timeout and error handling
- Artifact upload support
- Scheduled or manual triggers

## 🔧 Key Features

### Automatic tssim Detection

The framework automatically finds tssim in:
- `../dist/index.js` (if in `tssim/testing-framework/`)
- `tools/tssim/dist/index.js` (if tssim installed in tools)
- Global npm installation

### Smart Codebase Management

- Downloads codebases on-demand
- Caches for faster subsequent runs
- Configurable via JSON
- Git-ignored to keep repo clean

### Comprehensive Metrics

For each test, tracks:
- Execution time
- Duplicates found
- File count
- Lines of code
- Duplication percentage
- Tool-specific details

### Multiple Detection Modes

Tests various scenarios:
- Exact duplicates
- Similar code blocks
- Different formatting
- Structural similarity (future)

## 📁 Directory Structure

```
tssim-contrib/
├── README.md                      # This file
├── INTEGRATION.md                 # Integration guide
├── CONTRIBUTING_TO_TSSIM.md       # PR creation guide
└── duplication-testing/           # Main framework
    ├── README.md                  # Framework docs
    ├── SUMMARY.md                 # Results summary
    ├── ANALYSIS.md                # Detailed analysis
    ├── simple_test_runner.py      # Main test runner
    ├── compare_results.py         # Results comparison
    ├── add_codebase.py            # Codebase manager
    ├── codebases.json             # Codebase config
    ├── .gitignore                 # Excludes large files
    ├── codebases/                 # Downloaded repos (git-ignored)
    ├── results/                   # Tool outputs (git-ignored)
    └── reports/                   # Generated reports (git-ignored)
```

## 🎯 Use Cases

### For tssim Development

1. **Validation** - Verify tssim results match expectations
2. **Performance** - Benchmark speed improvements
3. **Regression Testing** - Catch behavior changes
4. **Feature Development** - Test new detection modes

### For tssim Users

1. **Evaluation** - Compare tssim with other tools
2. **Confidence** - See real-world results
3. **Tuning** - Find optimal parameters for your codebase
4. **Documentation** - Understand what tssim detects

### For tssim Documentation

1. **Examples** - Concrete results to reference
2. **Comparisons** - Show advantages over other tools
3. **Benchmarks** - Performance data
4. **Use Cases** - Real-world applications

## 🧪 Testing Strategy

### Current Implementation

| Tool | Status | Language Support |
|------|--------|-----------------|
| tssim | ✅ Integrated | TypeScript, JavaScript |
| jscpd | ✅ Working | All languages |
| hash_detector | ✅ Working | All languages |
| line_detector | ✅ Working | All languages |

### Planned Additions

- [ ] PMD CPD integration
- [ ] Simian integration
- [ ] More languages (Go, Java, Rust, C#)
- [ ] HTML report generation
- [ ] Visualization (heatmaps, charts)
- [ ] Incremental analysis

## 📈 Sample Results

Based on initial testing:

```
FastAPI: 42.3% duplication (highest)
  - jscpd: 1,151 duplicates
  - Indicates refactoring opportunities

Django: 2.4% duplication (well-maintained)
  - jscpd: 606 duplicates
  - Clean codebase example

Flask: 0.5% duplication (lowest)
  - jscpd: 5 duplicates
  - Best-in-class example

React: 14.8% duplication
  - jscpd: 1,998 duplicates
  - Moderate duplication

Tool Performance:
  - jscpd: 18.21s average, most comprehensive
  - hash_detector: 1.12s average, fastest
  - line_detector: 2.60s average, most sensitive
```

## 🤝 Contributing to tssim

### Ready to Submit?

1. Read `CONTRIBUTING_TO_TSSIM.md`
2. Fork tssim repository
3. Copy `duplication-testing/` to `testing-framework/`
4. Create pull request
5. Reference this documentation

### Questions?

- Check `INTEGRATION.md` for technical details
- Review `duplication-testing/README.md` for usage
- See `CONTRIBUTING_TO_TSSIM.md` for PR process

## 📝 License

This framework is provided for testing and benchmarking purposes. Feel free to modify for your needs when contributing to tssim.

## 🔗 Links

- **tssim Repository**: https://github.com/dsummersl/tssim
- **jscpd**: https://github.com/kucherenko/jscpd
- **PMD CPD**: https://pmd.github.io/latest/pmd_userdocs_cpd.html

## ✨ Benefits Summary

Adding this to tssim provides:

✅ **Credibility** - Demonstrate tssim's effectiveness with real data
✅ **Quality Assurance** - Continuous testing against other tools
✅ **Documentation** - Concrete examples for users
✅ **Development** - Framework for testing new features
✅ **Community** - Tool for users to evaluate tssim
✅ **Transparency** - Open comparison with competitors

---

**Ready to contribute?** Start with `CONTRIBUTING_TO_TSSIM.md`!
