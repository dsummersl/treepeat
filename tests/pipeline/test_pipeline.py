from pathlib import Path

from tssim.models.similarity import Region, SimilarRegionPair, SimilarityResult
from ..conftest import parsed_fixture
import pytest

from tssim.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
from tssim.pipeline.pipeline import run_pipeline
from tssim.pipeline.region_extraction import extract_all_regions
from tssim.pipeline.rules import RuleEngine, parse_rule
from tssim.pipeline.shingle import shingle_regions


fixture_class_with_methods = (
    Path(__file__).parent.parent / "fixtures" / "python" / "class_with_methods.py"
)
fixture_path4 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass4.py"
fixture_path5 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass5.py"


@pytest.mark.parametrize(
    "rules",
    [
        [],
        [parse_rule("python:skip:nodes=import_statement|import_from_statement")],
    ],
)
def test_dissimilar_files(rules):
    parsed_dataclass4 = parsed_fixture(fixture_path4)
    parsed_dataclass5 = parsed_fixture(fixture_path5)

    extracted_regions = extract_all_regions([parsed_dataclass4, parsed_dataclass5])

    shingled_regions = shingle_regions(
        extracted_regions=extracted_regions,
        parsed_files=[parsed_dataclass4, parsed_dataclass5],
        rule_engine=RuleEngine(rules),
    )

    signatures = compute_region_signatures(shingled_regions)
    result = detect_similarity(signatures, threshold=0.5)
    assert len(result.similar_pairs) == 0


def _make_region(path, language, region_type, region_name, start_line, end_line) -> Region:
    return Region(
        path=path,
        language=language,
        region_type=region_type,
        region_name=region_name,
        start_line=start_line,
        end_line=end_line,
    )


def _assert_has_pair(
    result: SimilarityResult, region1: Region, region2: Region
) -> SimilarRegionPair:
    """Assert that a pair (region1, region2) exists in the pairs iterable (in either order)."""
    for pair in result.similar_pairs:
        if (pair.region1 == region1 and pair.region2 == region2) or (
            pair.region1 == region2 and pair.region2 == region1
        ):
            return pair
    raise AssertionError(f"Pair ({region1}, {region2}) not found in pairs ({result.similar_pairs})")


classA_region = _make_region(fixture_class_with_methods, "python", "class", "ClassA", 4, 27)
classB_region = _make_region(fixture_class_with_methods, "python", "class", "ClassB", 30, 54)


fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"
class_with_methods_file = fixture_dir / "class_with_methods.py"

@pytest.mark.parametrize(
    "ruleset, path, threshold, similar_pairs, expected_regions",
    [
        # Tests with ruleset=none (no normalization)
        ("none", class_with_methods_file, 0.1, 1, [(classA_region, classB_region)]),
        ("none", class_with_methods_file, 0.3, 1, [(classA_region, classB_region)]),
        ("none", class_with_methods_file, 0.5, 1, [(classA_region, classB_region)]),
        ("none", class_with_methods_file, 0.7, 1, [(classA_region, classB_region)]),
        (
            "none",
            class_with_methods_file,
            0.8,
            2,
            [
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
        # Tests with ruleset=default (with normalization)
        # With normalization and identifier reset per region, classes become more similar
        ("default", class_with_methods_file, 0.1, 1, [(classA_region, classB_region)]),
        ("default", class_with_methods_file, 0.3, 1, [(classA_region, classB_region)]),
        # With threshold 0.5, ClassA and ClassB match at ~82% (2 of 3 methods identical)
        ("default", class_with_methods_file, 0.5, 1, [(classA_region, classB_region)]),
        # Tests with entire fixture directory (ruleset=none) - verifies no self-overlapping false positives
        (
            "none",
            fixture_dir,
            0.7,
            4,
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        fixture_dir / "small_functions_b.py", "python", "function", "large_duplicate", 9, 18
                    ),
                    _make_region(
                        fixture_dir / "small_functions.py", "python", "function", "large_duplicate", 9, 18
                    ),
                ),
                # Similar functions across dataclass files
                (
                    _make_region(
                        fixture_dir / "dataclass1.py", "python", "function", "my_adapted_one", 21, 26
                    ),
                    _make_region(
                        fixture_dir / "dataclass2.py", "python", "function", "one", 2, 7
                    ),
                ),
            ],
        ),
        (
            "none",
            fixture_dir,
            0.8,
            4,
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        fixture_dir / "small_functions_b.py", "python", "function", "large_duplicate", 9, 18
                    ),
                    _make_region(
                        fixture_dir / "small_functions.py", "python", "function", "large_duplicate", 9, 18
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
            2,
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        fixture_dir / "small_functions_b.py", "python", "function", "large_duplicate", 9, 18
                    ),
                    _make_region(
                        fixture_dir / "small_functions.py", "python", "function", "large_duplicate", 9, 18
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
def test_match_counts(ruleset, path, threshold, similar_pairs, expected_regions):
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

    assert len(result.similar_pairs) == similar_pairs
    for region1, region2 in expected_regions:
        _assert_has_pair(result, region1, region2).similarity > threshold

