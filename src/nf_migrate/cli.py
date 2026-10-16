"""Command line entry point: nf-migrate <command>."""

import argparse
import sys
from pathlib import Path

from nf_migrate.autogenerate import generate_migration
from nf_migrate.detect import detect_version
from nf_migrate.merge_template import merge_template
from nf_migrate.migrations import MigrationError, load_migrations
from nf_migrate.runner import upgrade
from nf_migrate.variables import TemplateVariableError
from nf_migrate.version import NF_CORE_YML, read_version, stamp_version

BUNDLED_MIGRATIONS = Path(__file__).parent / "nf_core_migrations"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        return arguments.handler(arguments)
    except (MigrationError, TemplateVariableError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nf-migrate", description=__doc__)
    parser.add_argument(
        "--project", type=Path, default=Path("."), help="pipeline directory"
    )
    parser.add_argument(
        "--migrations",
        type=Path,
        default=BUNDLED_MIGRATIONS,
        help="directory of migration files (default: the bundled chain)",
    )
    commands = parser.add_subparsers(required=True)

    current = commands.add_parser("current", help="show the template version")
    current.set_defaults(handler=_current)

    detect = commands.add_parser(
        "detect", help="work out the template version from the files"
    )
    detect.set_defaults(handler=_detect)

    history = commands.add_parser("history", help="list migrations in order")
    history.set_defaults(handler=_history)

    upgrade_command = commands.add_parser("upgrade", help="apply migrations")
    upgrade_command.add_argument("target", nargs="?", default="head")
    upgrade_command.add_argument(
        "--dry-run", action="store_true", help="print the diff, write nothing"
    )
    upgrade_command.add_argument(
        "--detect",
        action="store_true",
        help="start from the version the files look like, if older than "
        "nf_core_version",
    )
    upgrade_command.add_argument(
        "--allow-conflicts",
        action="store_true",
        help="apply every change that fits and report the conflicts",
    )
    upgrade_command.add_argument(
        "--partial-files",
        action="store_true",
        help="like --allow-conflicts, but also keep the changes that fit in "
        "a file with a conflict",
    )
    upgrade_command.set_defaults(handler=_upgrade)

    stamp = commands.add_parser(
        "stamp", help="record a version without running migrations"
    )
    stamp.add_argument("revision")
    stamp.set_defaults(handler=_stamp)

    revision = commands.add_parser(
        "revision", help="generate a migration from two TEMPLATE commits"
    )
    revision.add_argument("old_ref")
    revision.add_argument("new_ref")
    revision.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="git repo holding the TEMPLATE branch",
    )
    revision.set_defaults(handler=_revision)

    merge = commands.add_parser(
        "merge-template",
        help="resolve a template sync PR: upgrade BASE to HEAD's version "
        "and print a merge commit of both",
    )
    merge.add_argument("base", help="branch the PR targets, e.g. origin/dev")
    merge.add_argument("head", help="the PR's template branch")
    merge.add_argument("--repo", type=Path, default=Path("."))
    merge.add_argument(
        "--report-file", type=Path, help="write the Markdown report here"
    )
    merge.add_argument(
        "--detect",
        action="store_true",
        help="start from the version the files look like, if older than "
        "nf_core_version",
    )
    merge.add_argument(
        "--allow-conflicts",
        action="store_true",
        help="commit every change that fits and report the conflicts",
    )
    merge.add_argument(
        "--partial-files",
        action="store_true",
        help="like --allow-conflicts, but also keep the changes that fit in "
        "a file with a conflict",
    )
    merge.set_defaults(handler=_merge_template)

    return parser


def _merge_template(arguments: argparse.Namespace) -> int:
    result = merge_template(
        arguments.repo,
        arguments.base,
        arguments.head,
        arguments.migrations,
        detect=arguments.detect,
        allow_conflicts=arguments.allow_conflicts,
        partial_files=arguments.partial_files,
    )
    if arguments.report_file is not None:
        arguments.report_file.write_text(result.render_markdown())
    print(result.report.render() or "already up to date", file=sys.stderr)
    if result.commit is None:
        return 1
    print(result.commit)
    return 0


def _current(arguments: argparse.Namespace) -> int:
    print(read_version(arguments.project))
    return 0


def _detect(arguments: argparse.Namespace) -> int:
    chain = load_migrations(arguments.migrations)
    detection = detect_version(arguments.project, chain)
    print(detection.render())
    return 0


def _history(arguments: argparse.Namespace) -> int:
    current_version = read_version(arguments.project)
    for migration in load_migrations(arguments.migrations):
        marker = " (current)" if migration.revision == current_version else ""
        print(f"{migration.down_revision} -> {migration.revision}{marker}")
    return 0


def _upgrade(arguments: argparse.Namespace) -> int:
    chain = load_migrations(arguments.migrations)
    start_version = None
    # Pipelines from before nf-core/tools 3.0 have no stamp to start from.
    is_unstamped = read_version(arguments.project) is None
    if arguments.detect or is_unstamped:
        detection = detect_version(arguments.project, chain)
        start_version = detection.upgrade_from
        if is_unstamped:
            print(
                f"no nf_core_version; files look like {detection.version}",
                file=sys.stderr,
            )
        elif not detection.matches_stamp:
            print(
                f"nf_core_version says {detection.stamped}, files look like "
                f"{detection.version}; upgrading from {start_version}",
                file=sys.stderr,
            )
    report = upgrade(
        arguments.project,
        chain,
        target=arguments.target,
        dry_run=arguments.dry_run,
        current=start_version,
        allow_conflicts=arguments.allow_conflicts,
        partial_files=arguments.partial_files,
    )
    if arguments.dry_run:
        print(report.diff, end="")
    print(report.render() or "already up to date", file=sys.stderr)
    return 0 if report.succeeded else 1


def _stamp(arguments: argparse.Namespace) -> int:
    nf_core_yml = arguments.project / NF_CORE_YML
    # Pipelines from before nf-core/tools 2.3 have no .nf-core.yml yet.
    content = nf_core_yml.read_text() if nf_core_yml.exists() else ""
    nf_core_yml.write_text(stamp_version(content, arguments.revision))
    return 0


def _revision(arguments: argparse.Namespace) -> int:
    generated = generate_migration(
        arguments.repo, arguments.old_ref, arguments.new_ref
    )

    arguments.migrations.mkdir(parents=True, exist_ok=True)
    file_name = f"v{generated.revision.replace('.', '_')}.py"
    migration_path = arguments.migrations / file_name
    migration_path.write_text(generated.source)
    print(migration_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
