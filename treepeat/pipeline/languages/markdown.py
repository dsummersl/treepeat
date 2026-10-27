import logging

from tree_sitter import Node

from treepeat.pipeline.rules.models import Rule

from .base import LanguageConfig, RegionExtractionRule

logger = logging.getLogger(__name__)


_INFO_STRING_ALIASES = {
    "yml": "yaml",
    "ts": "typescript",
    "js": "javascript",
    "py": "python",
    "sh": "bash",
    "shell": "bash",
    "rs": "rust",
    "kt": "kotlin",
    "md": "markdown",
}


def _resolve_code_block_language(node: Node, source: bytes) -> str:

    for child in node.children:
        if child.type == "info_string":
            lang_text = source[child.start_byte : child.end_byte].decode("utf-8", errors="ignore").strip()
            if not lang_text:
                return ""

            lang = lang_text.split()[0].lower()
            lang = _INFO_STRING_ALIASES.get(lang, lang)
            from treepeat.pipeline.languages import LANGUAGE_CONFIGS

            if lang not in LANGUAGE_CONFIGS:
                logger.warning(
                    "Markdown code block declares unsupported language %r; skipping injection",
                    lang,
                )
                return ""
            return lang
    return ""


class MarkdownConfig(LanguageConfig):
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
            RegionExtractionRule(
                query="(fenced_code_block) @region",
                label="code_block",
                target_language=_resolve_code_block_language,
                content_query="(code_fence_content) @content",
            ),
            RegionExtractionRule(
                query="(indented_code_block) @region",
                label="code_block",
            ),
        ]
