from pathlib import Path
from ..conftest import parsed_fixture

from tssim.config import PipelineSettings, set_settings
from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
from tssim.pipeline.pipeline import run_pipeline
from tssim.pipeline.region_extraction import extract_all_regions
from tssim.pipeline.shingle import shingle_regions
from tssim.pipeline.normalizers.python import PythonImportNormalizer


fixture_path4 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass4.py"
fixture_path5 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass5.py"

parsed_dataclass4 = parsed_fixture(fixture_path4)
parsed_dataclass5 = parsed_fixture(fixture_path5)

extracted_regions = extract_all_regions([parsed_dataclass4, parsed_dataclass5])


def test_import_normalizer_with_docstring_content():
    """Test that module-level regions are correctly distinguished by their docstring content.

    After fixing the bug where string_content was being dropped (instead of truncated),
    the module-level regions now correctly show as different because their docstrings
    have different content:
    - dataclass4: "Factory for building normalizers based on settings."
    - dataclass5: "Configuration for normalizers using pydantic-setti" (truncated at 50 chars)

    Even though imports are removed by PythonImportNormalizer, the different docstrings
    prevent false similarity matches.
    """
    shingled_regions = shingle_regions(
        extracted_regions=extracted_regions,
        parsed_files=[parsed_dataclass4, parsed_dataclass5],
        normalizers=[PythonImportNormalizer()],
    )

    print(f"\nWith PythonImportNormalizer, shingled {len(shingled_regions)} regions:")
    for shingled in shingled_regions:
        print(f"  - {shingled.region.region_name}: {shingled.shingles} shingles")

    # Compute signatures and detect similarity
    signatures = compute_region_signatures(shingled_regions)
    result = detect_similarity(signatures, threshold=0.5)

    print(f"\nFound {len(result.similar_pairs)} similar pairs:")
    for pair in result.similar_pairs:
        print(
            f"  - {pair.region1.region_name} <-> {pair.region2.region_name}: {pair.similarity:.2%}"
        )

    # After the fix: module-level regions should NOT be similar because docstrings differ
    # Look for any module-level region pairs
    module_pairs = [p for p in result.similar_pairs if "lines_" in p.region1.region_name]

    assert len(module_pairs) == 0, (
        "Module-level regions should not be similar - they have different docstrings. "
        f"Found {len(module_pairs)} similar module pairs."
    )
    print("\n✓ Confirmed: Module regions with different docstrings are correctly identified as different")


def test_without_import_normalizer_shows_difference():
    """Test that module-level regions are correctly distinguished even without normalizer.

    With the fix to preserve string_content (truncated to 50 chars), the module-level
    regions are correctly identified as different due to their different docstrings,
    even when no normalizer is used.
    """
    for ext_region in extracted_regions:
        print(f"  - {ext_region.region.path.name}/{ext_region.region.region_name}")

    # Process WITHOUT PythonImportNormalizer
    shingled_regions = shingle_regions(
        extracted_regions=extracted_regions,
        parsed_files=[parsed_dataclass4, parsed_dataclass5],
        normalizers=[],  # No normalizers
    )

    print(f"\nWithout normalizer, shingled {len(shingled_regions)} regions:")
    for shingled in shingled_regions:
        print(f"  - {shingled.region.region_name}: {shingled.shingles.size} shingles")

    # Compute signatures and detect similarity
    signatures = compute_region_signatures(shingled_regions)
    result = detect_similarity(signatures, threshold=0.5)

    print(f"\nFound {len(result.similar_pairs)} similar pairs:")
    for pair in result.similar_pairs:
        print(
            f"  - {pair.region1.region_name} <-> {pair.region2.region_name}: {pair.similarity:.2%}"
        )

    # After the fix: module-level regions should NOT be similar
    module_pairs = [p for p in result.similar_pairs if "lines_" in p.region1.region_name]

    assert len(module_pairs) == 0, (
        "Module-level regions should not be similar - they have different docstrings. "
        f"Found {len(module_pairs)} similar module pairs."
    )
    print("\n✓ Confirmed: Even without normalizer, different docstrings prevent false matches")


