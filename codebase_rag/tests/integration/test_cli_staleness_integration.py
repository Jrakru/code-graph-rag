from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

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


def _prepare_console() -> Any:
    console_class = cli.app_context.console.__class__
    console = console_class(force_terminal=False, no_color=True, width=80, record=True)
    cli.app_context.console = console
    return console


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


def test_check_staleness_reports_files_and_stats() -> None:
    with TemporaryDirectory() as tmp_dir:
        paths = _build_repo(Path(tmp_dir))
        repo_root = paths["repo_root"]

        hash_a = compute_file_hash(paths["src/a.py"])
        assert hash_a is not None
        stored_hashes = {
            "src/a.py": hash_a,
            "src/b.py": "stale-hash",
        }

        def _connect_memgraph(_: int) -> StubIngestor:
            return StubIngestor(stored_hashes)

        console = _prepare_console()
        with patch.object(cli, "connect_memgraph", _connect_memgraph):
            cli.check_staleness(
                repo_path=str(repo_root),
                extension=None,
                path_pattern=None,
                batch_size=None,
            )

        output = console.export_text()
        assert cs.CLI_MSG_STALENESS_STATS.split("{")[0] in output
        assert "src/b.py" in output
        assert "docs/readme.md" in output
        assert "66.7%" in output


def test_check_staleness_filters_by_extension_and_pattern() -> None:
    with TemporaryDirectory() as tmp_dir:
        paths = _build_repo(Path(tmp_dir))
        repo_root = paths["repo_root"]

        hash_a = compute_file_hash(paths["src/a.py"])
        assert hash_a is not None
        stored_hashes = {
            "src/a.py": hash_a,
            "src/b.py": "stale-hash",
        }

        def _connect_memgraph(_: int) -> StubIngestor:
            return StubIngestor(stored_hashes)

        console = _prepare_console()
        with patch.object(cli, "connect_memgraph", _connect_memgraph):
            cli.check_staleness(
                repo_path=str(repo_root),
                extension=["py"],
                path_pattern=r"src/.*",
                batch_size=None,
            )

        output = console.export_text()
        assert "1/2" in output
        assert "50.0%" in output
        assert "docs/readme.md" not in output


def test_start_check_staleness_warns() -> None:
    with TemporaryDirectory() as tmp_dir:
        paths = _build_repo(Path(tmp_dir))
        repo_root = paths["repo_root"]

        stored_hashes = {"src/a.py": "stale-hash"}

        def _connect_memgraph(_: int) -> StubIngestor:
            return StubIngestor(stored_hashes)

        async def _noop_main_async(_: str, __: int) -> None:
            return None

        console = _prepare_console()
        with (
            patch.object(cli, "connect_memgraph", _connect_memgraph),
            patch.object(cli, "main_async", _noop_main_async),
        ):
            cli.start(
                repo_path=str(repo_root),
                update_graph=False,
                clean=False,
                output=None,
                orchestrator=None,
                cypher=None,
                no_confirm=False,
                batch_size=None,
                check_staleness=True,
            )

        output = console.export_text()
        assert cs.CLI_WARN_STALE_HINT in output
