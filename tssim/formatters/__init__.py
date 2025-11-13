"""Output formatters for tssim results."""

from tssim.formatters.sarif import format_as_sarif
from tssim.formatters.json import format_as_json

__all__ = ["format_as_sarif", "format_as_json"]
