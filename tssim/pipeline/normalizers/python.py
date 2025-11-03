"""Python-specific normalizers."""

import logging
from typing import cast

from tree_sitter import Node, Tree
from tree_sitter_language_pack import get_parser

from tssim.config import get_settings
from tssim.models.ast import ParsedFile
from tssim.pipeline.normalizers import Normalizer

logger = logging.getLogger(__name__)


class PythonImportNormalizer(Normalizer):
    """Removes import statements from Python source code.

    This normalizer removes both 'import' and 'from...import' statements
    to focus on the actual implementation rather than dependencies.
    """

    def should_apply(self, parsed_file: ParsedFile) -> bool:
        """Check if this is a Python file and import ignoring is enabled."""
        settings = get_settings()
        return parsed_file.language == "python" and settings.python.ignore_imports

    def normalize(self, parsed_file: ParsedFile) -> ParsedFile:
        """Remove import statements from the Python AST.

        Args:
            parsed_file: The parsed Python file

        Returns:
            A new ParsedFile with import statements removed
        """
        if not self.should_apply(parsed_file):
            return parsed_file

        # Find all import nodes
        import_nodes = self._find_import_nodes(parsed_file.root_node)

        if not import_nodes:
            logger.debug("No import statements found in %s", parsed_file.path)
            return parsed_file

        # Remove import statements from source code
        new_source = self._remove_nodes_from_source(parsed_file.source, import_nodes)

        # Re-parse the modified source
        parser = get_parser("python")
        new_tree = parser.parse(new_source)

        # Validate the new tree
        if new_tree.root_node.has_error:
            logger.warning(
                "Normalization introduced parse errors in %s, returning original",
                parsed_file.path,
            )
            return parsed_file

        logger.debug(
            "Removed %d import statement(s) from %s", len(import_nodes), parsed_file.path
        )

        # Return a new ParsedFile with the modified source and tree
        return ParsedFile(
            path=parsed_file.path,
            language=parsed_file.language,
            tree=new_tree,
            source=new_source,
        )

    def _find_import_nodes(self, root_node: Node) -> list[Node]:
        """Find all import nodes in the AST.

        Args:
            root_node: The root node of the AST

        Returns:
            List of import nodes (import_statement and import_from_statement)
        """
        import_nodes: list[Node] = []

        def visit(node: Node) -> None:
            if node.type in ("import_statement", "import_from_statement"):
                import_nodes.append(node)
            # Continue visiting children
            for child in node.children:
                visit(child)

        visit(root_node)
        return import_nodes

    def _remove_nodes_from_source(self, source: bytes, nodes: list[Node]) -> bytes:
        """Remove nodes from source code by their byte ranges.

        Args:
            source: The original source code
            nodes: List of nodes to remove

        Returns:
            Modified source code with nodes removed
        """
        if not nodes:
            return source

        # Sort nodes by start position (in reverse to remove from end to start)
        sorted_nodes = sorted(nodes, key=lambda n: n.start_byte, reverse=True)

        # Convert bytes to a mutable list for easier manipulation
        source_list = bytearray(source)

        for node in sorted_nodes:
            # Find the full line range including the newline
            start_byte = node.start_byte
            end_byte = node.end_byte

            # Find the start of the line
            while start_byte > 0 and source_list[start_byte - 1] not in (
                ord(b"\n"),
                ord(b"\r"),
            ):
                start_byte -= 1

            # Find the end of the line (include the newline)
            while end_byte < len(source_list) and source_list[end_byte] not in (
                ord(b"\n"),
                ord(b"\r"),
            ):
                end_byte += 1

            # Include the newline character(s)
            if end_byte < len(source_list):
                if source_list[end_byte] == ord(b"\r") and end_byte + 1 < len(
                    source_list
                ):
                    if source_list[end_byte + 1] == ord(b"\n"):
                        end_byte += 2  # \r\n
                    else:
                        end_byte += 1  # \r
                elif source_list[end_byte] == ord(b"\n"):
                    end_byte += 1  # \n

            # Remove the line
            del source_list[start_byte:end_byte]

        return bytes(source_list)
