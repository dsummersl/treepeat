from tree_sitter_language_pack import SupportedLanguage

from .astro import AstroConfig
from .base import LanguageConfig
from .bash import BashConfig
from .css import CSSConfig
from .go import GoConfig
from .html import HTMLConfig
from .java import JavaConfig
from .javascript import JavaScriptConfig
from .kotlin import KotlinConfig
from .markdown import MarkdownConfig
from .python import PythonConfig
from .rust import RustConfig
from .sql import SQLConfig
from .tsx import TsxConfig
from .typescript import TypeScriptConfig

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
    "tsx": TsxConfig(),
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
    "tsx": [".tsx"],
    "typescript": [".ts"],
}

__all__ = [
    "LanguageConfig",
    "LANGUAGE_CONFIGS",
    "PythonConfig",
    "JavaScriptConfig",
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
