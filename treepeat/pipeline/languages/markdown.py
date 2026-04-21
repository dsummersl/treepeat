from tree_sitter import Node

from treepeat.pipeline.rules.models import Rule

from .base import LanguageConfig, RegionExtractionRule


def _resolve_code_block_language(node: Node, source: bytes) -> str:
    """Return the language declared in a fenced_code_block's info_string.

    Markdown fenced code blocks may begin with an info string that names the
    language of the block (e.g. ` ```python `).  This callable is used as the
    dynamic ``target_language`` for the ``fenced_code_block`` region extraction
    rule so that each block is injected and shingled using its own language's
    normalization rules.

    Returns an empty string when no language tag is present; the injection
    mechanism treats an empty string as "no injection".
    """
    for child in node.children:
        if child.type == "info_string":
            lang_text = source[child.start_byte : child.end_byte].decode("utf-8", errors="ignore").strip()
            # Language identifiers may have extra text (e.g. "python title='foo'")
            return lang_text.split()[0].lower() if lang_text else ""
    return ""


class MarkdownConfig(LanguageConfig):
    """Configuration for Markdown language."""

    def get_language_name(self) -> str:
        return "markdown"

    def get_default_rules(self) -> list[Rule]:
        return []

    def get_loose_rules(self) -> list[Rule]:
        return []

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(
                query="[(atx_heading) (setext_heading) (section)] @region",
                label="heading",
            ),
            # Fenced code blocks are injected into their declared language so
            # the shingler produces language-specific shingles.  Blocks with no
            # language tag fall back to opaque shingling (empty string returned
            # by _resolve_code_block_language → injection skipped).
            RegionExtractionRule(
                query="(fenced_code_block) @region",
                label="code_block",
                target_language=_resolve_code_block_language,
                content_query="(code_fence_content) @content",
            ),
            RegionExtractionRule.from_node_type("indented_code_block"),
        ]
