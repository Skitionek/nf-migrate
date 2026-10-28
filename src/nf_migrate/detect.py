"""Work out a pipeline's template version from its files.

`nf_core_version` in .nf-core.yml can be wrong, for example after a template
update was reverted without resetting it. The migrations themselves say
what the template looks like on each side of a release: an operation that
still applies is evidence the pipeline is before that release, and one that
is already applied is evidence it is past it. The detected version is the
point in the chain that the most evidence agrees with.
"""

from dataclasses import dataclass
from pathlib import Path

from nf_migrate.migrations import Migration
from nf_migrate.operations import Outcome, Workspace
from nf_migrate.runner import stamp_workspace
from nf_migrate.variables import pipeline_variables
from nf_migrate.version import NF_CORE_YML, read_version


@dataclass(frozen=True, slots=True)
class MigrationEvidence:
    revision: str
    applicable: int
    already_applied: int
    conflicts: int


@dataclass(frozen=True, slots=True)
class Detection:
    version: str
    stamped: str | None
    evidence: list[MigrationEvidence]
    # Where an upgrade should start: the detected version only when it is
    # older than the stamp. Migrations already applied are no-ops, so
    # starting early is safe; starting past the stamp could skip changes a
    # partly updated pipeline still lacks.
    upgrade_from: str

    @property
    def matches_stamp(self) -> bool:
        return self.version == self.stamped

    def render(self) -> str:
        lines = [
            f"nf_core_version in {NF_CORE_YML}: {self.stamped}",
            f"files look like: {self.version}",
            "",
            "revision  applicable  already  conflict",
        ]
        for item in self.evidence:
            lines.append(
                f"{item.revision:<9} {item.applicable:>10} "
                f"{item.already_applied:>8} {item.conflicts:>9}"
            )
        return "\n".join(lines)


def detect_version(project: Path, chain: list[Migration]) -> Detection:
    stamped = read_version(project)
    if not chain:
        raise ValueError("cannot detect a version without migrations")

    variables = pipeline_variables(project)
    evidence = [
        _migration_evidence(project, variables, migration)
        for migration in chain
    ]

    # Candidate k means the first k migrations are applied.
    candidates = [chain[0].down_revision] + [
        migration.revision for migration in chain
    ]
    scores = [
        sum(item.already_applied for item in evidence[:applied_count])
        + sum(item.applicable for item in evidence[applied_count:])
        for applied_count in range(len(candidates))
    ]
    best_score = max(scores)
    best_versions = [
        version
        for version, score in zip(candidates, scores, strict=True)
        if score == best_score
    ]

    # Without clear evidence against it, trust the stamp; otherwise prefer
    # the newest of the equally good versions.
    if stamped in best_versions:
        detected = stamped
    else:
        detected = best_versions[-1]

    upgrade_from = detected
    if stamped in candidates:
        is_older = candidates.index(detected) < candidates.index(stamped)
        upgrade_from = detected if is_older else stamped
    return Detection(detected, stamped, evidence, upgrade_from)


def _migration_evidence(
    project: Path, variables: dict[str, str], migration: Migration
) -> MigrationEvidence:
    # A fresh workspace per migration: each is checked against the files as
    # they are on disk, not as earlier migrations would leave them.
    workspace = Workspace(project, variables)
    stamp_workspace(workspace, migration.revision)
    counts = {outcome: 0 for outcome in Outcome}
    for operation in migration.operations:
        raw = operation.apply(workspace)
        results = raw if isinstance(raw, list) else [raw]
        for result in results:
            counts[result.outcome] += 1
    return MigrationEvidence(
        revision=migration.revision,
        applicable=counts[Outcome.APPLIED],
        already_applied=counts[Outcome.ALREADY_APPLIED],
        conflicts=counts[Outcome.CONFLICT],
    )
