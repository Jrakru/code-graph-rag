from __future__ import annotations

from pathlib import Path

import pytest

from codebase_rag.protocols import SourceType
from codebase_rag.services.file_classifier import FileClassifier


@pytest.fixture
def classifier() -> FileClassifier:
    return FileClassifier()


class TestSourceTypeEnum:
    def test_source_types_exist(self) -> None:
        assert SourceType.CODE == "code"
        assert SourceType.DOCUMENTATION == "documentation"
        assert SourceType.TEST == "test"
        assert SourceType.CONFIG == "config"
        assert SourceType.UNKNOWN == "unknown"


class TestFileClassifierCode:
    @pytest.mark.parametrize(
        "path",
        [
            Path("src/module.py"),
            Path("lib/utils.js"),
            Path("components/Button.tsx"),
            Path("core/engine.rs"),
            Path("main.go"),
            Path("app/Main.java"),
            Path("Player.cpp"),
        ],
    )
    def test_code_files_classified_as_code(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        assert classifier.classify(path) == SourceType.CODE

    def test_unknown_extension_returns_unknown(
        self, classifier: FileClassifier
    ) -> None:
        assert classifier.classify(Path("script.xyz")) == SourceType.UNKNOWN


class TestFileClassifierDocumentation:
    @pytest.mark.parametrize(
        "path",
        [
            Path("docs/guide.md"),
            Path("README.md"),
            Path("CHANGELOG.md"),
            Path("notes.rst"),
            Path("info.txt"),
            Path("doc/api.md"),
            Path("documentation/intro.md"),
        ],
    )
    def test_doc_files_classified_as_documentation(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        assert classifier.classify(path) == SourceType.DOCUMENTATION

    def test_doc_extension_without_doc_folder(self, classifier: FileClassifier) -> None:
        assert classifier.classify(Path("notes.md")) == SourceType.DOCUMENTATION


class TestFileClassifierTest:
    @pytest.mark.parametrize(
        "path",
        [
            Path("tests/test_module.py"),
            Path("test/unit_test.js"),
            Path("__tests__/component.test.tsx"),
            Path("spec/feature.spec.ts"),
            Path("test_something.py"),
            Path("module.test.js"),
        ],
    )
    def test_test_files_classified_as_test(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        assert classifier.classify(path) == SourceType.TEST


class TestFileClassifierConfig:
    @pytest.mark.parametrize(
        "path",
        [
            Path("config.yml"),
            Path("settings.yaml"),
            Path("package.json"),
            Path("pyproject.toml"),
            Path("setup.cfg"),
            Path("app.conf"),
            Path(".env"),
            Path("production.env"),
        ],
    )
    def test_config_files_classified_as_config(
        self, classifier: FileClassifier, path: Path
    ) -> None:
        assert classifier.classify(path) == SourceType.CONFIG


class TestFileClassifierEdgeCases:
    def test_test_folder_takes_precedence_over_doc_extension(
        self, classifier: FileClassifier
    ) -> None:
        assert classifier.classify(Path("tests/README.md")) == SourceType.TEST

    def test_test_folder_takes_precedence_over_config_extension(
        self, classifier: FileClassifier
    ) -> None:
        assert classifier.classify(Path("tests/config.json")) == SourceType.TEST

    def test_test_prefix_takes_precedence(self, classifier: FileClassifier) -> None:
        assert classifier.classify(Path("src/test_utils.py")) == SourceType.TEST

    def test_doc_folder_takes_precedence_over_code_extension(
        self, classifier: FileClassifier
    ) -> None:
        assert classifier.classify(Path("docs/example.py")) == SourceType.DOCUMENTATION

    def test_uppercase_extension_normalized(self, classifier: FileClassifier) -> None:
        assert classifier.classify(Path("INFO.MD")) == SourceType.DOCUMENTATION

    def test_uppercase_doc_name_normalized(self, classifier: FileClassifier) -> None:
        assert classifier.classify(Path("README.txt")) == SourceType.DOCUMENTATION

    def test_path_with_multiple_dots(self, classifier: FileClassifier) -> None:
        assert classifier.classify(Path("component.test.tsx")) == SourceType.TEST

    def test_nested_test_folder(self, classifier: FileClassifier) -> None:
        assert (
            classifier.classify(Path("src/tests/unit/test_api.py")) == SourceType.TEST
        )
