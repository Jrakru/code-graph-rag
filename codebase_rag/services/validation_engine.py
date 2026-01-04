from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .. import constants as cs
from ..types_defs import PropertyValue, ResultRow
from . import QueryProtocol


@dataclass(frozen=True)
class OrphanRelationship:
    from_label: str
    from_key: str
    from_val: PropertyValue
    to_label: str
    to_key: str
    to_val: PropertyValue
    rel_type: str


class ValidationEngine:
    def __init__(
        self,
        query_service: QueryProtocol,
        pending_node_exists: Callable[[str, str, PropertyValue], bool] | None = None,
    ) -> None:
        self._query_service = query_service
        self._pending_node_exists = pending_node_exists
        self._cache: dict[tuple[str, str, PropertyValue], bool] = {}
        self._orphans: list[OrphanRelationship] = []

    def _node_exists(self, label: str, key: str, value: PropertyValue) -> bool:
        if not label or not key or value is None:
            return False

        cache_key = self._make_cache_key(label, key, value)
        if cache_key is not None and cache_key in self._cache:
            return self._cache[cache_key]

        if self._pending_node_exists and self._pending_node_exists(label, key, value):
            if cache_key is not None:
                self._cache[cache_key] = True
            return True

        query = f"MATCH (n:{label} {{{key}: $value}}) RETURN count(n) as count"
        rows: list[ResultRow] = self._query_service.fetch_all(
            query, {"value": value}
        )
        exists = self._count_from_rows(rows) > 0
        if cache_key is not None:
            self._cache[cache_key] = exists
        return exists

    def validate_relationship(
        self,
        from_spec: tuple[str, str, PropertyValue],
        rel_type: str,
        to_spec: tuple[str, str, PropertyValue],
    ) -> bool:
        if rel_type != cs.RelationshipType.CALLS:
            return True

        to_label, to_key, to_val = to_spec
        if self._node_exists(to_label, to_key, to_val):
            return True

        from_label, from_key, from_val = from_spec
        self._orphans.append(
            OrphanRelationship(
                from_label=from_label,
                from_key=from_key,
                from_val=from_val,
                to_label=to_label,
                to_key=to_key,
                to_val=to_val,
                rel_type=rel_type,
            )
        )
        return False

    def report_orphans(self) -> list[OrphanRelationship]:
        return list(self._orphans)

    def clear_orphans(self) -> None:
        self._orphans.clear()

    def _make_cache_key(
        self, label: str, key: str, value: PropertyValue
    ) -> tuple[str, str, PropertyValue] | None:
        if isinstance(value, list):
            return None
        return (label, key, value)

    def _count_from_rows(self, rows: list[ResultRow]) -> int:
        if not rows:
            return 0
        count_value = rows[0].get("count")
        if isinstance(count_value, bool):
            return int(count_value)
        if isinstance(count_value, int):
            return count_value
        if isinstance(count_value, float):
            return int(count_value)
        return 0
