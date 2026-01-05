import asyncio
from pathlib import Path

import typer
from loguru import logger

from . import cli_help as ch
from . import constants as cs
from . import logs as ls
from .config import settings
from .graph_updater import GraphUpdater
from .main import (
    app_context,
    connect_memgraph,
    export_graph_to_file,
    main_async,
    main_optimize_async,
    style,
    update_model_settings,
)
from .parser_loader import load_parsers
from .services.protobuf_service import ProtobufFileIngestor
from .services.provenance_tracker import ProvenanceTracker
from .services.staleness_checker import StalenessChecker, StalenessReport
from .services.staleness_reporter import ReportFormat, StalenessReporter
from .tools.language import cli as language_cli

app = typer.Typer(
    name="graph-code",
    help=ch.APP_DESCRIPTION,
    no_args_is_help=True,
    add_completion=False,
)


def _run_staleness_check(
    repo_path: Path,
    batch_size: int,
    extensions: list[str] | None = None,
    path_pattern: str | None = None,
) -> StalenessReport:
    with connect_memgraph(batch_size) as ingestor:
        tracker = ProvenanceTracker(ingestor, repo_path)
        checker = StalenessChecker(tracker, repo_path)
        return checker.scan(extensions=extensions, path_pattern=path_pattern)


def _print_staleness_report(report: StalenessReport, show_paths: bool = True) -> None:
    if report.total_files == 0:
        app_context.console.print(style(cs.CLI_MSG_STALENESS_NO_FILES, cs.Color.YELLOW))
    elif report.stale_count == 0:
        app_context.console.print(style(cs.CLI_MSG_STALENESS_NONE, cs.Color.GREEN))
    else:
        app_context.console.print(
            style(
                cs.CLI_WARN_STALE_FOUND.format(count=report.stale_count),
                cs.Color.YELLOW,
            )
        )
        if show_paths:
            app_context.console.print(cs.CLI_MSG_STALENESS_LIST_HEADER)
            for path in report.stale_paths:
                app_context.console.print(f"  {path}")

    app_context.console.print(
        style(
            cs.CLI_MSG_STALENESS_STATS.format(
                stale=report.stale_count,
                total=report.total_files,
                percent=report.stale_percentage,
            ),
            cs.Color.CYAN,
        )
    )


