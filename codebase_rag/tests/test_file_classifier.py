"""Tests for file classification by source type."""

from pathlib import Path

import pytest

from codebase_rag.services.file_classifier import FileClassifier, SourceType


@pytest.fixture
def classifier() -> FileClassifier:
    """Create a FileClassifier instance."""
    return FileClassifier()


class TestSourceTypeEnum:
    """Test SourceType enum values."""

    def test_source_types_exist(self) -> None:
        """All expected source types should be defined."""
        assert SourceType.CODE == "code"
        assert SourceType.DOCUMENTATION == "documentation"
        assert SourceType.TEST == "test"
        assert SourceType.CONFIG == "config"


class TestFileClassifierCode:
    """Test classification of code files."""

    @pytest.mark.parametrize(
        "path",
        [
            Path("src/main.py"),
            Path("lib/utils.js"),
            Path("app.ts"),
            Path("module.rs"),
            Path("handler.go"),
            Path("Service.java"),
            Path("widget.cpp"),
        ],
    )
    def test_code_files_classified_as_code(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        """Source code files should be classified as CODE."""
        assert classifier.classify(path) == SourceType.CODE

    def test_unknown_extension_defaults_to_code(
        self, classifier: FileClassifier
    ) -> None:
        """Unknown extensions should default to CODE."""
        assert classifier.classify(Path("script.xyz")) == SourceType.CODE


class TestFileClassifierDocumentation:
    """Test classification of documentation files."""

    @pytest.mark.parametrize(
        "path",
        [
            Path("README.md"),
            Path("docs/guide.md"),
            Path("CHANGELOG.md"),
            Path("LICENSE"),
            Path("CONTRIBUTING.md"),
            Path("documentation/api.rst"),
            Path("doc/tutorial.txt"),
            Path("notes.adoc"),
        ],
    )
    def test_doc_files_classified_as_documentation(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        """Documentation files should be classified as DOCUMENTATION."""
        assert classifier.classify(path) == SourceType.DOCUMENTATION

    def test_is_documentation_helper(self, classifier: FileClassifier) -> None:
        """is_documentation() should return True for doc files."""
        assert classifier.is_documentation(Path("README.md")) is True
        assert classifier.is_documentation(Path("main.py")) is False


class TestFileClassifierTest:
    """Test classification of test files."""

    @pytest.mark.parametrize(
        "path",
        [
            Path("test_main.py"),
            Path("tests/test_utils.py"),
            Path("main_test.py"),
            Path("__tests__/component.test.js"),
            Path("spec/model_spec.rb"),
            Path("src/utils.spec.ts"),
        ],
    )
    def test_test_files_classified_as_test(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        """Test files should be classified as TEST."""
        assert classifier.classify(path) == SourceType.TEST


class TestFileClassifierConfig:
    """Test classification of configuration files."""

    @pytest.mark.parametrize(
        "path",
        [
            Path("pyproject.toml"),
            Path("package.json"),
            Path("tsconfig.json"),
            Path("setup.py"),
            Path("setup.cfg"),
            Path(".gitignore"),
            Path(".env"),
            Path("Makefile"),
            Path("Dockerfile"),
            Path("docker-compose.yaml"),
            Path("config.yaml"),
            Path("settings.ini"),
        ],
    )
    def test_config_files_classified_as_config(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        """Configuration files should be classified as CONFIG."""
        assert classifier.classify(path) == SourceType.CONFIG


class TestFileClassifierEdgeCases:
    """Test edge cases and ambiguous files."""

    def test_test_in_docs_folder_is_documentation(
        self, classifier: FileClassifier
    ) -> None:
        """Test files in docs folder should be documentation if they have doc extension."""
        # .md files in any location are documentation
        assert (
            classifier.classify(Path("docs/test_guide.md")) == SourceType.DOCUMENTATION
        )

    def test_readme_in_tests_folder(self, classifier: FileClassifier) -> None:
        """README in tests folder should be documentation."""
        assert classifier.classify(Path("tests/README.md")) == SourceType.DOCUMENTATION

    def test_test_file_pattern_takes_precedence_over_extension(
        self, classifier: FileClassifier
    ) -> None:
        """Test patterns should identify test files regardless of location."""
        # test_ prefix indicates test file
        assert classifier.classify(Path("src/test_utils.py")) == SourceType.TEST

    def test_config_yaml_in_src_folder(self, classifier: FileClassifier) -> None:
        """YAML files should be classified as config."""
        assert classifier.classify(Path("src/config.yaml")) == SourceType.CONFIG
