# Contributing the Duplication Testing Framework to tssim

This guide explains how to add this comprehensive testing framework to the tssim repository as a pull request.

## What This Adds

This contribution provides tssim with:

1. **Comparative Benchmarking**: Compare tssim against other duplication detection tools
2. **Real-World Testing**: Test on popular open-source codebases (FastAPI, Django, Flask, React, etc.)
3. **Standardized Reporting**: CSV and JSON reports for easy analysis
4. **Extensible Framework**: Easy to add new codebases and tools
5. **CI/CD Integration**: Ready for automated benchmarking

## Prerequisites

Before creating the PR, ensure you have:

- Fork of dsummersl/tssim repository
- Git configured with SSH or HTTPS authentication
- Python 3.7+ installed
- Node.js 14+ installed

## Step-by-Step Guide

### Step 1: Fork and Clone tssim

```bash
# Fork the repository on GitHub first (click "Fork" button)

# Clone your fork
git clone https://github.com/YOUR_USERNAME/tssim.git
cd tssim

# Add upstream remote
git remote add upstream https://github.com/dsummersl/tssim.git
```

### Step 2: Create a Feature Branch

```bash
# Update your fork
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/testing-framework
```

### Step 3: Copy the Testing Framework

```bash
# From the agentexperiments directory where this framework lives
# Copy the duplication-testing directory to tssim

cp -r /path/to/agentexperiments/tssim-contrib/duplication-testing ./testing-framework

# Verify files copied
ls -la testing-framework/
```

### Step 4: Test the Integration

```bash
# Build tssim first
npm install
npm run build

# Navigate to testing framework
cd testing-framework

# Install Python dependencies if needed
pip3 install -r requirements.txt  # If requirements file exists

# Test with a small codebase first
python3 simple_test_runner.py

# Verify tssim is detected and runs
```

### Step 5: Update tssim Documentation

Edit `README.md` in the root of tssim to add:

```markdown
## Testing & Benchmarks

tssim includes a comprehensive testing framework for comparing duplication detection tools.

See [testing-framework/README.md](testing-framework/README.md) for:
- Benchmarking against other tools (jscpd, PMD CPD, Simian)
- Testing on real-world codebases
- Comparative analysis and reports

Quick start:
\`\`\`bash
cd testing-framework
python3 simple_test_runner.py
\`\`\`
```

### Step 6: (Optional) Add GitHub Actions Workflow

Create `.github/workflows/benchmarks.yml`:

```yaml
name: Benchmarks

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          npm install
          npm run build
          npm install -g jscpd

      - name: Run benchmarks
        run: |
          cd testing-framework
          python3 simple_test_runner.py

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: benchmark-results
          path: testing-framework/reports/
          retention-days: 90
```

### Step 7: Commit Your Changes

```bash
# Add files
git add testing-framework/
git add README.md  # If you updated it
git add .github/workflows/benchmarks.yml  # If you added it

# Commit with descriptive message
git commit -m "Add comprehensive duplication detection testing framework

This adds a testing framework that:
- Compares tssim with other tools (jscpd, hash detector, line detector)
- Tests on real-world codebases (FastAPI, Django, Flask, React)
- Generates standardized CSV/JSON reports
- Provides extensible framework for adding new tools and codebases
- Includes tssim integration with automatic detection

Benefits:
- Validate tssim against established tools
- Benchmark performance on real codebases
- Track improvements across versions
- Demonstrate capabilities with concrete examples
- Support for CI/CD integration

See testing-framework/INTEGRATION.md for detailed integration guide."
```

### Step 8: Push to Your Fork

```bash
# Push to your fork
git push origin feature/testing-framework
```

### Step 9: Create Pull Request

#### Via GitHub Web Interface:

1. Go to https://github.com/YOUR_USERNAME/tssim
2. Click "Compare & pull request" button
3. Set base repository: `dsummersl/tssim` base: `main`
4. Set head repository: `YOUR_USERNAME/tssim` compare: `feature/testing-framework`
5. Fill in the PR template (see below)
6. Click "Create pull request"

#### Via GitHub CLI:

```bash
gh pr create \
  --repo dsummersl/tssim \
  --base main \
  --head YOUR_USERNAME:feature/testing-framework \
  --title "Add comprehensive duplication detection testing framework" \
  --body-file PR_TEMPLATE.md
```

## Pull Request Template

Use this template for your PR description:

```markdown
## Summary

This PR adds a comprehensive testing framework for comparing duplication detection tools, with full tssim integration.

## What's Included

### Testing Framework (`testing-framework/`)
- **Main runner**: `simple_test_runner.py` - Runs all tools on all codebases
- **Comparison tool**: `compare_results.py` - Compare results across tools or runs
- **Codebase manager**: `add_codebase.py` - Add/remove test codebases
- **Documentation**: README.md, SUMMARY.md, ANALYSIS.md, INTEGRATION.md

### Tools Integrated
- ✅ **tssim** - Full integration with automatic detection
- ✅ jscpd - Industry-standard token-based detector
- ✅ hash_detector - Fast exact duplicate finder
- ✅ line_detector - Line sequence matcher

### Test Codebases
- FastAPI (Python, 99K LOC, 42.3% duplication)
- Django (Python, 505K LOC, 2.4% duplication)
- Flask (Python, 18K LOC, 0.5% duplication)
- React (JavaScript, 632K LOC, 14.8% duplication)
- Sample test cases with known duplicates

## Benefits for tssim

1. **Validation**: Compare tssim results against established tools
2. **Performance**: Benchmark execution time on real codebases
3. **Coverage**: Test diverse code patterns and languages
4. **Regression Testing**: Detect behavior changes across versions
5. **Documentation**: Demonstrate capabilities with concrete examples
6. **CI/CD Ready**: Automated benchmarking support

## Usage

```bash
# Run all tests
cd testing-framework
python3 simple_test_runner.py

