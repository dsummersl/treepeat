from tree_sitter_language_pack import SupportedLanguage

from .base import LanguageConfig
from .astro import AstroConfig
from .python import PythonConfig
from .javascript import JavaScriptConfig
from .typescript import TypeScriptConfig
from .html import HTMLConfig
from .css import CSSConfig
from .sql import SQLConfig
from .bash import BashConfig
from .markdown import MarkdownConfig
from .go import GoConfig
from .java import JavaConfig
from .kotlin import KotlinConfig
from .rust import RustConfig

# Registry mapping language names to their configurations
LANGUAGE_CONFIGS: dict[SupportedLanguage, LanguageConfig] = {
    "astro": AstroConfig(),
    "bash": BashConfig(),
    "css": CSSConfig(),
    "go": GoConfig(),
    "html": HTMLConfig(),
    "java": JavaConfig(),
    "javascript": JavaScriptConfig(),
    "kotlin": KotlinConfig(),
    "markdown": MarkdownConfig(),
    "python": PythonConfig(),
    "rust": RustConfig(),
    "sql": SQLConfig(),
    "typescript": TypeScriptConfig(),
}

LANGUAGE_EXTENSIONS: dict[SupportedLanguage, list[str]] = {
    "astro": [".astro"],
    "bash": [".sh", ".bash"],
    "css": [".css"],
    "go": [".go"],
    "html": [".html", ".htm"],
    "java": [".java"],
    "javascript": [".js", ".jsx"],
    "kotlin": [".kt", ".kts"],
    "markdown": [".md", ".markdown"],
    "python": [".py"],
    "rust": [".rs"],
    "sql": [".sql"],
    "typescript": [".ts", ".tsx"],
}

__all__ = [
    "LanguageConfig",
    "LANGUAGE_CONFIGS",
    "PythonConfig",
    "JavaScriptConfig",
    "TypeScriptConfig",
    "HTMLConfig",
    "CSSConfig",
    "JavaConfig",
    "KotlinConfig",
    "SQLConfig",
    "BashConfig",
    "RustConfig",
    "GoConfig",
    "MarkdownConfig",
]
