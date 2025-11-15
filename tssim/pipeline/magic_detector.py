"""File type detection using python-magic with fallback to extension-based detection."""

import logging
from pathlib import Path
from typing import Literal

import magic

logger = logging.getLogger(__name__)

# Type alias for supported languages (must match LANGUAGE_CONFIGS)
LanguageName = Literal[
    "python",
    "javascript",
    "typescript",
    "tsx",
    "jsx",
    "html",
    "css",
    "java",
    "sql",
    "bash",
    "rust",
    "ruby",
    "go",
    "csharp",
    "markdown",
]

# Mapping of MIME types to language names
# Only includes languages that exist in LANGUAGE_CONFIGS
MIME_TO_LANGUAGE: dict[str, LanguageName] = {
    # Python
    "text/x-python": "python",
    "text/x-script.python": "python",
    # JavaScript
    "text/javascript": "javascript",
    "application/javascript": "javascript",
    "application/x-javascript": "javascript",
    # TypeScript (note: magic might not detect these well, will rely on extension fallback)
    "text/x-typescript": "typescript",
    # HTML
    "text/html": "html",
    # CSS
    "text/css": "css",
    # Java
    "text/x-java": "java",
    "text/x-java-source": "java",
    # SQL
    "text/x-sql": "sql",
    "application/sql": "sql",
    # Bash/Shell
    "text/x-shellscript": "bash",
    "application/x-sh": "bash",
    "application/x-shellscript": "bash",
    # Rust
    "text/x-rust": "rust",
    # Ruby
    "text/x-ruby": "ruby",
    "text/x-script.ruby": "ruby",
    "application/x-ruby": "ruby",
    # Go
    "text/x-go": "go",
    # C#
    "text/x-csharp": "csharp",
    # Markdown
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
}

# File extension mapping as fallback
# Only includes extensions for languages that exist in LANGUAGE_CONFIGS
EXTENSION_TO_LANGUAGE: dict[str, LanguageName] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".java": "java",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".rs": "rust",
    ".rb": "ruby",
    ".go": "go",
    ".cs": "csharp",
    ".md": "markdown",
    ".markdown": "markdown",
}


def _detect_by_magic(file_path: Path) -> LanguageName | None:
    """Detect file type using python-magic."""
    try:
        mime = magic.from_file(str(file_path), mime=True)
        logger.debug(f"Detected MIME type for {file_path}: {mime}")

        # Map MIME type to language
        language = MIME_TO_LANGUAGE.get(mime)
        if language:
            logger.debug(f"Mapped MIME type {mime} to language {language}")
            return language

        return None
    except Exception as e:
        logger.debug(f"Magic detection failed for {file_path}: {e}")
        return None


def _detect_by_extension(file_path: Path) -> LanguageName | None:
    """Detect file type by extension."""
    suffix = file_path.suffix.lower()
    language = EXTENSION_TO_LANGUAGE.get(suffix)
    if language:
        logger.debug(f"Detected language {language} from extension {suffix}")
    return language


# Set of supported languages (must match LANGUAGE_CONFIGS)
SUPPORTED_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "tsx",
    "jsx",
    "html",
    "css",
    "java",
    "sql",
    "bash",
    "rust",
    "ruby",
    "go",
    "csharp",
    "markdown",
}


def _is_supported_language(language: str | None) -> bool:
    """Check if a language is supported."""
    if language is None:
        return False
    return language in SUPPORTED_LANGUAGES


def detect_language_with_magic(file_path: Path) -> LanguageName | None:
    """
    Detect programming language using python-magic with extension fallback.

    Only returns languages that exist in tssim.pipeline.languages.LANGUAGE_CONFIGS.

    Args:
        file_path: Path to the file to detect

    Returns:
        Language name if detected and supported, None otherwise
    """
    # First try magic detection
    language = _detect_by_magic(file_path)

    # If magic detection failed or returned unsupported language, try extension
    if not _is_supported_language(language):
        logger.debug(f"Magic detection failed or unsupported for {file_path}, trying extension")
        language = _detect_by_extension(file_path)

    # Validate the detected language is supported
    if _is_supported_language(language):
        logger.debug(f"Final detected language for {file_path}: {language}")
        return language

    logger.debug(f"No supported language detected for {file_path}")
    return None
