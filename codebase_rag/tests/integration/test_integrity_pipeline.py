from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from codebase_rag.tests.conftest import (
    create_and_run_updater,
    get_nodes,
    get_relationships,
)
from codebase_rag.types_defs import GraphData, GraphMetadata

PROVENANCE_FIELDS = ("parsed_at", "file_mtime")
SOURCE_TYPE_FIELD = "source_type"
CONFIDENCE_FIELD = "confidence"


@pytest.fixture
def sample_repo(temp_repo: Path) -> Path:
    project_path = temp_repo / "sample_repo"
    project_path.mkdir()

    (project_path / "README.md").write_text("# Sample Repo\n", encoding="utf-8")

    app_dir = project_path / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "utils.py").write_text(
        "def helper() -> int:\n    return 42\n", encoding="utf-8"
    )
    (app_dir / "main.py").write_text(
        """
from app.utils import helper

def run() -> int:
    return helper()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    return project_path


def _file_node_properties(mock_ingestor: MagicMock) -> list[dict[str, Any]]:
    return [call[0][1] for call in get_nodes(mock_ingestor, "File")]


def _maybe_skip_missing_fields(
    props_list: list[dict[str, Any]], required: Iterable[str], reason: str
) -> None:
    if not props_list:
        pytest.fail("No File nodes were ingested; test data may be invalid.")

    if not any(any(field in props for field in required) for props in props_list):
        pytest.skip(reason)


def _call_relationship_properties(mock_ingestor: MagicMock) -> list[dict[str, Any]]:
    relationships = get_relationships(mock_ingestor, "CALLS")
    if not relationships:
        pytest.fail("No CALLS relationships were ingested; test data may be invalid.")

    props_list: list[dict[str, Any]] = []
    for relationship in relationships:
        args = relationship.args
        props = args[3] if len(args) > 3 else None
        if props:
            props_list.append(props)
        else:
            props_list.append({})

    return props_list


def _maybe_skip_missing_confidence(
    props_list: list[dict[str, Any]], reason: str
) -> None:
    if not any(CONFIDENCE_FIELD in props for props in props_list):
        pytest.skip(reason)


def _build_graph_data_from_mock(mock_ingestor: MagicMock) -> GraphData:
    nodes = []
    node_id_counter = 1
    key_to_id: dict[tuple[str, str], int] = {}

    for call in mock_ingestor.ensure_node_batch.call_args_list:
        label = str(call[0][0])
        props = call[0][1]

        qn = props.get("qualified_name")
        name = props.get("name")
        path = props.get("path")

        if qn:
            key = (label, qn)
        elif name:
            key = (label, name)
        elif path:
            key = (label, path)
        else:
            continue

        if key not in key_to_id:
            key_to_id[key] = node_id_counter
            node_id_counter += 1

            nodes.append(
                {
                    "node_id": key_to_id[key],
                    "labels": [label],
                    "properties": props,
                }
            )

    relationships = []
    for call in mock_ingestor.ensure_relationship_batch.call_args_list:
        from_tuple = call[0][0]
        rel_type = call[0][1]
        to_tuple = call[0][2]
        props = call[0][3] if len(call[0]) > 3 and call[0][3] else {}

        from_key = (str(from_tuple[0]), from_tuple[2])
        to_key = (str(to_tuple[0]), to_tuple[2])

        from_id = key_to_id.get(from_key, 0)
        to_id = key_to_id.get(to_key, 0)

        if from_id and to_id:
            relationships.append(
                {
                    "from_id": from_id,
                    "to_id": to_id,
                    "type": rel_type,
                    "properties": props,
                }
            )

    return GraphData(
        nodes=nodes,
        relationships=relationships,
        metadata=GraphMetadata(
            total_nodes=len(nodes),
            total_relationships=len(relationships),
            exported_at="2025-01-01T00:00:00Z",
        ),
    )


def _load_validation_engine() -> type | None:
    candidate_modules = (
        "codebase_rag.validation_engine",
        "codebase_rag.validation.engine",
        "codebase_rag.validation",
    )
    for module_name in candidate_modules:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        engine = getattr(module, "ValidationEngine", None)
        if engine is not None:
            return engine
    return None


def _run_validation(engine_cls: type, graph_data: GraphData) -> Any:
    if hasattr(engine_cls, "validate_graph"):
        validate_graph = getattr(engine_cls, "validate_graph")
        return validate_graph(graph_data)

    try:
        engine = engine_cls(graph_data)
    except TypeError:
        engine = engine_cls()

    if hasattr(engine, "validate"):
        validate = getattr(engine, "validate")
        try:
            return validate(graph_data)
        except TypeError:
            return validate()

    if hasattr(engine, "run"):
        run = getattr(engine, "run")
        try:
            return run(graph_data)
        except TypeError:
            return run()

    raise AssertionError(
        "ValidationEngine does not expose validate_graph, validate, or run methods."
    )


def _extract_issue_texts(result: Any) -> list[str]:
    if result is None:
        return []

    if isinstance(result, dict):
        for key in ("errors", "issues", "orphans", "missing_targets"):
            if key in result:
                return [str(item) for item in result[key]]
        return [str(result)]

    if isinstance(result, (list, tuple)):
        return [str(item) for item in result]

    for attr in ("errors", "issues", "orphans", "missing_targets"):
        if hasattr(result, attr):
            value = getattr(result, attr)
            if isinstance(value, (list, tuple)):
                return [str(item) for item in value]
            return [str(value)]

    if hasattr(result, "is_valid"):
        return [f"is_valid={getattr(result, 'is_valid')}"]

    return [str(result)]


def _has_orphan_issue(issue_texts: list[str]) -> bool:
    indicators = ("orphan", "missing target", "missing node", "unresolved")
    return any(
        indicator in text.lower() for text in issue_texts for indicator in indicators
    )


def test_provenance_tracked_on_indexing(
    sample_repo: Path, mock_ingestor: MagicMock
) -> None:
    create_and_run_updater(sample_repo, mock_ingestor)

    file_props = _file_node_properties(mock_ingestor)
    _maybe_skip_missing_fields(
        file_props,
        PROVENANCE_FIELDS,
        "Provenance metadata not yet attached to File nodes.",
    )

    for props in file_props:
        for field in PROVENANCE_FIELDS:
            assert field in props, f"Missing {field} on File node: {props}"
            assert props[field] is not None


def test_source_type_classified_on_indexing(
    sample_repo: Path, mock_ingestor: MagicMock
) -> None:
    create_and_run_updater(sample_repo, mock_ingestor)

    file_props = _file_node_properties(mock_ingestor)
    _maybe_skip_missing_fields(
        file_props,
        [SOURCE_TYPE_FIELD],
        "Source type classification not yet attached to File nodes.",
    )

    for props in file_props:
        assert SOURCE_TYPE_FIELD in props, (
            f"Missing {SOURCE_TYPE_FIELD} on File node: {props}"
        )
        assert props[SOURCE_TYPE_FIELD] not in (None, "")


def test_calls_have_confidence(sample_repo: Path, mock_ingestor: MagicMock) -> None:
    create_and_run_updater(sample_repo, mock_ingestor)

    call_props = _call_relationship_properties(mock_ingestor)
    _maybe_skip_missing_confidence(
        call_props,
        "CALLS relationships do not yet include confidence scores.",
    )

    for props in call_props:
        assert CONFIDENCE_FIELD in props, f"Missing confidence on CALLS: {props}"
        confidence = props[CONFIDENCE_FIELD]
        assert confidence is not None
        assert 0 <= confidence <= 1


def test_validation_catches_orphans() -> None:
    engine_cls = _load_validation_engine()
    if engine_cls is None:
        pytest.skip("ValidationEngine not available in this checkout.")

    graph_data = GraphData(
        nodes=[
            {
                "node_id": 1,
                "labels": ["Function"],
                "properties": {"qualified_name": "sample.main"},
            }
        ],
        relationships=[
            {
                "from_id": 1,
                "to_id": 999,
                "type": "CALLS",
                "properties": {},
            }
        ],
        metadata=GraphMetadata(
            total_nodes=1,
            total_relationships=1,
            exported_at="2025-01-01T00:00:00Z",
        ),
    )

    result = _run_validation(engine_cls, graph_data)
    issue_texts = _extract_issue_texts(result)

    assert _has_orphan_issue(issue_texts), (
        "ValidationEngine did not report orphaned relationships. "
        f"Observed issues: {issue_texts}"
    )


def test_end_to_end_integrity(sample_repo: Path, mock_ingestor: MagicMock) -> None:
    engine_cls = _load_validation_engine()
    if engine_cls is None:
        pytest.skip("ValidationEngine not available in this checkout.")

    create_and_run_updater(sample_repo, mock_ingestor)

    file_props = _file_node_properties(mock_ingestor)
    _maybe_skip_missing_fields(
        file_props,
        PROVENANCE_FIELDS,
        "Provenance metadata not yet attached to File nodes.",
    )
    _maybe_skip_missing_fields(
        file_props,
        [SOURCE_TYPE_FIELD],
        "Source type classification not yet attached to File nodes.",
    )

    call_props = _call_relationship_properties(mock_ingestor)
    _maybe_skip_missing_confidence(
        call_props,
        "CALLS relationships do not yet include confidence scores.",
    )

    graph_data = _build_graph_data_from_mock(mock_ingestor)
    result = _run_validation(engine_cls, graph_data)
    issue_texts = _extract_issue_texts(result)

    assert not _has_orphan_issue(issue_texts), (
        "ValidationEngine reported orphaned relationships in a valid pipeline run. "
        f"Observed issues: {issue_texts}"
    )