# Compare tools
python3 compare_results.py tools

# Add new codebase
python3 add_codebase.py add myproject https://github.com/user/project.git TypeScript "My project"
```

## Testing Done

- [x] Tested on Python 3.10
- [x] Tested with Node.js 18
- [x] All tools run successfully
- [x] Reports generate correctly
- [x] tssim integration works (when tssim is built)

## Integration Points

### tssim Detection
The framework automatically detects tssim in:
- `../dist/index.js` (when in `tssim/testing-framework/`)
- `tools/tssim/dist/index.js` (when tssim in tools dir)
- Global installation (via `which tssim`)

### Output Format
tssim results are parsed from JSON output and integrated into standardized reports alongside other tools.

## Documentation

- **README.md**: User guide and quickstart
- **INTEGRATION.md**: Detailed integration instructions
- **SUMMARY.md**: Results overview and recommendations
- **ANALYSIS.md**: In-depth analysis of findings

## Future Enhancements

Potential additions (separate PRs):
- [ ] Add PMD CPD integration
- [ ] Add Simian integration
- [ ] HTML report generation
- [ ] Duplication heatmap visualization
- [ ] Incremental scanning support
- [ ] More test codebases (Go, Java, Rust)

## Breaking Changes

None - this is a purely additive change.

## Questions?

See `testing-framework/INTEGRATION.md` for detailed documentation.

---

**Note**: Large test codebases are not included in the PR. They are cloned automatically when tests run. The `.gitignore` excludes `codebases/`, `results/`, and `reports/` directories.
```

## What to Expect

### Review Process

The maintainer (dsummersl) will likely:

1. **Review the code** - Check Python code quality and structure
2. **Test locally** - Run the framework on their machine
3. **Evaluate fit** - Determine if this aligns with tssim's goals
4. **Request changes** - May ask for:
   - Additional documentation
   - Code style improvements
   - Different directory structure
   - Specific tssim CLI integration

### Common Questions You Might Get

**Q: Why not use existing benchmark frameworks?**
A: This framework is specifically designed for duplication detection tools and provides direct tssim integration.

**Q: How large are the test codebases?**
A: They're cloned on-demand and git-ignored. Users choose which codebases to test.

**Q: Does this add dependencies to tssim?**
A: No - the testing framework is self-contained. tssim only needs Node.js as before.

**Q: Can this run in CI/CD?**
A: Yes - see `.github/workflows/benchmarks.yml` example.

### Timeline

- Initial review: 1-7 days
- Discussion/changes: Varies
- Merge: When approved

## Alternative: Manual Instructions

If you can't create the PR directly, you can:

1. **Share the framework separately**:
   ```bash
   # Create a gist or separate repo
   cd tssim-contrib
   gh gist create duplication-testing/* --public
   ```

2. **Provide instructions** for the maintainer to integrate manually

3. **Create an issue** first to discuss the contribution before PR

## Troubleshooting

### "tssim not found" Error

Ensure tssim is built:
```bash
cd /path/to/tssim
npm run build
ls dist/index.js  # Should exist
```

### Tests Timeout

Reduce codebases tested:
```bash
cd testing-framework
python3 add_codebase.py remove django
python3 add_codebase.py remove react
```

### Git Authentication Issues

Use HTTPS with token:
```bash
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/tssim.git
```

Or use SSH:
```bash
git remote set-url origin git@github.com:YOUR_USERNAME/tssim.git
```

## Files to Include in PR

Checklist of what should be in the PR:

- [x] `testing-framework/` directory with all files
- [x] `testing-framework/README.md`
- [x] `testing-framework/SUMMARY.md`
- [x] `testing-framework/ANALYSIS.md`
- [x] `testing-framework/INTEGRATION.md`
- [x] `testing-framework/simple_test_runner.py`
- [x] `testing-framework/compare_results.py`
- [x] `testing-framework/add_codebase.py`
- [x] `testing-framework/codebases.json`
- [x] `testing-framework/.gitignore` (excludes codebases/, results/, reports/)
- [x] Updated root `README.md` (optional but recommended)
- [x] `.github/workflows/benchmarks.yml` (optional)

## Questions?

If you have questions about the contribution process:

1. Check the tssim repository for contribution guidelines
2. Open an issue in tssim to discuss before PR
3. Reference this document in your PR

## Success Criteria

Your PR is ready when:

- ✅ All files copied correctly
- ✅ Tests run successfully locally
- ✅ tssim integration works
- ✅ Documentation is clear
- ✅ Commit message is descriptive
- ✅ PR description is comprehensive

Good luck with your contribution! 🚀
