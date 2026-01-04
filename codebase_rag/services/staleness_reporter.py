from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .. import constants as cs
from ..cypher_queries import CYPHER_FETCH_FILE_SNAPSHOTS
from ..services import QueryProtocol


class ReportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"


class StalenessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"


class StalenessReason(StrEnum):
    MISSING_FILE = "missing_file"
    MISSING_HASH = "missing_hash"
    HASH_MISMATCH = "hash_mismatch"
    UNREADABLE = "unreadable"


class StalenessSeverity(StrEnum):
    RECENTLY_CHANGED = "recently_changed"
    MODERATELY_CHANGED = "moderately_changed"
    SIGNIFICANTLY_CHANGED = "significantly_changed"
    SEVERELY_CHANGED = "severely_changed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StalenessFileRecord:
    path: str
    status: StalenessStatus
    reason: StalenessReason | None
    severity: StalenessSeverity | None
    last_modified: str | None
    parsed_at: str | None
    staleness_days: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status.value,
            "reason": self.reason.value if self.reason else None,
            "severity": self.severity.value if self.severity else None,
            "last_modified": self.last_modified,
            "parsed_at": self.parsed_at,
            "staleness_days": self.staleness_days,
        }


@dataclass(frozen=True)
class OldestStaleFile:
    path: str
    staleness_days: float
    last_modified: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "staleness_days": self.staleness_days,
            "last_modified": self.last_modified,
        }


@dataclass(frozen=True)
class StalenessMetrics:
    files_analyzed: int
    stale_files: int
    fresh_files: int
    stale_percentage: float
    oldest_stale_file: OldestStaleFile | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_analyzed": self.files_analyzed,
            "stale_files": self.stale_files,
            "fresh_files": self.fresh_files,
            "stale_percentage": self.stale_percentage,
            "oldest_stale_file": (
                self.oldest_stale_file.to_dict() if self.oldest_stale_file else None
            ),
        }


