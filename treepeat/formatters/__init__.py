"""Output formatters for whorl results."""

from treepeat.formatters.sarif import format_as_sarif
from treepeat.formatters.json import format_as_json

__all__ = ["format_as_sarif", "format_as_json"]
