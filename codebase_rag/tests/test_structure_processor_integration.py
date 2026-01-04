from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codebase_rag import constants as cs
from codebase_rag.models import LanguageSpec
from codebase_rag.parsers.structure_processor import StructureProcessor
from codebase_rag.services.file_classifier import FileClassifier, SourceType


def _make_mock_queries(
    package_indicators: tuple[str, ...],
) -> dict[str, MagicMock | LanguageSpec | None]:
    return {
        "functions": None,
        "classes": None,
        "calls": None,
        "imports": None,
        "locals": None,
        "config": LanguageSpec(
            language=cs.SupportedLanguage.PYTHON,
            file_extensions=(".py",),
            function_node_types=(),
            class_node_types=(),
            module_node_types=(),
            package_indicators=package_indicators,
        ),
        "language": MagicMock(),
        "parser": MagicMock(),
    }


@pytest.fixture
def mock_language_queries() -> dict[
    cs.SupportedLanguage, dict[str, MagicMock | LanguageSpec | None]
]:
    return {cs.SupportedLanguage.PYTHON: _make_mock_queries(("__init__.py",))}


def _get_file_node_properties(mock_ingestor: MagicMock) -> dict[str, str]:
    file_calls = [
        call
        for call in mock_ingestor.ensure_node_batch.call_args_list
        if call[0][0] == cs.NodeLabel.FILE
    ]
    assert len(file_calls) == 1
    return file_calls[0][0][1]


def _process_file(
    temp_repo: Path,
    mock_ingestor: MagicMock,
    mock_language_queries: dict[
        cs.SupportedLanguage, dict[str, MagicMock | LanguageSpec | None]
    ],
    file_path: Path,
    file_classifier: FileClassifier | None = None,
) -> dict[str, str]:
    processor = StructureProcessor(
        ingestor=mock_ingestor,
        repo_path=temp_repo,
        project_name="test_project",
        queries=mock_language_queries,
        file_classifier=file_classifier,
    )
    processor.process_generic_file(file_path, file_path.name)
    return _get_file_node_properties(mock_ingestor)


def test_file_nodes_include_source_type(
    temp_repo: Path,
    mock_ingestor: MagicMock,
    mock_language_queries: dict[
        cs.SupportedLanguage, dict[str, MagicMock | LanguageSpec | None]
    ],
) -> None:
    file_path = temp_repo / "README.md"
    file_path.touch()

    props = _process_file(
        temp_repo,
        mock_ingestor,
        mock_language_queries,
        file_path,
        file_classifier=FileClassifier(),
    )

    assert cs.KEY_SOURCE_TYPE in props


def test_source_type_classifies_test_files(
    temp_repo: Path,
    mock_ingestor: MagicMock,
    mock_language_queries: dict[
        cs.SupportedLanguage, dict[str, MagicMock | LanguageSpec | None]
    ],
) -> None:
    file_path = temp_repo / "tests" / "test_example.py"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    props = _process_file(
        temp_repo,
        mock_ingestor,
        mock_language_queries,
        file_path,
        file_classifier=FileClassifier(),
    )

    assert props[cs.KEY_SOURCE_TYPE] == SourceType.TEST.value


def test_source_type_classifies_documentation_files(
    temp_repo: Path,
    mock_ingestor: MagicMock,
    mock_language_queries: dict[
        cs.SupportedLanguage, dict[str, MagicMock | LanguageSpec | None]
    ],
) -> None:
    file_path = temp_repo / "README.md"
    file_path.touch()

    props = _process_file(
        temp_repo,
        mock_ingestor,
        mock_language_queries,
        file_path,
        file_classifier=FileClassifier(),
    )

    assert props[cs.KEY_SOURCE_TYPE] == SourceType.DOCUMENTATION.value


def test_source_type_classifies_config_files(
    temp_repo: Path,
    mock_ingestor: MagicMock,
    mock_language_queries: dict[
        cs.SupportedLanguage, dict[str, MagicMock | LanguageSpec | None]
    ],
) -> None:
    file_path = temp_repo / "pyproject.toml"
    file_path.touch()

    props = _process_file(
        temp_repo,
        mock_ingestor,
        mock_language_queries,
        file_path,
        file_classifier=FileClassifier(),
    )

    assert props[cs.KEY_SOURCE_TYPE] == SourceType.CONFIG.value


def test_source_type_defaults_to_code_without_classifier(
    temp_repo: Path,
    mock_ingestor: MagicMock,
    mock_language_queries: dict[
        cs.SupportedLanguage, dict[str, MagicMock | LanguageSpec | None]
    ],
) -> None:
    file_path = temp_repo / "src" / "main.py"
    file_path.parent.mkdir(parents=True)
    file_path.touch()

    props = _process_file(
        temp_repo,
        mock_ingestor,
        mock_language_queries,
        file_path,
        file_classifier=None,
    )

    assert props[cs.KEY_SOURCE_TYPE] == SourceType.CODE.value
