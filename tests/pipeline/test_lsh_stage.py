from ..conftest import parsed_fixture, fixture_path1, fixture_path2

from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
from tssim.pipeline.region_extraction import extract_all_regions
from tssim.pipeline.rules import RuleEngine
from tssim.pipeline.shingle import shingle_regions


def test_detect_similarity_1():
    """Test similarity regions from dataclass1.py fixture."""
    parsed_dataclass1 = parsed_fixture(fixture_path1)
    shingled_regions = shingle_regions(
        extracted_regions=extract_all_regions([parsed_dataclass1]),
        parsed_files=[parsed_dataclass1],
        rule_engine=RuleEngine([]),
    )
    signatures = compute_region_signatures(shingled_regions)
    result = detect_similarity(signatures, threshold=0.1)

    assert len(result.similar_pairs) == 1
    assert result.similar_pairs[0].similarity > 0.4


def test_detect_similarity_2():
    """Test similarity regions from dataclass1.py fixture."""
    parsed_dataclass2 = parsed_fixture(fixture_path2)
    shingled_regions = shingle_regions(
        extracted_regions=extract_all_regions([parsed_dataclass2]),
        parsed_files=[parsed_dataclass2],
        rule_engine=RuleEngine([]),
    )
    signatures = compute_region_signatures(shingled_regions)
    result = detect_similarity(signatures, threshold=0.7)

    assert len(result.similar_pairs) == 1
    assert result.similar_pairs[0].similarity > 0.7