@dataclass(frozen=True)
class StalenessReport:
    generated_at: str
    repo_root: str
    metrics: StalenessMetrics
    categories: dict[str, list[StalenessFileRecord]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "repo_root": self.repo_root,
            "metrics": self.metrics.to_dict(),
            "categories": {
                category: [record.to_dict() for record in records]
                for category, records in self.categories.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=cs.JSON_INDENT, sort_keys=True)

    def to_markdown(self) -> str:
        lines: list[str] = ["# Staleness Report", ""]
        lines.append(f"Generated: {self.generated_at}")
        lines.append(f"Repository: {self.repo_root}")
        lines.append("")

        lines.append("## Summary")
        lines.append(f"- Files analyzed: {self.metrics.files_analyzed}")
        lines.append(f"- Fresh files: {self.metrics.fresh_files}")
        lines.append(
            f"- Stale files: {self.metrics.stale_files} "
            f"({self.metrics.stale_percentage:.2f}%)"
        )

        if self.metrics.oldest_stale_file:
            oldest = self.metrics.oldest_stale_file
            lines.append(
                f"- Oldest stale file: {oldest.path} ({oldest.staleness_days:.2f} days)"
            )
        else:
            lines.append("- Oldest stale file: n/a")

        lines.append("")
        lines.append("## Severity Breakdown")
        lines.append("| Severity | Count |")
        lines.append("| --- | ---: |")
        for severity in StalenessSeverity:
            label = _severity_label(severity)
            count = len(self.categories.get(severity.value, []))
            lines.append(f"| {label} | {count} |")

        lines.append("")
        lines.append("## Stale Files by Severity")
        for severity in StalenessSeverity:
            records = self.categories.get(severity.value, [])
            label = _severity_label(severity)
            lines.append(f"### {label} ({len(records)})")
            if not records:
                lines.append("")
                continue
            for record in records:
                detail = []
                if record.staleness_days is not None:
                    detail.append(f"{record.staleness_days:.2f} days")
                if record.reason:
                    detail.append(record.reason.value.replace("_", " "))
                detail_suffix = f" ({', '.join(detail)})" if detail else ""
                lines.append(f"- {record.path}{detail_suffix}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"


class StalenessReporter:
    def __init__(
        self,
        ingestor: QueryProtocol,
        repo_root: Path | str,
        now_provider: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self.ingestor = ingestor
        self.repo_root = Path(repo_root).resolve()
        self._now_provider = now_provider or (lambda: dt.datetime.now(dt.UTC))

    def generate_report(self) -> StalenessReport:
        rows = self.ingestor.fetch_all(CYPHER_FETCH_FILE_SNAPSHOTS)
        now = self._now_provider()

        records: list[StalenessFileRecord] = []
        for row in rows:
            path_value = row.get(cs.KEY_PATH)
            if not isinstance(path_value, str):
                continue
            stored_hash = _coerce_hash(row.get(cs.KEY_FILE_HASH))
            parsed_at = _format_timestamp(row.get(cs.KEY_PARSED_AT))
            record = self._inspect_file(path_value, stored_hash, parsed_at, now)
            records.append(record)

        stale_records = [
            record for record in records if record.status is StalenessStatus.STALE
        ]

        categories: dict[str, list[StalenessFileRecord]] = {
            severity.value: [] for severity in StalenessSeverity
        }
        for record in stale_records:
            severity = record.severity or StalenessSeverity.UNKNOWN
            categories[severity.value].append(record)

        metrics = self._build_metrics(records, stale_records)

        return StalenessReport(
            generated_at=now.isoformat(),
            repo_root=str(self.repo_root),
            metrics=metrics,
            categories=categories,
        )

    def render(self, report: StalenessReport, output_format: ReportFormat) -> str:
        if output_format is ReportFormat.JSON:
            return report.to_json()
        if output_format is ReportFormat.MARKDOWN:
            return report.to_markdown()
        raise ValueError(f"Unsupported report format: {output_format}")

    def _inspect_file(
        self,
        path: str,
        stored_hash: str | None,
        parsed_at: str | None,
        now: dt.datetime,
    ) -> StalenessFileRecord:
        file_path = self._resolve_path(path)
        last_modified, staleness_days = self._get_last_modified(file_path, now)

        if not file_path.exists():
            return StalenessFileRecord(
                path=path,
                status=StalenessStatus.STALE,
                reason=StalenessReason.MISSING_FILE,
                severity=StalenessSeverity.UNKNOWN,
                last_modified=None,
                parsed_at=parsed_at,
                staleness_days=None,
            )

        current_hash = self._hash_file(file_path)

        if not _hash_is_valid(stored_hash):
            severity = _severity_from_age(staleness_days)
            return StalenessFileRecord(
                path=path,
                status=StalenessStatus.STALE,
                reason=StalenessReason.MISSING_HASH,
                severity=severity,
                last_modified=last_modified,
                parsed_at=parsed_at,
                staleness_days=staleness_days,
            )

        if not _hash_is_valid(current_hash):
            severity = _severity_from_age(staleness_days)
            return StalenessFileRecord(
                path=path,
                status=StalenessStatus.STALE,
                reason=StalenessReason.UNREADABLE,
                severity=severity,
                last_modified=last_modified,
                parsed_at=parsed_at,
                staleness_days=staleness_days,
            )

        if stored_hash != current_hash:
            severity = _severity_from_age(staleness_days)
            return StalenessFileRecord(
                path=path,
                status=StalenessStatus.STALE,
                reason=StalenessReason.HASH_MISMATCH,
                severity=severity,
                last_modified=last_modified,
                parsed_at=parsed_at,
                staleness_days=staleness_days,
            )

        return StalenessFileRecord(
            path=path,
            status=StalenessStatus.FRESH,
            reason=None,
            severity=None,
            last_modified=last_modified,
            parsed_at=parsed_at,
            staleness_days=None,
        )

    def _resolve_path(self, path: str) -> Path:
        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return self.repo_root / path_obj

    def _hash_file(self, path: Path) -> str | None:
        try:
            hasher = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError:
            return None

    def _get_last_modified(
        self, path: Path, now: dt.datetime
    ) -> tuple[str | None, float | None]:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None, None

        modified = dt.datetime.fromtimestamp(mtime, tz=dt.UTC)
        staleness_days = max((now - modified).total_seconds() / 86_400, 0.0)
        return modified.isoformat(), round(staleness_days, 2)

    def _build_metrics(
        self,
        records: list[StalenessFileRecord],
        stale_records: list[StalenessFileRecord],
    ) -> StalenessMetrics:
        files_analyzed = len(records)
        stale_files = len(stale_records)
        fresh_files = files_analyzed - stale_files
        stale_percentage = (
            round(stale_files / files_analyzed * 100, 2) if files_analyzed else 0.0
        )

        oldest = self._find_oldest_stale(stale_records)
        return StalenessMetrics(
            files_analyzed=files_analyzed,
            stale_files=stale_files,
            fresh_files=fresh_files,
            stale_percentage=stale_percentage,
            oldest_stale_file=oldest,
        )

    def _find_oldest_stale(
        self, stale_records: list[StalenessFileRecord]
    ) -> OldestStaleFile | None:
        candidates = [
            record for record in stale_records if record.staleness_days is not None
        ]
        if not candidates:
            return None

        oldest = max(candidates, key=lambda record: record.staleness_days or 0.0)
        return OldestStaleFile(
            path=oldest.path,
            staleness_days=oldest.staleness_days or 0.0,
            last_modified=oldest.last_modified,
        )


def _hash_is_valid(value: str | None) -> bool:
    return isinstance(value, str) and value != ""


def _coerce_hash(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _format_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, tz=dt.UTC).isoformat()
    if isinstance(value, str):
        return value
    return None


def _severity_from_age(staleness_days: float | None) -> StalenessSeverity:
    if staleness_days is None:
        return StalenessSeverity.UNKNOWN
    if staleness_days <= 7:
        return StalenessSeverity.RECENTLY_CHANGED
    if staleness_days <= 30:
        return StalenessSeverity.MODERATELY_CHANGED
    if staleness_days <= 90:
        return StalenessSeverity.SIGNIFICANTLY_CHANGED
    return StalenessSeverity.SEVERELY_CHANGED


def _severity_label(severity: StalenessSeverity) -> str:
    return severity.value.replace("_", " ").title()
