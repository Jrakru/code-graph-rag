from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

validation_engine = pytest.importorskip("codebase_rag.services.validation_engine")
ValidationEngine = validation_engine.ValidationEngine
OrphanRelationship = validation_engine.OrphanRelationship


@pytest.fixture
def graph_service() -> MagicMock:
    service = MagicMock()
    service.fetch_all.return_value = []
    return service


@pytest.fixture
def engine(graph_service: MagicMock) -> Any:
    return ValidationEngine(graph_service)


class TestValidationEngineValidateRelationship:
    def test_returns_true_when_target_exists(self, engine: Any) -> None:
        from_spec = ("Function", "qualified_name", "project.module.caller")
        to_spec = ("Function", "qualified_name", "project.module.target")

        with patch.object(engine, "_node_exists", return_value=True) as mock_exists:
            assert engine.validate_relationship(from_spec, "CALLS", to_spec) is True
            assert mock_exists.called

    def test_returns_false_when_target_missing(self, engine: Any) -> None:
        from_spec = ("Function", "qualified_name", "project.module.caller")
        to_spec = ("Function", "qualified_name", "project.module.missing")

        with patch.object(engine, "_node_exists", return_value=False) as mock_exists:
            assert engine.validate_relationship(from_spec, "CALLS", to_spec) is False
            assert mock_exists.called

    def test_adds_to_orphans_when_target_missing(self, engine: Any) -> None:
        from_spec = ("Function", "qualified_name", "project.module.caller")
        to_spec = ("Function", "qualified_name", "project.module.missing")

        with patch.object(engine, "_node_exists", return_value=False):
            engine.validate_relationship(from_spec, "CALLS", to_spec)

        orphans = engine.report_orphans()
        assert len(orphans) == 1
        assert orphans[0].from_label == "Function"
        assert orphans[0].from_val == "project.module.caller"
        assert orphans[0].to_val == "project.module.missing"
        assert orphans[0].rel_type == "CALLS"


class TestValidationEngineNodeExists:
    def test_node_exists_returns_true_when_rows_found(
        self, engine: Any, graph_service: MagicMock
    ) -> None:
        graph_service.fetch_all.return_value = [{"count": 1}]

        assert (
            engine._node_exists("Function", "qualified_name", "project.module.func")
            is True
        )
        graph_service.fetch_all.assert_called_once()

    def test_node_exists_returns_false_when_no_rows(
        self, engine: Any, graph_service: MagicMock
    ) -> None:
        graph_service.fetch_all.return_value = []

        assert (
            engine._node_exists("Function", "qualified_name", "project.module.missing")
            is False
        )
        graph_service.fetch_all.assert_called_once()

    def test_node_exists_returns_false_for_empty_label(self, engine: Any) -> None:
        assert engine._node_exists("", "qualified_name", "project.module.func") is False

    def test_node_exists_returns_false_for_none_value(self, engine: Any) -> None:
        assert engine._node_exists("Function", "qualified_name", None) is False


class TestValidationEngineReportOrphans:
    def test_report_orphans_returns_internal_list(self, engine: Any) -> None:
        from_spec = ("Function", "qualified_name", "project.module.caller")
        to_spec = ("Function", "qualified_name", "project.module.missing")

        with patch.object(engine, "_node_exists", return_value=False):
            engine.validate_relationship(from_spec, "CALLS", to_spec)

        orphans = engine.report_orphans()
        assert len(orphans) == 1
        assert isinstance(orphans[0], OrphanRelationship)

    def test_report_orphans_returns_empty_list_when_none(self, engine: Any) -> None:
        assert engine.report_orphans() == []

    def test_clear_orphans_empties_list(self, engine: Any) -> None:
        from_spec = ("Function", "qualified_name", "project.module.caller")
        to_spec = ("Function", "qualified_name", "project.module.missing")

        with patch.object(engine, "_node_exists", return_value=False):
            engine.validate_relationship(from_spec, "CALLS", to_spec)

        assert len(engine.report_orphans()) == 1
        engine.clear_orphans()
        assert engine.report_orphans() == []
