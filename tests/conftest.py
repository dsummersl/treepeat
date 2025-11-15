from pathlib import Path
from tree_sitter_language_pack import get_parser
from tssim.models.ast import ParsedFile
from tssim.pipeline.rules import RuleEngine
from tssim.pipeline.rules.engine import build_default_rules


fixture_path1 = Path(__file__).parent / "fixtures" / "python" / "dataclass1.py"
fixture_path2 = Path(__file__).parent / "fixtures" / "python" / "dataclass2.py"
fixture_nested = Path(__file__).parent / "fixtures" / "python" / "nested_functions.py"
fixture_class_methods = Path(__file__).parent / "fixtures" / "python" / "class_with_methods.py"


def load_fixture(path):
    with open(path, "rb") as f:
        return f.read()


def parsed_fixture(path):
    parser = get_parser("python")
    fixture = load_fixture(path)
    tree = parser.parse(fixture)
    return ParsedFile(
        path=path,
        language="python",
        tree=tree,
        source=fixture,
    )


def default_rule_engine():
    """Create a default rule engine for tests."""
    rules = [rule for rule, _ in build_default_rules()]
    return RuleEngine(rules)
