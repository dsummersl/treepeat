"""Models for normalization."""

from pydantic import BaseModel, Field


class NodeRepresentation(BaseModel):
    """Representation of a node for shingling.

    Each node has a name (its type) and an optional value (for leaf nodes).
    """

    name: str = Field(description="Node type name (e.g., 'function_definition', 'identifier')")
    value: str | None = Field(
        default=None, description="Node value (e.g., 'my_func', '42') or None for structural nodes"
    )

    def __str__(self) -> str:
        """Format as string for shingle representation."""
        if self.value:
            return f"{self.name}({self.value})"
        return self.name


class NormalizationResult(BaseModel):
    """Result of applying a normalizer to a node.

    Either field can be None to indicate no change should be made.
    """

    name: str | None = Field(default=None, description="New node name, or None to keep original")
    value: str | None = Field(default=None, description="New node value, or None to keep original")


class SkipNode(Exception):
    """Exception raised by normalizers to indicate a node should be skipped.

    When raised during normalization, the shingling process will skip
    this node and its entire subtree.
    """

    pass
