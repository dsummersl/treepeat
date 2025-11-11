from pathlib import Path
from ..conftest import parsed_fixture

from tssim.pipeline.lsh_stage import detect_similarity
from tssim.pipeline.minhash_stage import compute_region_signatures
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
    print(f"\nClass regions:")
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
