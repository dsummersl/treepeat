"""AST domain models."""

from pathlib import Path

from pydantic import BaseModel, Field
from tree_sitter import Node, Tree


class ParsedFile(BaseModel):
    """Represents a successfully parsed source file."""

    model_config = {"arbitrary_types_allowed": True}

    path: Path = Field(description="Path to the source file")
    language: str = Field(description="Programming language detected")
    tree: Tree = Field(description="Tree-sitter AST")
    source: bytes = Field(description="Original source code bytes")

    @property
    def root_node(self) -> Node:
        """Get the root node of the AST."""
        return self.tree.root_node


class ParseResult(BaseModel):
    """Result of parsing one or more files."""

    parsed_files: list[ParsedFile] = Field(
        default_factory=list, description="Successfully parsed files"
    )

    @property
    def total_files(self) -> int:
        """Total number of files processed."""
        return len(self.parsed_files)

    @property
    def success_count(self) -> int:
        """Number of successfully parsed files."""
        return len(self.parsed_files)
