

from pathlib import Path

from pydantic import BaseModel, Field
from tree_sitter import Node, Tree


class ParsedFile(BaseModel):


    model_config = {"arbitrary_types_allowed": True}

    path: Path = Field(description="Path to the source file")
    language: str = Field(description="Programming language detected")
    tree: Tree = Field(description="Tree-sitter AST")
    source: bytes = Field(description="Original source code bytes")

    @property
    def root_node(self) -> Node:

        return self.tree.root_node


class ParseResult(BaseModel):


    parsed_files: list[ParsedFile] = Field(
        default_factory=list, description="Successfully parsed files"
    )

    @property
    def total_files(self) -> int:

        return len(self.parsed_files)

    @property
    def success_count(self) -> int:

        return len(self.parsed_files)