@app.command(help=ch.CMD_START)
def start(
    repo_path: str | None = typer.Option(
        None, "--repo-path", help=ch.HELP_REPO_PATH_RETRIEVAL
    ),
    update_graph: bool = typer.Option(
        False,
        "--update-graph",
        help=ch.HELP_UPDATE_GRAPH,
    ),
    clean: bool = typer.Option(
        False,
        "--clean",
        help=ch.HELP_CLEAN_DB,
    ),
    output: str | None = typer.Option(
        None,
        "-o",
        "--output",
        help=ch.HELP_OUTPUT_GRAPH,
    ),
    orchestrator: str | None = typer.Option(
        None,
        "--orchestrator",
        help=ch.HELP_ORCHESTRATOR,
    ),
    cypher: str | None = typer.Option(
        None,
        "--cypher",
        help=ch.HELP_CYPHER_MODEL,
    ),
    no_confirm: bool = typer.Option(
        False,
        "--no-confirm",
        help=ch.HELP_NO_CONFIRM,
    ),
    batch_size: int | None = typer.Option(
        None,
        "--batch-size",
        min=1,
        help=ch.HELP_BATCH_SIZE,
    ),
    check_staleness: bool = typer.Option(
        False,
        "--check-staleness",
        help=ch.HELP_CHECK_STALENESS,
    ),
) -> None:
    app_context.session.confirm_edits = not no_confirm

    target_repo_path = repo_path or settings.TARGET_REPO_PATH

    if output and not update_graph:
        app_context.console.print(
            style(cs.CLI_ERR_OUTPUT_REQUIRES_UPDATE, cs.Color.RED)
        )
        raise typer.Exit(1)

    update_model_settings(orchestrator, cypher)

    effective_batch_size = settings.resolve_batch_size(batch_size)

    if check_staleness and not update_graph:
        try:
            report = _run_staleness_check(
                Path(target_repo_path),
                effective_batch_size,
            )
            if report.stale_count > 0:
                _print_staleness_report(report, show_paths=False)
                app_context.console.print(
                    style(cs.CLI_WARN_STALE_HINT, cs.Color.YELLOW)
                )
        except ValueError as e:
            app_context.console.print(
                style(cs.CLI_ERR_STALENESS.format(error=e), cs.Color.RED)
            )
        except Exception as e:
            app_context.console.print(
                style(cs.CLI_ERR_STALENESS.format(error=e), cs.Color.RED)
            )
            logger.exception(ls.STALENESS_CHECK_FAILED.format(error=e))

    if update_graph:
        repo_to_update = Path(target_repo_path)
        app_context.console.print(
            style(cs.CLI_MSG_UPDATING_GRAPH.format(path=repo_to_update), cs.Color.GREEN)
        )

        with connect_memgraph(effective_batch_size) as ingestor:
            if clean:
                app_context.console.print(
                    style(cs.CLI_MSG_CLEANING_DB, cs.Color.YELLOW)
                )
                ingestor.clean_database()
            ingestor.ensure_constraints()

            parsers, queries = load_parsers()

            updater = GraphUpdater(ingestor, repo_to_update, parsers, queries)
            updater.run()

            if output:
                app_context.console.print(
                    style(cs.CLI_MSG_EXPORTING_TO.format(path=output), cs.Color.CYAN)
                )
                if not export_graph_to_file(ingestor, output):
                    raise typer.Exit(1)

        app_context.console.print(style(cs.CLI_MSG_GRAPH_UPDATED, cs.Color.GREEN))
        return

    try:
        asyncio.run(main_async(target_repo_path, effective_batch_size))
    except KeyboardInterrupt:
        app_context.console.print(style(cs.CLI_MSG_APP_TERMINATED, cs.Color.RED))
    except ValueError as e:
        app_context.console.print(
            style(cs.CLI_ERR_STARTUP.format(error=e), cs.Color.RED)
        )


@app.command(help=ch.CMD_INDEX)
def index(
    repo_path: str | None = typer.Option(
        None, "--repo-path", help=ch.HELP_REPO_PATH_INDEX
    ),
    output_proto_dir: str = typer.Option(
        ...,
        "-o",
        "--output-proto-dir",
        help=ch.HELP_OUTPUT_PROTO_DIR,
    ),
    split_index: bool = typer.Option(
        False,
        "--split-index",
        help=ch.HELP_SPLIT_INDEX,
    ),
) -> None:
    target_repo_path = repo_path or settings.TARGET_REPO_PATH
    repo_to_index = Path(target_repo_path)

    app_context.console.print(
        style(cs.CLI_MSG_INDEXING_AT.format(path=repo_to_index), cs.Color.GREEN)
    )
    app_context.console.print(
        style(cs.CLI_MSG_OUTPUT_TO.format(path=output_proto_dir), cs.Color.CYAN)
    )

    try:
        ingestor = ProtobufFileIngestor(
            output_path=output_proto_dir, split_index=split_index
        )
        parsers, queries = load_parsers()
        updater = GraphUpdater(ingestor, repo_to_index, parsers, queries)

        updater.run()

        app_context.console.print(style(cs.CLI_MSG_INDEXING_DONE, cs.Color.GREEN))
    except Exception as e:
        app_context.console.print(
            style(cs.CLI_ERR_INDEXING.format(error=e), cs.Color.RED)
        )
        logger.exception(ls.INDEXING_FAILED)
        raise typer.Exit(1) from e


