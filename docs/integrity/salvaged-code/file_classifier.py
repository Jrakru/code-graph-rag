"""File classification by source type."""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import ClassVar


class SourceType(StrEnum):
    """Classification of source files."""

    CODE = "code"
    DOCUMENTATION = "documentation"
    TEST = "test"
    CONFIG = "config"


class FileClassifier:
    """Classifies files by source type based on extension and path patterns."""

    DOC_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {".md", ".rst", ".txt", ".adoc", ".asciidoc"}
    )

    DOC_PATTERNS: ClassVar[tuple[str, ...]] = (
        "README",
        "CHANGELOG",
        "LICENSE",
        "CONTRIBUTING",
        "docs/",
        "documentation/",
        "doc/",
    )

    TEST_PATTERNS: ClassVar[tuple[str, ...]] = (
        "test_",
        "_test.",
        ".test.",
        "tests/",
        "__tests__/",
        "spec/",
        ".spec.",
    )

    CONFIG_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}
    )

    CONFIG_NAMES: ClassVar[frozenset[str]] = frozenset(
        {
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "package.json",
            "tsconfig.json",
            "cargo.toml",
            ".gitignore",
            ".env",
            "Makefile",
            "Dockerfile",
            "docker-compose.yaml",
            "docker-compose.yml",
        }
    )

    def classify(self, path: Path) -> SourceType:
        """Classify a file path into a source type.

        Args:
            path: Path to the file (can be relative or absolute)

        Returns:
            SourceType indicating the file's classification
        """
        name = path.name
        suffix = path.suffix.lower()
        path_str = str(path)

        if self._is_doc_file(name, suffix, path_str):
            return SourceType.DOCUMENTATION

        if self._is_test_file(path_str):
            return SourceType.TEST

        if self._is_config_file(name, suffix):
            return SourceType.CONFIG

        return SourceType.CODE

    def is_documentation(self, path: Path) -> bool:
        """Quick check if file is documentation.

        Args:
            path: Path to check

        Returns:
            True if the file is documentation
        """
        return self.classify(path) == SourceType.DOCUMENTATION

    def _is_doc_file(self, name: str, suffix: str, path_str: str) -> bool:
        """Check if file is documentation."""
        if suffix in self.DOC_EXTENSIONS:
            return True
        return any(
            pattern in path_str or pattern in name.upper()
            for pattern in self.DOC_PATTERNS
        )

    def _is_test_file(self, path_str: str) -> bool:
        """Check if file is a test file."""
        return any(pattern in path_str for pattern in self.TEST_PATTERNS)

    def _is_config_file(self, name: str, suffix: str) -> bool:
        """Check if file is a config file."""
        if name in self.CONFIG_NAMES:
            return True
        return suffix in self.CONFIG_EXTENSIONS
