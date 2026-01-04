from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from codebase_rag import cli
from codebase_rag import constants as cs
from codebase_rag.services.staleness_checker import compute_file_hash


class StubIngestor:
    def __init__(self, stored_hashes: dict[str, str]) -> None:
        self._stored_hashes = stored_hashes

    def __enter__(self) -> StubIngestor:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def fetch_all(self, query: str, params: dict[str, object] | None = None) -> list:
        paths = []
        if params:
            raw_paths = params.get(cs.KEY_PATHS, [])
            if isinstance(raw_paths, list):
                paths = [p for p in raw_paths if isinstance(p, str)]
        results = []
        for path in paths:
            if path in self._stored_hashes:
                results.append(
                    {
                        cs.KEY_PATH: path,
                        cs.KEY_FILE_HASH: self._stored_hashes[path],
                        cs.KEY_PARSED_AT: "t",
                    }
                )
        return results


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_repo(tmp_path: Path) -> dict[str, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = {
        "src/a.py": repo_root / "src" / "a.py",
        "src/b.py": repo_root / "src" / "b.py",
        "docs/readme.md": repo_root / "docs" / "readme.md",
    }
    _write_file(paths["src/a.py"], "print('a')\n")
    _write_file(paths["src/b.py"], "print('b')\n")
    _write_file(paths["docs/readme.md"], "# docs\n")
    paths["repo_root"] = repo_root
    return paths


def test_check_staleness_reports_files_and_stats(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = _build_repo(tmp_path)
    repo_root = paths["repo_root"]

    hash_a = compute_file_hash(paths["src/a.py"])
    assert hash_a is not None
    stored_hashes = {
        "src/a.py": hash_a,
        "src/b.py": "stale-hash",
    }

    def _connect_memgraph(_: int) -> StubIngestor:
        return StubIngestor(stored_hashes)

    monkeypatch.setattr(cli, "connect_memgraph", _connect_memgraph)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["check-staleness", "--repo-path", str(repo_root)],
    )

    assert result.exit_code == 0
    assert cs.CLI_MSG_STALENESS_STATS.split("{")[0] in result.output
    assert "src/b.py" in result.output
    assert "docs/readme.md" in result.output
    assert "66.7%" in result.output


def test_check_staleness_filters_by_extension_and_pattern(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = _build_repo(tmp_path)
    repo_root = paths["repo_root"]

    hash_a = compute_file_hash(paths["src/a.py"])
    assert hash_a is not None
    stored_hashes = {
        "src/a.py": hash_a,
        "src/b.py": "stale-hash",
    }

    def _connect_memgraph(_: int) -> StubIngestor:
        return StubIngestor(stored_hashes)

    monkeypatch.setattr(cli, "connect_memgraph", _connect_memgraph)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "check-staleness",
            "--repo-path",
            str(repo_root),
            "--extension",
            "py",
            "--path-pattern",
            r"src/.*",
        ],
    )

    assert result.exit_code == 0
    assert "1/2" in result.output
    assert "50.0%" in result.output
    assert "docs/readme.md" not in result.output


def test_start_check_staleness_warns(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    paths = _build_repo(tmp_path)
    repo_root = paths["repo_root"]

    stored_hashes = {"src/a.py": "stale-hash"}

    def _connect_memgraph(_: int) -> StubIngestor:
        return StubIngestor(stored_hashes)

    async def _noop_main_async(_: str, __: int) -> None:
        return None

    monkeypatch.setattr(cli, "connect_memgraph", _connect_memgraph)
    monkeypatch.setattr(cli, "main_async", _noop_main_async)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        ["start", "--repo-path", str(repo_root), "--check-staleness"],
    )

    assert result.exit_code == 0
    assert cs.CLI_WARN_STALE_HINT in result.output