@app.command(name=ch.CLICommandName.CHECK_STALENESS, help=ch.CMD_CHECK_STALENESS)
def check_staleness(
    repo_path: str | None = typer.Option(
        None, "--repo-path", help=ch.HELP_REPO_PATH_RETRIEVAL
    ),
    extension: list[str] | None = typer.Option(
        None,
        "--extension",
        help=ch.HELP_STALENESS_EXTENSION,
    ),
    path_pattern: str | None = typer.Option(
        None,
        "--path-pattern",
        help=ch.HELP_STALENESS_PATH_PATTERN,
    ),
    batch_size: int | None = typer.Option(
        None,
        "--batch-size",
        min=1,
        help=ch.HELP_BATCH_SIZE,
    ),
) -> None:
    target_repo_path = repo_path or settings.TARGET_REPO_PATH
    repo_root = Path(target_repo_path)

    if not repo_root.exists() or not repo_root.is_dir():
        app_context.console.print(
            style(
                cs.CLI_ERR_STALENESS.format(error="Repository path not found"),
                cs.Color.RED,
            )
        )
        raise typer.Exit(1)

    app_context.console.print(
        style(cs.CLI_MSG_STALENESS_SCAN.format(path=repo_root), cs.Color.CYAN)
    )

    effective_batch_size = settings.resolve_batch_size(batch_size)

    try:
        report = _run_staleness_check(
            repo_root, effective_batch_size, extension, path_pattern
        )
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e
    except Exception as e:
        app_context.console.print(
            style(cs.CLI_ERR_STALENESS.format(error=e), cs.Color.RED)
        )
        logger.exception(ls.STALENESS_CHECK_FAILED.format(error=e))
        raise typer.Exit(1) from e

    _print_staleness_report(report, show_paths=True)


@app.command(help=ch.CMD_EXPORT)
def export(
    output: str = typer.Option(..., "-o", "--output", help=ch.HELP_OUTPUT_PATH),
    format_json: bool = typer.Option(
        True, "--json/--no-json", help=ch.HELP_FORMAT_JSON
    ),
    batch_size: int | None = typer.Option(
        None,
        "--batch-size",
        min=1,
        help=ch.HELP_BATCH_SIZE,
    ),
) -> None:
    if not format_json:
        app_context.console.print(style(cs.CLI_ERR_ONLY_JSON, cs.Color.RED))
        raise typer.Exit(1)

    app_context.console.print(style(cs.CLI_MSG_CONNECTING_MEMGRAPH, cs.Color.CYAN))

    effective_batch_size = settings.resolve_batch_size(batch_size)

    try:
        with connect_memgraph(effective_batch_size) as ingestor:
            app_context.console.print(style(cs.CLI_MSG_EXPORTING_DATA, cs.Color.CYAN))
            if not export_graph_to_file(ingestor, output):
                raise typer.Exit(1)

    except Exception as e:
        app_context.console.print(
            style(cs.CLI_ERR_EXPORT_FAILED.format(error=e), cs.Color.RED)
        )
        logger.exception(ls.EXPORT_ERROR.format(error=e))
        raise typer.Exit(1) from e


@app.command(name=ch.CLICommandName.STALENESS_REPORT, help=ch.CMD_STALENESS_REPORT)
def staleness_report(
    repo_path: str | None = typer.Option(
        None, "--repo-path", help=ch.HELP_REPO_PATH_RETRIEVAL
    ),
    output_format: ReportFormat = typer.Option(
        ReportFormat.MARKDOWN, "--format", help=ch.HELP_STALENESS_FORMAT
    ),
    batch_size: int | None = typer.Option(
        None,
        "--batch-size",
        min=1,
        help=ch.HELP_BATCH_SIZE,
    ),
) -> None:
    target_repo_path = repo_path or settings.TARGET_REPO_PATH

    app_context.console.print(style(cs.CLI_MSG_STALENESS_REPORT, cs.Color.CYAN))
    effective_batch_size = settings.resolve_batch_size(batch_size)

    try:
        with connect_memgraph(effective_batch_size) as ingestor:
            reporter = StalenessReporter(ingestor, target_repo_path)
            report = reporter.generate_report()
            output = reporter.render(report, output_format)
            app_context.console.print(output)
    except Exception as e:
        app_context.console.print(
            style(cs.CLI_ERR_STALENESS_REPORT.format(error=e), cs.Color.RED)
        )
        logger.exception(ls.STALENESS_REPORT_FAILED.format(error=e))
        raise typer.Exit(1) from e


