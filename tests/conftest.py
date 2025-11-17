from pathlib import Path
from tree_sitter_language_pack import get_parser
from whorl.models.ast import ParsedFile
from whorl.models.similarity import Region, SimilarRegionGroup, SimilarityResult
from whorl.pipeline.rules.engine import RuleEngine, build_default_rules


# Legacy fixture paths (for backward compatibility)
fixture_path1 = Path(__file__).parent / "fixtures" / "python" / "dataclass1.py"
fixture_path2 = Path(__file__).parent / "fixtures" / "python" / "dataclass2.py"
fixture_nested = Path(__file__).parent / "fixtures" / "python" / "nested_functions.py"
fixture_class_methods = Path(__file__).parent / "fixtures" / "python" / "class_with_methods.py"


def load_fixture(path: Path) -> bytes:
    """Load a fixture file as bytes."""
    with open(path, "rb") as f:
        return f.read()


def parse_fixture(path: Path, language: str) -> ParsedFile:
    """Parse a fixture file for any language.

    Args:
        path: Path to the fixture file
        language: Language name (e.g., "python", "javascript", "html")

    Returns:
        ParsedFile object with parsed tree
    """
    parser = get_parser(language)
    fixture = load_fixture(path)
    tree = parser.parse(fixture)
    return ParsedFile(
        path=path,
        language=language,
        tree=tree,
        source=fixture,
    )


def assert_regions_in_same_group(
    result: SimilarityResult, region1: Region, region2: Region
) -> SimilarRegionGroup:
    """Assert that region1 and region2 are in the same similarity group."""
    for group in result.similar_groups:
        if region1 in group.regions and region2 in group.regions:
            return group
    raise AssertionError(
        f"Regions ({region1}, {region2}) not found in same group ({result.similar_groups})"
    )


def parsed_fixture(path):
    """Legacy function for backward compatibility - parses Python files."""
    return parse_fixture(path, "python")


def default_rule_engine():
    """Create a default rule engine for tests."""
    rules = [rule for rule, _ in build_default_rules()]
    return RuleEngine(rules)
