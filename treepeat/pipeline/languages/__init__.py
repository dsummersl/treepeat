from .astro import AstroConfig
from .base import LanguageConfig
from .bash import BashConfig
from .css import CSSConfig
from .go import GoConfig
from .html import HTMLConfig
from .java import JavaConfig
from .javascript import JavaScriptConfig
from .jsx import JsxConfig
from .kotlin import KotlinConfig
from .markdown import MarkdownConfig
from .python import PythonConfig
from .rust import RustConfig
from .sql import SQLConfig
from .tsx import TsxConfig
from .typescript import TypeScriptConfig

# Registry mapping language names to their configurations
LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "astro": AstroConfig(),
    "bash": BashConfig(),
    "css": CSSConfig(),
    "go": GoConfig(),
    "html": HTMLConfig(),
    "java": JavaConfig(),
    "javascript": JavaScriptConfig(),
    "jsx": JsxConfig(),
    "kotlin": KotlinConfig(),
    "markdown": MarkdownConfig(),
    "python": PythonConfig(),
    "rust": RustConfig(),
    "sql": SQLConfig(),
    "tsx": TsxConfig(),
    "typescript": TypeScriptConfig(),
}

LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "astro": [".astro"],
    "bash": [".sh", ".bash"],
    "css": [".css"],
    "go": [".go"],
    "html": [".html", ".htm"],
    "java": [".java"],
    "javascript": [".js"],
    "jsx": [".jsx"],
    "kotlin": [".kt", ".kts"],
    "markdown": [".md", ".markdown"],
    "python": [".py"],
    "rust": [".rs"],
    "sql": [".sql"],
    "tsx": [".tsx"],
    "typescript": [".ts"],
}

# Languages that share a tree-sitter grammar with another language.
# JSX is parsed with the JavaScript grammar since no separate jsx grammar exists.
GRAMMAR_ALIASES: dict[str, str] = {
    "jsx": "javascript",
}


def get_grammar(language: str) -> str:
    """Return the tree-sitter grammar name for a language."""
    return GRAMMAR_ALIASES.get(language, language)


__all__ = [
    "LanguageConfig",
    "LANGUAGE_CONFIGS",
    "LANGUAGE_EXTENSIONS",
    "GRAMMAR_ALIASES",
    "get_grammar",
    "PythonConfig",
    "JavaScriptConfig",
    "JsxConfig",
    "TypeScriptConfig",
    "TsxConfig",
    "HTMLConfig",
    "CSSConfig",
    "JavaConfig",
    "KotlinConfig",
    "SQLConfig",
    "BashConfig",
    "RustConfig",
    "GoConfig",
    "MarkdownConfig",
    "AstroConfig",
]
