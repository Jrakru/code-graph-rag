from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

from codebase_rag import constants as cs
from codebase_rag.services.staleness_reporter import (
    ReportFormat,
    StalenessReporter,
    StalenessSeverity,
)


def _write_file(path: Path, content: str, modified_at: dt.datetime) -> str:
    path.write_text(content, encoding="utf-8")
    timestamp = modified_at.timestamp()
    os.utime(path, (timestamp, timestamp))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_staleness_report_metrics_and_categories(tmp_path: Path) -> None:
    now = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)

    _write_file(tmp_path / "recent.txt", "recent", now - dt.timedelta(days=2))
    _write_file(tmp_path / "old.txt", "old", now - dt.timedelta(days=120))
    fresh_hash = _write_file(
        tmp_path / "fresh.txt", "fresh", now - dt.timedelta(days=1)
    )

    ingestor = MagicMock()
    ingestor.fetch_all.return_value = [
        {
            cs.KEY_PATH: "recent.txt",
            cs.KEY_FILE_HASH: "different",
            cs.KEY_PARSED_AT: "t",
        },
        {cs.KEY_PATH: "old.txt", cs.KEY_FILE_HASH: "different", cs.KEY_PARSED_AT: "t"},
        {cs.KEY_PATH: "fresh.txt", cs.KEY_FILE_HASH: fresh_hash, cs.KEY_PARSED_AT: "t"},
        {cs.KEY_PATH: "missing.txt", cs.KEY_FILE_HASH: "hash", cs.KEY_PARSED_AT: "t"},
    ]

    reporter = StalenessReporter(ingestor, tmp_path, now_provider=lambda: now)
    report = reporter.generate_report()

    assert report.metrics.files_analyzed == 4
    assert report.metrics.stale_files == 3
    assert report.metrics.fresh_files == 1
    assert report.metrics.stale_percentage == 75.0
    assert report.metrics.oldest_stale_file is not None
    assert report.metrics.oldest_stale_file.path == "old.txt"

    categories = report.categories
    assert len(categories[StalenessSeverity.RECENTLY_CHANGED.value]) == 1
    assert len(categories[StalenessSeverity.SEVERELY_CHANGED.value]) == 1
    assert len(categories[StalenessSeverity.UNKNOWN.value]) == 1


def test_report_renderers_return_expected_formats(tmp_path: Path) -> None:
    now = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
    fresh_hash = _write_file(
        tmp_path / "fresh.txt", "fresh", now - dt.timedelta(days=1)
    )

    ingestor = MagicMock()
    ingestor.fetch_all.return_value = [
        {cs.KEY_PATH: "fresh.txt", cs.KEY_FILE_HASH: fresh_hash, cs.KEY_PARSED_AT: "t"}
    ]

    reporter = StalenessReporter(ingestor, tmp_path, now_provider=lambda: now)
    report = reporter.generate_report()

    json_output = reporter.render(report, ReportFormat.JSON)
    parsed = json.loads(json_output)
    assert parsed["metrics"]["files_analyzed"] == 1

    markdown_output = reporter.render(report, ReportFormat.MARKDOWN)
    assert "# Staleness Report" in markdown_output
    assert "## Summary" in markdown_output
