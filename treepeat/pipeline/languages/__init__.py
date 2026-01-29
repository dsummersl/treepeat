from tree_sitter_language_pack import SupportedLanguage

from .base import LanguageConfig
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

# Registry mapping language names to their configurations
LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "python": PythonConfig(),
    "javascript": JavaScriptConfig(),
    "typescript": TypeScriptConfig(),
    "tsx": TypeScriptConfig(),
    "jsx": JavaScriptConfig(),
    "html": HTMLConfig(),
    "css": CSSConfig(),
    "sql": SQLConfig(),
    "bash": BashConfig(),
    "markdown": MarkdownConfig(),
    "go": GoConfig(),
    "java": JavaConfig(),
    "kotlin": KotlinConfig(),
}

LANGUAGE_EXTENSIONS: dict[SupportedLanguage, list[str]] = {
    "python": [".py"],
    "javascript": [".js", ".jsx"],
    "typescript": [".ts", ".tsx"],
    "html": [".html", ".htm"],
    "css": [".css"],
    "sql": [".sql"],
    "bash": [".sh", ".bash"],
    "markdown": [".md", ".markdown"],
    "go": [".go"],
    "java": [".java"],
    "kotlin": [".kt", ".kts"],
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
    "RubyConfig",
    "GoConfig",
    "CSharpConfig",
    "MarkdownConfig",
]
