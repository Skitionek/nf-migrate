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

from nf_migrate.detect import Detection, detect_version
from nf_migrate.migrations import MigrationError, load_migrations
from nf_migrate.runner import UpgradeReport, upgrade
from nf_migrate.version import NF_CORE_YML, parse_version


@dataclass(frozen=True, slots=True)
class MergeResult:
    target_version: str
    start_version: str | None
    detection: Detection
    report: UpgradeReport
    commit: str | None

    def render_markdown(self) -> str:
        lines = [f"### nf-migrate: template {self.target_version}", ""]
        if self.detection.stamped is None:
            lines.append(
                f"> [!NOTE]\n"
                f"> The base branch has no `nf_core_version`; its files look "
                f"like template {self.detection.version}. Upgraded from "
                f"{self.start_version}."
            )
            lines.append("")
        elif not self.detection.matches_stamp:
            lines.append(
                f"> [!WARNING]\n"
                f"> `nf_core_version` says {self.detection.stamped}, but the "
                f"files look like template {self.detection.version}. "
                f"Upgraded from {self.start_version}."
            )
            lines.append("")
        lines.append(self.report.render_markdown())
        return "\n".join(lines)


def merge_template(
    repo: Path,
    base: str,
    head: str,
    migrations_dir: Path,
    detect: bool = False,
    allow_conflicts: bool = False,
    lint_fix: bool = False,
) -> MergeResult:
    """Upgrade `base` to the template version on `head`.

    Returns the merge commit when every migration applied; with a conflict
    no commit is made and the report says what needs resolving by hand.
    The template version is always detected from the files and reported;
    with `detect`, the upgrade also starts from it when it is older than
    the stamp. With `allow_conflicts` the merge commit holds every change
    that fits, and the report lists the conflicts left for review.
    With `lint_fix`, `nf-core pipelines lint --fix` commits follow the merge
    and the last of them is returned.
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
            detection = detect_version(worktree, chain)
            # Pipelines from before nf-core/tools 3.0 have no stamp.
            is_unstamped = detection.stamped is None
            start_version = None
            if detect or is_unstamped:
                start_version = detection.upgrade_from
            report = upgrade(
                worktree,
                chain,
                target=target_version,
                current=start_version,
                allow_conflicts=allow_conflicts,
            )
            commit = None
            if report.succeeded or allow_conflicts:
                commit = _commit_merge(
                    worktree, base_sha, head_sha, target_version
                )
                if lint_fix:
                    commit = _commit_lint_fixes(
                        worktree, commit, head_sha, target_version
                    )
        finally:
            _git(repo, "worktree", "remove", "--force", str(worktree))

    if start_version is None:
        start_version = detection.stamped
    return MergeResult(target_version, start_version, detection, report, commit)


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


# Each fix is its own commit: the container configs are regenerated from the
# files the first fix leaves, and nf-core refuses to run on a dirty tree.
LINT_FIXES = (
    ("files_unchanged", "style: apply nf-core pipelines lint --fix"),
    ("container_configs", "chore: regenerate container configs"),
)


def _commit_lint_fixes(
    worktree: Path, merge_commit: str, head_sha: str, version: str
) -> str:
    _git(worktree, "reset", "--quiet", "--hard", merge_commit)
    for fix_name, message in LINT_FIXES:
        _run_lint_fix(worktree, fix_name, version)
        _restore_template_logos(worktree, head_sha)
        if _git(worktree, "status", "--porcelain"):
            _git(worktree, "add", "--all")
            _git(worktree, "commit", "--quiet", "-m", message)
    return _git(worktree, "rev-parse", "HEAD")


def _run_lint_fix(worktree: Path, fix_name: str, version: str) -> None:
    # CI lints with the template's own nf-core release, whose expected files
    # differ from a newer release's, so the fix has to run that release.
    command = [
        "uvx",
        f"nf-core@{version}",
        "pipelines",
        "lint",
        "--dir",
        str(worktree),
        "--fix",
        fix_name,
    ]
    try:
        # nf-core exits non-zero while any lint test still fails, which is
        # expected here: only the files it fixed are wanted.
        subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        raise MigrationError(
            "--lint-fix needs uv (uvx) to run the nf-core release of the "
            "template"
        ) from None


def _restore_template_logos(worktree: Path, head_sha: str) -> None:
    # nf-core redraws the logos locally, and CI's lint then reports them as
    # not matching the template, whose branch holds the ones it expects.
    template_files = _git(
        worktree, "ls-tree", "-r", "--name-only", head_sha
    ).splitlines()
    logos = [
        path
        for path in template_files
        if path.endswith(("_logo_light.png", "_logo_dark.png"))
    ]
    if logos:
        _git(worktree, "checkout", head_sha, "--", *logos)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()
