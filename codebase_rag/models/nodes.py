from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..constants import NodeLabel
from .base import BaseNode


class FileNode(BaseNode):
    label: Literal[NodeLabel.FILE] = NodeLabel.FILE
    path: str
    name: str
    extension: str


class ModuleNode(BaseNode):
    label: Literal[NodeLabel.MODULE] = NodeLabel.MODULE
    qualified_name: str
    name: str
    path: str


class FunctionNode(BaseNode):
    label: Literal[NodeLabel.FUNCTION] = NodeLabel.FUNCTION
    qualified_name: str
    name: str
    decorators: list[str] = Field(default_factory=list)


class ClassNode(BaseNode):
    label: Literal[NodeLabel.CLASS] = NodeLabel.CLASS
    qualified_name: str
    name: str
    decorators: list[str] = Field(default_factory=list)
