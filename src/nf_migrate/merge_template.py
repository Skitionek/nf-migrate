"""Resolve an nf-core template sync PR with migrations instead of a merge.

`nf-core pipelines sync` opens a PR from a branch holding the new TEMPLATE
commit into dev, and git's merge of the two conflicts wherever the pipeline
diverged from the template. Here dev is upgraded with migrations in a
temporary worktree, and the result is recorded as a merge commit of dev and
the template commit. Pushed to the PR branch, it makes the PR conflict-free
and keeps TEMPLATE in dev's history, so the next sync merges from the right
base.
"""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from nf_migrate.migrations import MigrationError, load_migrations
from nf_migrate.runner import UpgradeReport, upgrade
from nf_migrate.version import NF_CORE_YML, parse_version


@dataclass(frozen=True, slots=True)
class MergeResult:
    target_version: str
    report: UpgradeReport
    commit: str | None

    def render_markdown(self) -> str:
        lines = [f"### nf-migrate: template {self.target_version}", ""]
        lines.append(self.report.render_markdown())
        return "\n".join(lines)


def merge_template(
    repo: Path,
    base: str,
    head: str,
    migrations_dir: Path,
) -> MergeResult:
    """Upgrade `base` to the template version on `head`.

    Returns the merge commit when every migration applied; with a conflict
    no commit is made and the report says what needs resolving by hand.
    """
    base_sha = _git(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    head_sha = _git(repo, "rev-parse", "--verify", f"{head}^{{commit}}")
    head_nf_core_yml = _git(repo, "show", f"{head_sha}:{NF_CORE_YML}")
    target_version = parse_version(head_nf_core_yml)
    if target_version is None:
        raise MigrationError(f"{head} has no nf_core_version in {NF_CORE_YML}")

    chain = load_migrations(migrations_dir)
    with tempfile.TemporaryDirectory() as temporary_directory:
        worktree = Path(temporary_directory) / "base"
        _git(
            repo,
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(worktree),
            base_sha,
        )
        try:
            report = upgrade(worktree, chain, target=target_version)
            commit = None
            if report.succeeded:
                commit = _commit_merge(
                    worktree, base_sha, head_sha, target_version
                )
        finally:
            _git(repo, "worktree", "remove", "--force", str(worktree))

    return MergeResult(target_version, report, commit)


def _commit_merge(
    worktree: Path, base_sha: str, head_sha: str, version: str
) -> str:
    _git(worktree, "add", "--all")
    tree = _git(worktree, "write-tree")
    message = (
        f"Merge nf-core/tools {version} template with nf-migrate\n\n"
        "Applied the template update as migrations instead of a git merge."
    )
    return _git(
        worktree,
        "commit-tree",
        tree,
        "-p",
        base_sha,
        "-p",
        head_sha,
        "-m",
        message,
    )


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