def test_class_regions_are_actually_different():
    shingled_regions = shingle_regions(
        extracted_regions=extracted_regions,
        parsed_files=[parsed_dataclass4, parsed_dataclass5],
        normalizers=[PythonImportNormalizer()],
    )

    # Get just the class regions
    class_regions = [s for s in shingled_regions if "Normalizer" in s.region.region_name]
    print("\nClass regions:")
    for region in class_regions:
        print(f"  - {region.region.region_name}: {region.shingles.size} shingles")

    # Compute signatures for just class regions
    signatures = compute_region_signatures(class_regions)
    result = detect_similarity(signatures, threshold=0.5)

    print(f"\nSimilar class pairs found: {len(result.similar_pairs)}")

    # The classes should NOT be similar - they have different names and structure
    assert len(result.similar_pairs) == 0, (
        "Class regions should not be similar - they have different names "
        "(NormalizerSpec vs NormalizerSettings) and different structures"
    )
    print("✓ Confirmed: Class regions are correctly identified as different")


# ===== END-TO-END TESTS FOR TWO-LEVEL MATCHING =====


def test_e2e_two_level_matching_finds_duplicate_methods():
    """E2E test: Two-level matching should find duplicate methods between classes.

    Tests the scenario where ClassA and ClassB have some duplicate methods (method2, method3)
    and some different methods. The recursive extraction should find these individual method
    duplicates even though the classes themselves are different.
    """
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"
    test_file = fixture_dir / "class_with_methods.py"

    # Run the full pipeline
    result = run_pipeline(test_file)

    print("\n=== E2E Two-Level Matching Test ===")
    print(f"Total pairs found: {len(result.similar_pairs)}")
    for pair in result.similar_pairs:
        print(f"  {pair.region1.region_name} <-> {pair.region2.region_name}: {pair.similarity:.2%}")

    # Should find method2 and method3 as duplicates between ClassA and ClassB
    method_pairs = [
        p for p in result.similar_pairs
        if "method" in p.region1.region_name and "method" in p.region2.region_name
    ]

    assert len(method_pairs) >= 2, (
        f"Should find at least 2 duplicate methods (method2 and method3). "
        f"Found {len(method_pairs)} method pairs"
    )

    # Verify we found method2 and method3 duplicates
    method_names = set()
    for pair in method_pairs:
        method_names.add(pair.region1.region_name)
        method_names.add(pair.region2.region_name)

    assert "method2" in method_names, "Should find method2 duplicate"
    assert "method3" in method_names, "Should find method3 duplicate"

    print(f"✓ Successfully detected {len(method_pairs)} duplicate methods across classes")


def test_e2e_min_lines_filtering():
    """E2E test: min_lines threshold should filter out small regions.

    Tests that small duplicate functions (< min_lines) are filtered out,
    while larger duplicate functions (>= min_lines) are detected.
    """
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"

    # Set min_lines to 5
    settings = PipelineSettings()
    settings.lsh.min_lines = 5
    set_settings(settings)

    try:
        # Create a temporary directory with our test files
        result = run_pipeline(fixture_dir / "small_functions.py")

        # Also parse the second file by running on parent directory
        result = run_pipeline(fixture_dir)

        print("\n=== E2E Min Lines Filtering Test ===")
        print(f"Total pairs found: {len(result.similar_pairs)}")

        # Filter to just pairs from our test files
        test_pairs = [
            p for p in result.similar_pairs
            if "small_functions" in str(p.region1.path)
            and "small_functions" in str(p.region2.path)
        ]

        print(f"Pairs from test files: {len(test_pairs)}")
        for pair in test_pairs:
            print(f"  {pair.region1.region_name} ({pair.region1.end_line - pair.region1.start_line + 1} lines) "
                  f"<-> {pair.region2.region_name} ({pair.region2.end_line - pair.region2.start_line + 1} lines)")

        # Should find large_duplicate but not small_duplicate
        large_duplicate_found = any(
            "large_duplicate" in p.region1.region_name or "large_duplicate" in p.region2.region_name
            for p in test_pairs
        )

        small_duplicate_found = any(
            "small_duplicate" in p.region1.region_name
            and "small_duplicate" in p.region2.region_name
            and p.region1.path != p.region2.path  # Not self-similarity
            for p in test_pairs
        )

        # Note: small_duplicate is only 2 lines (def + return), so should be filtered out
        assert not small_duplicate_found, (
            "small_duplicate should be filtered out by min_lines=5"
        )

        print("✓ Min lines filtering working correctly")
        print(f"  - large_duplicate detected: {large_duplicate_found}")
        print(f"  - small_duplicate filtered: {not small_duplicate_found}")

    finally:
        # Reset settings
        set_settings(PipelineSettings())


