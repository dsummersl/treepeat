from pathlib import Path

from whorl.models.similarity import Region, SimilarRegionGroup, SimilarityResult
from ..conftest import parsed_fixture
import pytest

from whorl.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from whorl.pipeline.lsh_stage import detect_similarity
from whorl.pipeline.minhash_stage import compute_region_signatures
from whorl.pipeline.pipeline import run_pipeline
from whorl.pipeline.region_extraction import extract_all_regions
from whorl.pipeline.shingle import shingle_regions
from ..conftest import default_rule_engine


fixture_class_with_methods = (
    Path(__file__).parent.parent / "fixtures" / "python" / "class_with_methods.py"
)
fixture_path4 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass4.py"
fixture_path5 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass5.py"


def test_dissimilar_files():
    parsed_dataclass4 = parsed_fixture(fixture_path4)
    parsed_dataclass5 = parsed_fixture(fixture_path5)
    engine = default_rule_engine()

    extracted_regions = extract_all_regions([parsed_dataclass4, parsed_dataclass5], engine)

    shingled_regions = shingle_regions(
        extracted_regions=extracted_regions,
        parsed_files=[parsed_dataclass4, parsed_dataclass5],
        rule_engine=engine,
    )

    signatures = compute_region_signatures(shingled_regions)
    result = detect_similarity(signatures, threshold=0.5)
    assert len(result.similar_groups) == 0


def _make_region(path, language, region_type, region_name, start_line, end_line) -> Region:
    return Region(
        path=path,
        language=language,
        region_type=region_type,
        region_name=region_name,
        start_line=start_line,
        end_line=end_line,
    )


def _assert_regions_in_same_group(
    result: SimilarityResult, region1: Region, region2: Region
) -> SimilarRegionGroup:
    """Assert that region1 and region2 are in the same similarity group."""
    for group in result.similar_groups:
        if region1 in group.regions and region2 in group.regions:
            return group
    raise AssertionError(
        f"Regions ({region1}, {region2}) not found in same group ({result.similar_groups})"
    )


classA_region = _make_region(fixture_class_with_methods, "python", "class", "ClassA", 4, 27)
classB_region = _make_region(fixture_class_with_methods, "python", "class", "ClassB", 30, 54)


fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"
class_with_methods_file = fixture_dir / "class_with_methods.py"


@pytest.mark.parametrize(
    "ruleset, path, threshold, similar_groups, expected_regions",
    [
        # Tests with ruleset=none (no normalization)
        ("none", class_with_methods_file, 0.1, 0, []),
        ("none", class_with_methods_file, 0.9, 1, []),
        # Tests with ruleset=default (with normalization)
        # With normalization and identifier reset per region, classes become more similar
        ("default", class_with_methods_file, 0.1, 0, []),
        ("default", class_with_methods_file, 0.3, 1, []),
        # With threshold 0.5, ClassA and ClassB match at ~82% (2 of 3 methods identical)
        ("default", class_with_methods_file, 0.5, 3, [(classA_region, classB_region)]),
        # Tests with entire fixture directory (ruleset=none) - verifies no self-overlapping false positives
        (
            "none",
            fixture_dir,
            0.7,
            6,  # Updated: verification filters out 1 group below order-sensitive threshold
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        fixture_dir / "small_functions_b.py",
                        "python",
                        "function",
                        "large_duplicate",
                        9,
                        18,
                    ),
                    _make_region(
                        fixture_dir / "small_functions.py",
                        "python",
                        "function",
                        "large_duplicate",
                        9,
                        18,
                    ),
                ),
                # Similar functions across dataclass files
                (
                    _make_region(
                        fixture_dir / "dataclass1.py",
                        "python",
                        "function",
                        "my_adapted_one",
                        21,
                        26,
                    ),
                    _make_region(fixture_dir / "dataclass2.py", "python", "function", "one", 2, 7),
                ),
            ],
        ),
        (
            "none",
            fixture_dir,
            0.8,
            4,  # Updated: verification filters out 1 group below order-sensitive threshold
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        fixture_dir / "small_functions_b.py",
                        "python",
                        "function",
                        "large_duplicate",
                        9,
                        18,
                    ),
                    _make_region(
                        fixture_dir / "small_functions.py",
                        "python",
                        "function",
                        "large_duplicate",
                        9,
                        18,
                    ),
                ),
                # Duplicate methods within same file (non-overlapping)
                (
                    _make_region(
                        fixture_class_with_methods, "python", "function", "method2", 13, 19
                    ),
                    _make_region(
                        fixture_class_with_methods, "python", "function", "method2", 40, 46
                    ),
                ),
                (
                    _make_region(
                        fixture_class_with_methods, "python", "function", "method3", 21, 27
                    ),
                    _make_region(
                        fixture_class_with_methods, "python", "function", "method3", 48, 54
                    ),
                ),
            ],
        ),
        (
            "none",
            fixture_dir,
            0.9,
            2,  # Updated: verification filters out 1 group below order-sensitive threshold
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        fixture_dir / "small_functions_b.py",
                        "python",
                        "function",
                        "large_duplicate",
                        9,
                        18,
                    ),
                    _make_region(
                        fixture_dir / "small_functions.py",
                        "python",
                        "function",
                        "large_duplicate",
                        9,
                        18,
                    ),
                ),
                # Duplicate method2 within same file (non-overlapping)
                (
                    _make_region(
                        fixture_class_with_methods, "python", "function", "method2", 13, 19
                    ),
                    _make_region(
                        fixture_class_with_methods, "python", "function", "method2", 40, 46
                    ),
                ),
            ],
        ),
    ],
)
def test_match_counts(ruleset, path, threshold, similar_groups, expected_regions):
    """Testing with different rulesets and LSH thresholds."""
    set_settings(
        PipelineSettings(
            rules=RulesSettings(ruleset=ruleset),
            shingle=ShingleSettings(),
            minhash=MinHashSettings(),
            lsh=LSHSettings(threshold=threshold),
        )
    )
    result = run_pipeline(path)

    assert len(result.similar_groups) == similar_groups
    for region1, region2 in expected_regions:
        _assert_regions_in_same_group(result, region1, region2).similarity > threshold


