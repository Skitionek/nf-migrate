"""Apply pending migrations to a pipeline, one migration at a time."""

from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from pathlib import Path

from nf_migrate.migrations import Migration, pending_migrations
from nf_migrate.operations import OperationResult, Outcome, Workspace
from nf_migrate.variables import pipeline_variables
from nf_migrate.version import NF_CORE_YML, read_version, stamp_version

# Files the template only seeds: pipelines rewrite them, so a template
# change that no longer fits is a suggestion, not a conflict.
PIPELINE_OWNED_DOCS = ("README.md", "CHANGELOG.md", "CITATIONS.md", "docs/*.md")


@dataclass(slots=True)
class MigrationReport:
    revision: str
    results: list[OperationResult]

    @property
    def conflicts(self) -> list[OperationResult]:
        return [
            result
            for result in self.results
            if result.outcome is Outcome.CONFLICT
        ]


@dataclass(slots=True)
class UpgradeReport:
    migrations: list[MigrationReport] = field(default_factory=list)
    diff: str = ""

    @property
    def failed_revision(self) -> str | None:
        for migration in self.migrations:
            if migration.conflicts:
                return migration.revision
        return None

    @property
    def succeeded(self) -> bool:
        return self.failed_revision is None

    def render(self) -> str:
        lines: list[str] = []
        for migration in self.migrations:
            counts = {outcome: 0 for outcome in Outcome}
            for result in migration.results:
                counts[result.outcome] += 1
            summary = ", ".join(
                f"{count} {outcome.value}" for outcome, count in counts.items()
            )
            lines.append(f"{migration.revision}: {summary}")
            for result in migration.results:
                reported = (Outcome.CONFLICT, Outcome.MANUAL, Outcome.SUGGESTED)
                if result.outcome in reported:
                    label = result.outcome.name
                    lines.append(f"  {label} {result.path}: {result.message}")
        return "\n".join(lines)

    def render_markdown(self) -> str:
        """The report as a PR comment: conflicts, then manual steps."""
        lines: list[str] = []
        for migration in self.migrations:
            counts = {outcome: 0 for outcome in Outcome}
            for result in migration.results:
                counts[result.outcome] += 1
            summary = ", ".join(
                f"{count} {outcome.value}" for outcome, count in counts.items()
            )
            lines.append(f"#### {migration.revision}\n\n{summary}\n")
            for result in migration.results:
                if result.outcome is Outcome.CONFLICT:
                    lines.append(f"- :x: `{result.path}`: {result.message}")
                    if result.suggestion:
                        lines.append(_suggestion_block(result.suggestion))
                elif result.outcome is Outcome.MANUAL:
                    lines.append(f"- [ ] `{result.path}`: {result.message}")
                elif result.outcome is Outcome.SUGGESTED:
                    lines.append(
                        f"- :bulb: `{result.path}`: template change to "
                        f"consider ({result.message})"
                    )
                    if result.suggestion:
                        lines.append(_suggestion_block(result.suggestion))
            lines.append("")
        return "\n".join(lines)


def upgrade(
    project: Path,
    chain: list[Migration],
    target: str,
    dry_run: bool = False,
    current: str | None = None,
    allow_conflicts: bool = False,
    partial_files: bool = False,
) -> UpgradeReport:
    """Upgrade `project` to `target`, stopping at the first conflict.

    Each migration either applies completely, including its version stamp,
    or leaves the pipeline untouched — the same guarantee Alembic gets from
    running each revision in a transaction.

    With `allow_conflicts`, every release keeps the changes that fit and the
    upgrade carries on to `target`; the report lists what is left to do by
    hand, so `succeeded` stays False. A file with a conflict is left as it
    was before the release, unless `partial_files` keeps the changes that
    fit in it too.
    """
    # Keeping partial files only makes sense when conflicts are allowed.
    allow_conflicts = allow_conflicts or partial_files
    # `current` overrides nf_core_version, e.g. with a detected version.
    if current is None:
        current = read_version(project)

    report = UpgradeReport()

    # A dry run keeps one workspace so later migrations see earlier changes.
    workspace = Workspace(project, pipeline_variables(project))
    for migration in pending_migrations(chain, current, target):
        migration_report = _apply_migration(
            migration, workspace, allow_conflicts, partial_files
        )
        report.migrations.append(migration_report)
        if migration_report.conflicts and not allow_conflicts:
            break
        if not dry_run:
            workspace.commit()

    if dry_run:
        report.diff = workspace.diff()
    return report


def _apply_migration(
    migration: Migration,
    workspace: Workspace,
    allow_conflicts: bool = False,
    partial_files: bool = False,
) -> MigrationReport:
    checkpoint = workspace.snapshot()

    # Migrations are generated against .nf-core.yml already stamped with
    # their revision, so stamp it the same way before applying them.
    stamp_workspace(workspace, migration.revision)
    results = [operation.apply(workspace) for operation in migration.operations]
    results = [_suggest_for_owned_docs(result) for result in results]
    migration_report = MigrationReport(migration.revision, results)

    if migration_report.conflicts and not allow_conflicts:
        workspace.restore(checkpoint)
        return migration_report
    if migration_report.conflicts and not partial_files:
        migration_report = _hold_back_conflicting_files(
            migration_report, workspace, checkpoint
        )

    # Again, in case conflicts held .nf-core.yml back to before this release.
    stamp_workspace(workspace, migration.revision)
    return migration_report


def stamp_workspace(workspace: Workspace, revision: str) -> None:
    nf_core_yml = workspace.read(NF_CORE_YML) or ""
    workspace.write(NF_CORE_YML, stamp_version(nf_core_yml, revision))


def _suggest_for_owned_docs(result: OperationResult) -> OperationResult:
    is_owned_doc = any(
        fnmatch(result.path, pattern) for pattern in PIPELINE_OWNED_DOCS
    )
    if result.outcome is Outcome.CONFLICT and is_owned_doc:
        return replace(result, outcome=Outcome.SUGGESTED)
    return result


def _hold_back_conflicting_files(
    migration_report: MigrationReport,
    workspace: Workspace,
    checkpoint: dict[str, str | None],
) -> MigrationReport:
    """Leave every file with a conflict as it was before this release.

    A file that got some of a release's changes but not others can end up
    half converted and broken, so its changes are reported together for a
    maintainer instead.
    """
    conflicting_paths = {
        conflict.path for conflict in migration_report.conflicts
    }
    workspace.restore_paths(checkpoint, conflicting_paths)

    results: list[OperationResult] = []
    for result in migration_report.results:
        is_held_back = (
            result.path in conflicting_paths
            and result.outcome is Outcome.APPLIED
        )
        if is_held_back:
            message = "held back: another change to this file conflicts"
            result = replace(result, outcome=Outcome.CONFLICT, message=message)
        results.append(result)
    return MigrationReport(migration_report.revision, results)


def _suggestion_block(diff: str) -> str:
    """A collapsed diff of the template change a conflict could not place."""
    fence = "````" if "```" in diff else "```"
    body = diff if diff.endswith("\n") else diff + "\n"
    indented = "".join(f"  {line}" for line in body.splitlines(keepends=True))
    return (
        "\n  <details><summary>template change</summary>\n\n"
        f"  {fence}diff\n{indented}  {fence}\n\n  </details>\n"
    )
