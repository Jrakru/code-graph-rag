from __future__ import annotations

import pytest
from pydantic import ValidationError

from codebase_rag.constants import NodeLabel, RelationshipType
from codebase_rag.models import (
    CallsRelationship,
    ClassNode,
    FileNode,
    FunctionNode,
    ImportsRelationship,
    ModuleNode,
    Result,
    SourceType,
)


def test_file_node_validates_required_fields() -> None:
    node = FileNode(
        node_id=1,
        path="src/main.py",
        name="main.py",
        extension=".py",
        confidence=0.95,
        source_type=SourceType.PARSED,
    )

    assert node.label == NodeLabel.FILE
    assert node.path == "src/main.py"


def test_module_node_requires_qualified_name() -> None:
    with pytest.raises(ValidationError):
        ModuleNode(
            node_id=2,
            name="core",
            path="src/core.py",
            confidence=0.8,
            source_type=SourceType.INFERRED,
        )


def test_function_node_defaults_decorators() -> None:
    node = FunctionNode(
        node_id=3,
        qualified_name="package.module.func",
        name="func",
        confidence=0.7,
        source_type=SourceType.PARSED,
    )

    assert node.label == NodeLabel.FUNCTION
    assert node.decorators == []


def test_class_node_rejects_invalid_source_type() -> None:
    with pytest.raises(ValidationError):
        ClassNode(
            node_id=4,
            qualified_name="package.module.Classy",
            name="Classy",
            confidence=0.85,
            source_type="unknown",
        )


def test_confidence_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        FileNode(
            node_id=5,
            path="src/bad.py",
            name="bad.py",
            extension=".py",
            confidence=1.5,
            source_type=SourceType.MANUAL,
        )


def test_calls_relationship_type_is_fixed() -> None:
    with pytest.raises(ValidationError):
        CallsRelationship(
            from_id=1,
            to_id=2,
            type=RelationshipType.IMPORTS,
            confidence=0.6,
            source_type=SourceType.PARSED,
        )

    rel = CallsRelationship(
        from_id=1,
        to_id=2,
        confidence=0.6,
        source_type=SourceType.PARSED,
    )
    assert rel.type == RelationshipType.CALLS


def test_imports_relationship_type_is_fixed() -> None:
    rel = ImportsRelationship(
        from_id=10,
        to_id=20,
        confidence=0.55,
        source_type=SourceType.INFERRED,
    )
    assert rel.type == RelationshipType.IMPORTS


def test_result_sets_success_on_error() -> None:
    success_result: Result[int] = Result(data=123)
    assert success_result.success is True

    error_result: Result[None] = Result(error_message="boom")
    assert error_result.success is False