def test_single_region_files_with_identical_blocks():
    """
    Test that files treated as 'one region' (CSS, bash, SQL) can detect
    identical blocks of lines when they meet the min_lines threshold.

    This test creates two CSS files that:
    - Are mostly different (unique header/footer sections)
    - Share an identical block of ~15 lines in the middle
    - Should have that identical block detected by line-level matching
    """
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "css"
    file1 = fixture_dir / "file_with_shared_block_1.css"
    file2 = fixture_dir / "file_with_shared_block_2.css"

    # Use a low threshold and min_lines to catch the shared block
    set_settings(
        PipelineSettings(
            rules=RulesSettings(ruleset="default"),
            shingle=ShingleSettings(k=3),
            minhash=MinHashSettings(num_perm=128),
            lsh=LSHSettings(
                threshold=0.3,  # Low threshold to catch partial matches
                min_lines=5,    # Shared block is ~15 lines
            ),
        )
    )

    result = run_pipeline(fixture_dir)

    # Expected behavior: The shared block (lines ~14-32 in file1, lines ~14-32 in file2)
    # should be detected either in Level 1 or Level 2

    # Print detailed results for debugging
    print(f"\n=== Test Results for Single Region Files ===")
    print(f"Total similar groups found: {len(result.similar_groups)}")

    for i, group in enumerate(result.similar_groups):
        print(f"\nGroup {i + 1}:")
        print(f"  Similarity: {group.similarity:.2%}")
        print(f"  Regions:")
        for region in group.regions:
            print(f"    - {region.path.name}:{region.start_line}-{region.end_line} "
                  f"({region.region_type}) [{region.region_name}]")

    # Find any group that contains regions from both files
    shared_groups = []
    for group in result.similar_groups:
        file1_in_group = any(r.path == file1 for r in group.regions)
        file2_in_group = any(r.path == file2 for r in group.regions)
        if file1_in_group and file2_in_group:
            shared_groups.append(group)

    print(f"\n=== Analysis ===")
    print(f"Groups containing both files: {len(shared_groups)}")

    if shared_groups:
        for i, group in enumerate(shared_groups):
            print(f"\nShared group {i + 1}:")
            file1_regions = [r for r in group.regions if r.path == file1]
            file2_regions = [r for r in group.regions if r.path == file2]
            print(f"  File 1 regions: {file1_regions}")
            print(f"  File 2 regions: {file2_regions}")
    else:
        print("  ISSUE: No shared identical block was detected!")
        print("  This suggests that single-region files are not being broken down")
        print("  into smaller line-based chunks for comparison.")

    # This assertion documents the expected behavior
    # If it fails, it confirms the issue: identical blocks are NOT being detected
    assert len(shared_groups) > 0, (
        "Expected to find at least one similarity group containing regions from both files. "
        "The identical block (shared-button, shared-container, shared-card) should be detected "
        "by line-level matching, but was not found. This indicates that single-region files "
        "are not being properly chunked for line-level comparison."
    )
