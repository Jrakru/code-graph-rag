from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codebase_rag import constants as cs
from codebase_rag.graph_updater import GraphUpdater
from codebase_rag.parser_loader import load_parsers
from codebase_rag.services.confidence_scorer import ConfidenceScorer, ResolutionMethod


def _run_updater(
    temp_repo: Path,
    mock_ingestor: MagicMock,
    files: dict[str, str],
) -> None:
    parsers, queries = load_parsers()
    if cs.SupportedLanguage.PYTHON not in parsers:
        pytest.skip("Python parser not available")

    for rel_path, content in files.items():
        file_path = temp_repo / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=temp_repo,
        parsers=parsers,
        queries=queries,
    )
    updater.run()


def _get_calls(mock_ingestor: MagicMock) -> list:
    return [
        c
        for c in mock_ingestor.ensure_relationship_batch.call_args_list
        if c.args[1] == cs.RelationshipType.CALLS
    ]


def test_calls_include_confidence_and_resolution_method_direct_import(
    temp_repo: Path,
    mock_ingestor: MagicMock,
) -> None:
    _run_updater(
        temp_repo,
        mock_ingestor,
        {
            "utils.py": """

def helper():
    return "ok"
""",
            "main.py": """
from utils import helper

def main():
    helper()
""",
        },
    )

    calls = _get_calls(mock_ingestor)
    assert calls

    helper_call = next(
        c for c in calls if ".utils.helper" in c.args[2][2]
    )
    props = helper_call.kwargs.get("properties")
    assert props is not None
    assert cs.KEY_CONFIDENCE in props
    assert cs.KEY_RESOLUTION_METHOD in props
    assert props[cs.KEY_RESOLUTION_METHOD] == ResolutionMethod.DIRECT_IMPORT.value
    assert props[cs.KEY_CONFIDENCE] == pytest.approx(1.0)


def test_trie_fallback_confidence_is_lower(
    temp_repo: Path,
    mock_ingestor: MagicMock,
) -> None:
    _run_updater(
        temp_repo,
        mock_ingestor,
        {
            "target_mod.py": """

def remote_target():
    return 123
""",
            "caller.py": """

def caller():
    remote_target()
""",
        },
    )

    calls = _get_calls(mock_ingestor)
    assert calls

    fallback_call = next(
        c for c in calls if ".target_mod.remote_target" in c.args[2][2]
    )
    props = fallback_call.kwargs.get("properties")
    assert props is not None
    assert props[cs.KEY_RESOLUTION_METHOD] == ResolutionMethod.TRIE_FALLBACK.value
    assert props[cs.KEY_CONFIDENCE] == pytest.approx(0.5)


def test_call_processor_uses_default_confidence_scorer(
    temp_repo: Path,
    mock_ingestor: MagicMock,
) -> None:
    parsers, queries = load_parsers()
    if cs.SupportedLanguage.PYTHON not in parsers:
        pytest.skip("Python parser not available")

    updater = GraphUpdater(
        ingestor=mock_ingestor,
        repo_path=temp_repo,
        parsers=parsers,
        queries=queries,
    )
    processor = updater.factory.call_processor
    assert isinstance(processor._confidence_scorer, ConfidenceScorer)
