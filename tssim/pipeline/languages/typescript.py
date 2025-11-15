from .javascript import JavaScriptConfig


class TypeScriptConfig(JavaScriptConfig):
    """Configuration for Javascript language."""

    def get_language_name(self) -> str:
        return "javascript"
