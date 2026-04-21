from tree_sitter_language_pack import SupportedLanguage

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
from .typescript import TypeScriptConfig

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
    "rust": RustConfig(),
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
    "rust": [".rs"],
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
