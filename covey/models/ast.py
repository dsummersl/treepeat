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

    model_config = {"arbitrary_types_allowed": True}

    parsed_files: list[ParsedFile] = Field(
        default_factory=list, description="Successfully parsed files"
    )
    failed_files: dict[Path, str] = Field(
        default_factory=dict, description="Failed files with error messages"
    )

    @property
    def total_files(self) -> int:
        """Total number of files processed."""
        return len(self.parsed_files) + len(self.failed_files)

    @property
    def success_count(self) -> int:
        """Number of successfully parsed files."""
        return len(self.parsed_files)

    @property
    def failure_count(self) -> int:
        """Number of failed files."""
        return len(self.failed_files)
