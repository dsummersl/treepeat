"""Language-specific configuration for tree-sitter parsing and region extraction."""

from .base import LanguageConfig
from .python import PythonConfig
from .javascript import JavaScriptConfig
from .typescript import TypeScriptConfig
from .html import HTMLConfig
from .css import CSSConfig
from .java import JavaConfig
from .sql import SQLConfig
from .bash import BashConfig
from .rust import RustConfig
from .ruby import RubyConfig
from .go import GoConfig
from .csharp import CSharpConfig
from .markdown import MarkdownConfig

# Registry mapping language names to their configurations
LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "python": PythonConfig(),
    "javascript": JavaScriptConfig(),
    "typescript": TypeScriptConfig(),
    "tsx": TypeScriptConfig(),
    "jsx": JavaScriptConfig(),
    "html": HTMLConfig(),
    "css": CSSConfig(),
    "java": JavaConfig(),
    "sql": SQLConfig(),
    "bash": BashConfig(),
    "rust": RustConfig(),
    "ruby": RubyConfig(),
    "go": GoConfig(),
    "csharp": CSharpConfig(),
    "markdown": MarkdownConfig(),
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
    "SQLConfig",
    "BashConfig",
    "RustConfig",
    "RubyConfig",
    "GoConfig",
    "CSharpConfig",
    "MarkdownConfig",
]
