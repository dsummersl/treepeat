from pathlib import Path
from tree_sitter_language_pack import get_parser
from tssim.models.ast import ParsedFile


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
