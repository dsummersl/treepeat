from pathlib import Path

from tssim.models.similarity import Region, SimilarRegionPair, SimilarityResult
from ..conftest import parsed_fixture
import pytest

from tssim.config import (
    LSHSettings,
    MinHashSettings,
    NormalizerSettings,
    PipelineSettings,
    ShingleSettings,
    set_settings,
)
from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
from tssim.pipeline.pipeline import run_pipeline
from tssim.pipeline.region_extraction import extract_all_regions
from tssim.pipeline.shingle import shingle_regions
from tssim.pipeline.normalizers.python import PythonImportNormalizer


fixture_class_with_methods = (
    Path(__file__).parent.parent / "fixtures" / "python" / "class_with_methods.py"
)
fixture_path4 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass4.py"
fixture_path5 = Path(__file__).parent.parent / "fixtures" / "python" / "dataclass5.py"

parsed_dataclass4 = parsed_fixture(fixture_path4)
parsed_dataclass5 = parsed_fixture(fixture_path5)

extracted_regions = extract_all_regions([parsed_dataclass4, parsed_dataclass5])


@pytest.mark.parametrize("normalizers", [[], [PythonImportNormalizer()]])
def test_dissimilar_files(normalizers):
    shingled_regions = shingle_regions(
        extracted_regions=extracted_regions,
        parsed_files=[parsed_dataclass4, parsed_dataclass5],
        normalizers=normalizers,
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
    """Assert that a pair (region1, region2) exists in the pairs iterable."""
    for pair in result.similar_pairs:
        if pair.region1 == region1 and pair.region2 == region2:
            return pair
    raise AssertionError(f"Pair ({region1}, {region2}) not found in pairs ({result.similar_pairs})")


def test_class_with_methods_has_similarities():
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"
    test_file = fixture_dir / "class_with_methods.py"

    result = run_pipeline(test_file)

    assert len(result.similar_pairs) == 3

    assert (
        _assert_has_pair(
            result,
            _make_region(fixture_class_with_methods, "python", "function", "method2", 13, 19),
            _make_region(fixture_class_with_methods, "python", "function", "method2", 40, 46),
        ).similarity
        > 0.9
    )

    assert (
        _assert_has_pair(
            result,
            _make_region(fixture_class_with_methods, "python", "function", "method3", 21, 27),
            _make_region(fixture_class_with_methods, "python", "function", "method3", 48, 54),
        ).similarity
        > 0.9
    )

    assert (
        _assert_has_pair(
            result,
            _make_region(fixture_class_with_methods, "python", "class", "ClassA", 4, 27),
            _make_region(fixture_class_with_methods, "python", "class", "ClassB", 30, 54),
        ).similarity
        > 0.7
    )


def test_higher_threshold():
    """Testing with an increased LSH threshold filters out less probable matches."""
    fixture_dir = Path(__file__).parent.parent / "fixtures" / "python"
    test_file = fixture_dir / "class_with_methods.py"

    set_settings(
        PipelineSettings(
            normalizer=NormalizerSettings(),
            shingle=ShingleSettings(),
            minhash=MinHashSettings(),
            lsh=LSHSettings(threshold=0.8),
        )
    )
    result = run_pipeline(test_file)

    assert len(result.similar_pairs) == 2

    assert (
        _assert_has_pair(
            result,
            _make_region(fixture_class_with_methods, "python", "function", "method2", 13, 19),
            _make_region(fixture_class_with_methods, "python", "function", "method2", 40, 46),
        ).similarity
        > 0.9
    )

    assert (
        _assert_has_pair(
            result,
            _make_region(fixture_class_with_methods, "python", "function", "method3", 21, 27),
            _make_region(fixture_class_with_methods, "python", "function", "method3", 48, 54),
        ).similarity
        > 0.9
    )
