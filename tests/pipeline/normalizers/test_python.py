"""Tests for Python normalizers."""


import pytest
from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from tssim.models.normalization import SkipNode
from tssim.pipeline.normalizers.python import PythonImportNormalizer


@pytest.fixture
def normalizer():
    """Create a PythonImportNormalizer instance."""
    return PythonImportNormalizer()


@pytest.fixture
def parser():
    """Get a Python parser."""
    return get_parser("python")


def parse_source(source: str, parser) -> tuple[Node, bytes]:
    """Helper to parse source code.

    Args:
        source: Python source code as a string
        parser: Tree-sitter parser

    Returns:
        Tuple of (root_node, source_bytes)
    """
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    return tree.root_node, source_bytes


def find_node_by_type(node: Node, node_type: str) -> Node | None:
    """Find first node of given type in tree.

    Args:
        node: Root node to search from
        node_type: Node type to find

    Returns:
        First matching node or None
    """
    if node.type == node_type:
        return node
    for child in node.children:
        result = find_node_by_type(child, node_type)
        if result:
            return result
    return None


class TestPythonImportNormalizer:
    """Tests for PythonImportNormalizer."""

    def test_skip_import_statement_python(self, normalizer, parser):
        """Test that import_statement nodes are skipped for Python."""
        root, source = parse_source("import os\n", parser)
        import_node = find_node_by_type(root, "import_statement")

        assert import_node is not None
        with pytest.raises(SkipNode):
            normalizer.normalize_node(import_node, "import_statement", None, "python", source)

    def test_skip_import_from_statement_python(self, normalizer, parser):
        """Test that import_from_statement nodes are skipped for Python."""
        root, source = parse_source("from os import path\n", parser)
        import_node = find_node_by_type(root, "import_from_statement")

        assert import_node is not None
        with pytest.raises(SkipNode):
            normalizer.normalize_node(import_node, "import_from_statement", None, "python", source)

    def test_no_change_for_non_import_python(self, normalizer, parser):
        """Test that non-import nodes return None (no change)."""
        root, source = parse_source("def foo(): pass\n", parser)
        func_node = find_node_by_type(root, "function_definition")

        assert func_node is not None
        result = normalizer.normalize_node(func_node, "function_definition", None, "python", source)
        assert result is None

    def test_no_change_for_non_python_language(self, normalizer, parser):
        """Test that non-Python files return None."""
        root, source = parse_source("import os\n", parser)
        import_node = find_node_by_type(root, "import_statement")

        assert import_node is not None
        result = normalizer.normalize_node(
            import_node, "import_statement", None, "javascript", source
        )
        assert result is None

    def test_no_change_for_identifier(self, normalizer, parser):
        """Test that identifier nodes are not affected."""
        root, source = parse_source("x = 5\n", parser)
        identifier_node = find_node_by_type(root, "identifier")

        assert identifier_node is not None
        result = normalizer.normalize_node(identifier_node, "identifier", "x", "python", source)
        assert result is None

    def test_skip_multiline_import(self, normalizer, parser):
        """Test that multiline imports are skipped."""
        source_code = """from typing import (
    List,
    Dict
)
"""
        root, source = parse_source(source_code, parser)
        import_node = find_node_by_type(root, "import_from_statement")

        assert import_node is not None
        with pytest.raises(SkipNode):
            normalizer.normalize_node(import_node, "import_from_statement", None, "python", source)
