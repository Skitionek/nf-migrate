"""Apply pending migrations to a pipeline, one migration at a time."""

from dataclasses import dataclass, field
from pathlib import Path

from nf_migrate.migrations import Migration, pending_migrations
from nf_migrate.operations import OperationResult, Outcome, Workspace
from nf_migrate.variables import template_variables
from nf_migrate.version import NF_CORE_YML, read_version, stamp_version


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
                if result.outcome in (Outcome.CONFLICT, Outcome.MANUAL):
                    label = result.outcome.name
                    lines.append(f"  {label} {result.path}: {result.message}")
        return "\n".join(lines)


def upgrade(
    project: Path,
    chain: list[Migration],
    target: str,
    dry_run: bool = False,
) -> UpgradeReport:
    """Upgrade `project` to `target`, stopping at the first conflict.

    Each migration either applies completely, including its version stamp,
    or leaves the pipeline untouched — the same guarantee Alembic gets from
    running each revision in a transaction.
    """
    current = read_version(project)
    report = UpgradeReport()

    # A dry run keeps one workspace so later migrations see earlier changes.
    nf_core_yml = (project / NF_CORE_YML).read_text()
    workspace = Workspace(project, template_variables(nf_core_yml))
    for migration in pending_migrations(chain, current, target):
        migration_report = _apply_migration(migration, workspace)
        report.migrations.append(migration_report)
        if migration_report.conflicts:
            break
        if not dry_run:
            workspace.commit()

    if dry_run:
        report.diff = workspace.diff()
    return report


def _apply_migration(
    migration: Migration, workspace: Workspace
) -> MigrationReport:
    checkpoint = workspace.snapshot()

    results = [operation.apply(workspace) for operation in migration.operations]
    migration_report = MigrationReport(migration.revision, results)

    if migration_report.conflicts:
        workspace.restore(checkpoint)
        return migration_report

    nf_core_yml = workspace.read(NF_CORE_YML) or ""
    workspace.write(NF_CORE_YML, stamp_version(nf_core_yml, migration.revision))
    return migration_report
