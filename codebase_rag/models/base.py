from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..constants import NodeLabel, RelationshipType


class SourceType(StrEnum):
    PARSED = "parsed"
    INFERRED = "inferred"
    MANUAL = "manual"


class Result[T](BaseModel):
    success: bool = True
    data: T | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def _set_success_on_error(self) -> Result[T]:
        if self.error_message is not None:
            self.success = False
        return self

    model_config = ConfigDict(extra="forbid")


class BaseNode(BaseModel):
    node_id: int
    label: NodeLabel
    confidence: float
    source_type: SourceType

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return value

    model_config = ConfigDict(extra="forbid")


class BaseRelationship(BaseModel):
    from_id: int
    to_id: int
    type: RelationshipType
    confidence: float
    source_type: SourceType

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return value

    model_config = ConfigDict(extra="forbid")