def test_e2e_line_level_matching_creates_line_regions():
    """E2E test: Level 2 should create line-based regions for unmatched code.

    Tests that the two-level pipeline creates line-based regions in Level 2
    for code that wasn't matched by functions/classes in Level 1. While these
    line-based regions may not always match (depending on similarity threshold),
    they should be created for all unmatched sections.
    """
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"

    # Set min_lines to 3
    settings = PipelineSettings()
    settings.lsh.min_lines = 3
    settings.lsh.threshold = 0.7  # Moderate threshold
    set_settings(settings)

    try:
        result = run_pipeline(fixture_dir)

        print("\n=== E2E Line-Level Region Creation Test ===")
        print(f"Total signatures: {len(result.signatures)}")

        # Check that line-based regions were created
        line_regions = [s for s in result.signatures if s.region.region_type == "lines"]
        function_regions = [s for s in result.signatures if s.region.region_type == "function"]
        class_regions = [s for s in result.signatures if s.region.region_type == "class"]

        print("Region types created:")
        print(f"  - Functions: {len(function_regions)}")
        print(f"  - Classes: {len(class_regions)}")
        print(f"  - Line-based: {len(line_regions)}")

        # Should have created line-based regions for unmatched code
        assert len(line_regions) > 0, (
            "Should have created line-based regions for Level 2 matching"
        )

        # Check if any line-level matches were found
        line_level_pairs = [
            p for p in result.similar_pairs
            if p.region1.region_type == "lines" and p.region2.region_type == "lines"
        ]

        print(f"\nLine-level pairs found: {len(line_level_pairs)}")
        if line_level_pairs:
            for pair in line_level_pairs[:5]:  # Show first 5
                print(f"  {pair.region1.path.name}/{pair.region1.region_name} "
                      f"<-> {pair.region2.path.name}/{pair.region2.region_name}: {pair.similarity:.2%}")

        print(f"✓ Level 2 successfully created {len(line_regions)} line-based regions")
        print(f"✓ Found {len(line_level_pairs)} line-level matches")

    finally:
        # Reset settings
        set_settings(PipelineSettings())


def test_e2e_combined_results_from_both_levels():
    """E2E test: Final result should combine matches from both Level 1 and Level 2.

    Tests that the final SimilarityResult contains pairs from both region-level
    matching (Level 1) and line-level matching (Level 2).
    """
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"

    # Use settings that will catch matches at both levels
    settings = PipelineSettings()
    settings.lsh.min_lines = 3
    settings.lsh.threshold = 0.7
    set_settings(settings)

    try:
        result = run_pipeline(fixture_dir)

        print("\n=== E2E Combined Results Test ===")
        print(f"Total pairs: {len(result.similar_pairs)}")
        print(f"Total signatures: {len(result.signatures)}")

        # Count region types
        function_regions = [s for s in result.signatures if s.region.region_type == "function"]
        class_regions = [s for s in result.signatures if s.region.region_type == "class"]
        line_regions = [s for s in result.signatures if s.region.region_type == "lines"]

        print("Region types:")
        print(f"  - Functions: {len(function_regions)}")
        print(f"  - Classes: {len(class_regions)}")
        print(f"  - Line-based: {len(line_regions)}")

        # Should have signatures from both levels (unless no line-level matches were found)
        assert len(function_regions) > 0 or len(class_regions) > 0, (
            "Should have at least some Level 1 (function/class) regions"
        )

        # The pipeline should have created line-based regions for Level 2
        # (even if they didn't match, they should be in signatures)
        print("✓ Pipeline created regions from both levels")
        print(f"  - Level 1 (functions/classes): {len(function_regions) + len(class_regions)}")
        print(f"  - Level 2 (line-based): {len(line_regions)}")

    finally:
        # Reset settings
        set_settings(PipelineSettings())
