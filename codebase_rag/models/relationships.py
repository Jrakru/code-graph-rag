from __future__ import annotations

from typing import Literal

from ..constants import RelationshipType
from .base import BaseRelationship


class CallsRelationship(BaseRelationship):
    type: Literal[RelationshipType.CALLS] = RelationshipType.CALLS


class ImportsRelationship(BaseRelationship):
    type: Literal[RelationshipType.IMPORTS] = RelationshipType.IMPORTS
