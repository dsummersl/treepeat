# Single Region Line-Level Matching Issue

## Summary

Files treated as "one region" (CSS, bash, SQL) cannot detect identical blocks of code when the files as a whole are not similar enough to match in Level 1.

## The Problem

### Current Behavior

When a file language doesn't have region extraction rules (CSS, bash, SQL):

1. **Level 1**: The entire file is treated as ONE region (`region_type="file"`)
2. **If no Level 1 match**: The entire file is marked as unmatched
3. **Level 2**: Creates ONE line-based region for the entire unmatched file
4. **Result**: Small identical blocks within otherwise different files are NOT detected

### Why This Happens

The line-level matching (Level 2) only creates line-based regions from **unmatched gaps** between Level 1 matches. For single-region files:

- If the whole file doesn't match in Level 1 → the whole file is one big gap
- Level 2 creates one line-based region for the entire file
- This is essentially the same comparison as Level 1
- No chunking or sliding window occurs

### Code Location

**Region extraction** (`whorl/pipeline/region_extraction.py:109-123`):
```python
if not mappings:
    # For unsupported languages, treat the entire file as one region
    logger.warning(
        "Language '%s' not supported for region extraction, treating entire file as one region",
        parsed_file.language,
    )
    region = Region(
        path=parsed_file.path,
        language=parsed_file.language,
        region_type="file",
        region_name=parsed_file.path.name,
        start_line=1,
        end_line=parsed_file.root_node.end_point[0] + 1,
    )
    regions = [ExtractedRegion(region=region, node=parsed_file.root_node)]
```

**Line-based region creation** (`whorl/pipeline/region_extraction.py:213-242`):
```python
def create_line_based_regions(
    parsed_files: list[ParsedFile],
    matched_lines_by_file: dict[Path, set[int]],
    min_lines: int,
) -> list[ExtractedRegion]:
    """Create line-based regions for unmatched sections of files."""
    line_regions: list[ExtractedRegion] = []

    for parsed_file in parsed_files:
        matched_lines = matched_lines_by_file.get(parsed_file.path, set())
        file_end_line = parsed_file.root_node.end_point[0] + 1

        unmatched_ranges = _find_unmatched_ranges(matched_lines, file_end_line)

        for start_line, end_line in unmatched_ranges:
            line_count = end_line - start_line + 1
            if line_count >= min_lines:
                extracted_region = _create_line_region(parsed_file, start_line, end_line)
                line_regions.append(extracted_region)
```

**Key issue**: `_find_unmatched_ranges()` finds gaps between matched lines. If there are no matched lines, it returns ONE range for the entire file.

## Test Case Demonstration

**Test**: `tests/pipeline/test_pipeline.py::test_single_region_files_with_identical_blocks`

**Setup**:
- Two CSS files with completely different content
- Both share an identical 22-line block in the middle
- File 1: 132 lines total (~17% overlap)
- File 2: 153 lines total (~14% overlap)

**Expected**: The identical block should be detected by line-level matching

**Actual Result**:
```
Total similar groups found: 1

Group 1:
  Similarity: 44.28%
  Regions:
    - comprehensive.css:1-210 (file) [comprehensive.css]
    - file_with_shared_block_1.css:1-132 (file) [file_with_shared_block_1.css]

Groups containing both test files: 0

ISSUE: No shared identical block was detected!
```

## Impact

This affects:
1. **CSS files**: Can't detect shared utility classes or component styles
2. **Bash scripts**: Can't detect identical helper functions
3. **SQL files**: Can't detect shared stored procedures or query patterns
4. **Any language without region extraction rules**

## Potential Solutions

### Option 1: Chunk-Based Approach for Single-Region Files

When a file is treated as a single region AND doesn't match in Level 1, break it into overlapping or non-overlapping chunks for Level 2:

```python
def create_line_based_regions_for_single_region_files(
    parsed_file: ParsedFile,
    chunk_size: int = 50,  # Lines per chunk
    overlap: int = 10,     # Overlap between chunks
) -> list[ExtractedRegion]:
    """Create overlapping line-based chunks for single-region files."""
    # Implementation would create sliding window chunks
```

**Pros**:
- Would detect identical blocks within different files
- Configurable chunk size and overlap
- Minimal impact on existing code

**Cons**:
- More regions to compare (performance impact)
- May create false positives with very small chunks
- Need to tune chunk_size and overlap parameters

### Option 2: Add Region Extraction Rules for CSS/Bash/SQL

Implement proper region extraction for these languages:

- **CSS**: Extract rule sets, media queries, keyframes
- **Bash**: Extract functions (already possible with tree-sitter)
- **SQL**: Extract stored procedures, functions, views

**Pros**:
- More accurate comparisons
- Leverages existing Level 1 infrastructure
- Semantic understanding of code structure

**Cons**:
- Requires tree-sitter query development for each language
- More complex implementation
- Ongoing maintenance

### Option 3: Hybrid Approach

1. Add region extraction for languages where it makes sense (Bash functions, SQL procedures)
2. Use chunk-based approach for truly flat files (CSS, config files)

## Recommendation

**Short-term**: Add region extraction rules for Bash and SQL, as they have clear function/procedure boundaries

**Long-term**: Implement chunk-based approach for CSS and other truly flat file formats

## Running the Test

```bash
uv run pytest tests/pipeline/test_pipeline.py::test_single_region_files_with_identical_blocks -v -s --no-cov
```

The test currently **fails** (as expected), demonstrating the issue.

## Related Files

- Test fixtures:
  - `tests/fixtures/css/file_with_shared_block_1.css` (132 lines, shared block at lines 47-68)
  - `tests/fixtures/css/file_with_shared_block_2.css` (153 lines, shared block at lines 55-76)
- Language implementations:
  - `whorl/pipeline/languages/css.py:57-58`
  - `whorl/pipeline/languages/bash.py:57-58`
  - `whorl/pipeline/languages/sql.py:52-53`
- Region extraction logic:
  - `whorl/pipeline/region_extraction.py:109-123` (single region creation)
  - `whorl/pipeline/region_extraction.py:213-242` (line-based region creation)
- Pipeline logic:
  - `whorl/pipeline/pipeline.py:184-219` (Level 2 matching)
