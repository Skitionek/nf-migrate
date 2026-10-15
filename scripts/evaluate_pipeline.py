"""Replay a pipeline's real template merges with nf-migrate.

For every TEMPLATE commit the bundled chain covers, find the dev merge that
brought it in, apply the chain to the commit before that merge, and compare
the result with the merge the maintainers resolved by hand. Every operation
is applied (no stop at the first conflict) so all outcomes are counted.

usage: evaluate_pipeline.py REPO WORK_DIR
"""

import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from nf_migrate.cli import BUNDLED_MIGRATIONS
from nf_migrate.migrations import (
    MigrationError,
    load_migrations,
    pending_migrations,
)
from nf_migrate.operations import Outcome, Workspace
from nf_migrate.variables import template_variables
from nf_migrate.version import parse_version


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def show(repo: Path, ref: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def export(repo: Path, ref: str, target: Path) -> None:
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", ref],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["tar", "-x", "-C", str(target)], input=archive.stdout, check=True
    )


def template_merges(repo: Path, revisions: set[str]) -> list[tuple[str, str]]:
    """(dev merge commit, template version) per covered TEMPLATE commit."""
    dev_first_parents = git(
        repo, "rev-list", "--first-parent", "--reverse", "origin/dev"
    ).splitlines()
    template_commits = git(
        repo, "rev-list", "--reverse", "origin/TEMPLATE"
    ).splitlines()

    merges: dict[str, str] = {}
    search_from = 0
    for template_commit in template_commits:
        version = parse_version(
            show(repo, template_commit, ".nf-core.yml") or ""
        )
        if version not in revisions:
            continue
        # Template merges land on dev in order, so resume the scan.
        for index in range(search_from, len(dev_first_parents)):
            commit = dev_first_parents[index]
            is_merged = (
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "merge-base",
                        "--is-ancestor",
                        template_commit,
                        commit,
                    ],
                ).returncode
                == 0
            )
            if is_merged:
                # A later TEMPLATE commit merged in the same PR wins.
                merges[commit] = version
                search_from = index
                break
    return list(merges.items())


def evaluate_step(
    repo: Path, work: Path, merge: str, target: str, chain: list
) -> dict:
    before_ref = git(repo, "rev-parse", "--short", f"{merge}^1")
    after_ref = git(repo, "rev-parse", "--short", merge)
    before = work / "before"
    after = work / "after"
    export(repo, before_ref, before)
    export(repo, after_ref, after)

    nf_core_yml = (before / ".nf-core.yml").read_text()
    current = parse_version(nf_core_yml)
    step = {
        "before": before_ref,
        "after": after_ref,
        "from": current,
        "to": target,
    }
    try:
        migrations = pending_migrations(chain, current, target)
    except MigrationError as error:
        step["skipped"] = str(error)
        return step

    workspace = Workspace(before, template_variables(nf_core_yml))
    outcomes: Counter = Counter()
    conflicts: list[str] = []
    for migration in migrations:
        for operation in migration.operations:
            result = operation.apply(workspace)
            outcomes[result.outcome.name] += 1
            if result.outcome is Outcome.CONFLICT:
                conflicts.append(f"{result.path}: {result.message}")

    touched = workspace.changed_paths()
    identical = [
        path
        for path in touched
        if workspace.read(path)
        == ((after / path).read_text() if (after / path).is_file() else None)
    ]
    step.update(
        outcomes=dict(outcomes),
        conflicts=conflicts,
        touched=len(touched),
        identical=len(identical),
        differs=[path for path in touched if path not in identical],
    )
    return step


def main() -> None:
    repo = Path(sys.argv[1])
    work = Path(sys.argv[2])
    chain = load_migrations(BUNDLED_MIGRATIONS)
    revisions = {migration.revision for migration in chain}

    steps = [
        evaluate_step(repo, work, merge, target, chain)
        for merge, target in template_merges(repo, revisions)
    ]
    print(json.dumps({"pipeline": repo.name, "steps": steps}, indent=2))


if __name__ == "__main__":
    main()