@app.command(help=ch.CMD_OPTIMIZE)
def optimize(
    language: str = typer.Argument(
        ...,
        help=ch.HELP_LANGUAGE_ARG,
    ),
    repo_path: str | None = typer.Option(
        None, "--repo-path", help=ch.HELP_REPO_PATH_OPTIMIZE
    ),
    reference_document: str | None = typer.Option(
        None,
        "--reference-document",
        help=ch.HELP_REFERENCE_DOC,
    ),
    orchestrator: str | None = typer.Option(
        None,
        "--orchestrator",
        help=ch.HELP_ORCHESTRATOR,
    ),
    cypher: str | None = typer.Option(
        None,
        "--cypher",
        help=ch.HELP_CYPHER_MODEL,
    ),
    no_confirm: bool = typer.Option(
        False,
        "--no-confirm",
        help=ch.HELP_NO_CONFIRM,
    ),
    batch_size: int | None = typer.Option(
        None,
        "--batch-size",
        min=1,
        help=ch.HELP_BATCH_SIZE,
    ),
) -> None:
    app_context.session.confirm_edits = not no_confirm

    target_repo_path = repo_path or settings.TARGET_REPO_PATH

    try:
        asyncio.run(
            main_optimize_async(
                language,
                target_repo_path,
                reference_document,
                orchestrator,
                cypher,
                batch_size,
            )
        )
    except KeyboardInterrupt:
        app_context.console.print(
            style(cs.CLI_MSG_OPTIMIZATION_TERMINATED, cs.Color.RED)
        )
    except ValueError as e:
        app_context.console.print(
            style(cs.CLI_ERR_STARTUP.format(error=e), cs.Color.RED)
        )


@app.command(name=ch.CLICommandName.MCP_SERVER, help=ch.CMD_MCP_SERVER)
def mcp_server() -> None:
    try:
        from codebase_rag.mcp import main as mcp_main

        asyncio.run(mcp_main())
    except KeyboardInterrupt:
        app_context.console.print(style(cs.CLI_MSG_MCP_TERMINATED, cs.Color.RED))
    except ValueError as e:
        app_context.console.print(
            style(cs.CLI_ERR_CONFIG.format(error=e), cs.Color.RED)
        )
        app_context.console.print(style(cs.CLI_MSG_HINT_TARGET_REPO, cs.Color.YELLOW))
    except Exception as e:
        app_context.console.print(
            style(cs.CLI_ERR_MCP_SERVER.format(error=e), cs.Color.RED)
        )


@app.command(name=ch.CLICommandName.GRAPH_LOADER, help=ch.CMD_GRAPH_LOADER)
def graph_loader_command(
    graph_file: str = typer.Argument(..., help=ch.HELP_GRAPH_FILE),
) -> None:
    from .graph_loader import load_graph

    try:
        graph = load_graph(graph_file)
        summary = graph.summary()

        app_context.console.print(style(cs.CLI_MSG_GRAPH_SUMMARY, cs.Color.GREEN))
        app_context.console.print(f"  Total nodes: {summary['total_nodes']}")
        app_context.console.print(
            f"  Total relationships: {summary['total_relationships']}"
        )
        app_context.console.print(
            f"  Node types: {list(summary['node_labels'].keys())}"
        )
        app_context.console.print(
            f"  Relationship types: {list(summary['relationship_types'].keys())}"
        )
        app_context.console.print(
            f"  Exported at: {summary['metadata']['exported_at']}"
        )

    except Exception as e:
        app_context.console.print(
            style(cs.CLI_ERR_LOAD_GRAPH.format(error=e), cs.Color.RED)
        )
        raise typer.Exit(1) from e


@app.command(
    name=ch.CLICommandName.LANGUAGE,
    help=ch.CMD_LANGUAGE,
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
def language_command(ctx: typer.Context) -> None:
    language_cli(ctx.args, standalone_mode=False)


if __name__ == "__main__":
    app()
