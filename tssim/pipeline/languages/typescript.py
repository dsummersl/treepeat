"""TypeScript language configuration."""

from .javascript import JavaScriptConfig


class TypeScriptConfig(JavaScriptConfig):
    """Configuration for TypeScript language (inherits from JavaScript)."""

    def get_language_name(self) -> str:
        return "typescript"
