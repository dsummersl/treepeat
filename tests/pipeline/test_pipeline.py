from pathlib import Path

from treepeat.models.similarity import Region
from ..conftest import parsed_fixture, assert_regions_in_same_group
import pytest

from treepeat.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from treepeat.pipeline.lsh_stage import detect_similarity
from treepeat.pipeline.minhash_stage import compute_region_signatures
from treepeat.pipeline.pipeline import run_pipeline
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.shingle import shingle_regions
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
    result = detect_similarity(signatures, 0.5, shingled_regions)
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


classA_region = _make_region(fixture_class_with_methods, "python", "class_definition", "ClassA", 4, 27)
classB_region = _make_region(fixture_class_with_methods, "python", "class_definition", "ClassB", 30, 54)


python_fixtures = Path(__file__).parent.parent / "fixtures" / "python"
class_with_methods_file = python_fixtures / "class_with_methods.py"

css_fixtures = Path(__file__).parent.parent.parent / "fixtures" / "css"
fixture_comprehensive = css_fixtures / "comprehensive.css"
fixture_comprehensive_deleted_region = css_fixtures / "comprehensive-slight-mod.css"


@pytest.mark.parametrize(
    "ruleset, path, similarity_threshold, similar_groups, expected_regions",
    [
        ("none", css_fixtures, 1.0, 0, []),
        ("none", class_with_methods_file, 0.1, 1, []),
        ("none", class_with_methods_file, 0.9, 3, []),
        ("default", class_with_methods_file, 0.1, 1, []),
        ("default", class_with_methods_file, 0.3, 2, []),
        ("default", class_with_methods_file, 0.5, 3, [(classA_region, classB_region)]),
        (
            "none",
            python_fixtures,
            0.7,
            5,
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        python_fixtures / "small_functions_b.py",
                        "python",
                        "function_definition",
                        "large_duplicate",
                        9,
                        18,
                    ),
                    _make_region(
                        python_fixtures / "small_functions.py",
                        "python",
                        "function_definition",
                        "large_duplicate",
                        9,
                        18,
                    ),
                ),
                # Similar functions across dataclass files
                (
                    _make_region(
                        python_fixtures / "dataclass1.py",
                        "python",
                        "function_definition",
                        "my_adapted_one",
                        21,
                        26,
                    ),
                    _make_region(
                        python_fixtures / "dataclass2.py", "python", "function_definition", "one", 2, 7
                    ),
                ),
            ],
        ),
        (
            "none",
            python_fixtures,
            0.8,
            5,
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        python_fixtures / "small_functions_b.py",
                        "python",
                        "function_definition",
                        "large_duplicate",
                        9,
                        18,
                    ),
                    _make_region(
                        python_fixtures / "small_functions.py",
                        "python",
                        "function_definition",
                        "large_duplicate",
                        9,
                        18,
                    ),
                ),
                # Duplicate methods within same file (non-overlapping)
                (
                    _make_region(
                        fixture_class_with_methods, "python", "function_definition", "method2", 13, 19
                    ),
                    _make_region(
                        fixture_class_with_methods, "python", "function_definition", "method2", 40, 46
                    ),
                ),
                (
                    _make_region(
                        fixture_class_with_methods, "python", "function_definition", "method3", 21, 27
                    ),
                    _make_region(
                        fixture_class_with_methods, "python", "function_definition", "method3", 48, 54
                    ),
                ),
            ],
        ),
        (
            "none",
            python_fixtures,
            0.9,
            4,
            [
                # Cross-file duplicate functions
                (
                    _make_region(
                        python_fixtures / "small_functions_b.py",
                        "python",
                        "function_definition",
                        "large_duplicate",
                        9,
                        18,
                    ),
                    _make_region(
                        python_fixtures / "small_functions.py",
                        "python",
                        "function_definition",
                        "large_duplicate",
                        9,
                        18,
                    ),
                ),
                # Duplicate method2 within same file (non-overlapping)
                (
                    _make_region(
                        fixture_class_with_methods, "python", "function_definition", "method2", 13, 19
                    ),
                    _make_region(
                        fixture_class_with_methods, "python", "function_definition", "method2", 40, 46
                    ),
                ),
            ],
        ),
    ],
)
def test_match_counts(ruleset, path, similarity_threshold, similar_groups, expected_regions):
    """Testing with different rulesets and LSH thresholds."""
    set_settings(
        PipelineSettings(
            rules=RulesSettings(ruleset=ruleset),
            shingle=ShingleSettings(),
            minhash=MinHashSettings(),
            lsh=LSHSettings(similarity_percent=similarity_threshold),
        )
    )
    result = run_pipeline(path)

    assert len(result.similar_groups) == similar_groups
    for region1, region2 in expected_regions:
        assert_regions_in_same_group(result, region1, region2).similarity > similarity_threshold
