"""Replay a pipeline's real template merges with nf-migrate.

For every TEMPLATE commit the bundled chain covers, find the dev merge that
brought it in, apply the chain to the commit before that merge, and compare
the result with the merge the maintainers resolved by hand. Migrations run
as `upgrade --allow-conflicts` does, so all outcomes are counted; with
`--partial-files`, as `upgrade --partial-files` does.

usage: evaluate_pipeline.py [--partial-files] REPO WORK_DIR
"""

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from nf_migrate.cli import BUNDLED_MIGRATIONS
from nf_migrate.detect import detect_version
from nf_migrate.migrations import (
    MigrationError,
    load_migrations,
    pending_migrations,
)
from nf_migrate.operations import Outcome, Workspace
from nf_migrate.runner import run_migrations
from nf_migrate.variables import pipeline_variables
from nf_migrate.version import parse_version, read_version

# Before 2.14 TEMPLATE commits carry no nf_core_version; their subject does.
TEMPLATE_SUBJECT_VERSION = re.compile(r"nf-core/tools,? version (\S+)")


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
        version = template_version(repo, template_commit)
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
                # A pipeline created from the template starts at the
                # TEMPLATE commit itself; that is no merge to replay.
                if commit == template_commit:
                    break
                # A later TEMPLATE commit merged in the same PR wins.
                merges[commit] = version
                search_from = index
                break
    return list(merges.items())


def template_version(repo: Path, template_commit: str) -> str | None:
    version = parse_version(show(repo, template_commit, ".nf-core.yml") or "")
    if version is not None:
        return version
    subject = git(repo, "log", "-1", "--format=%s", template_commit)
    match = TEMPLATE_SUBJECT_VERSION.search(subject)
    return match.group(1) if match else None


def evaluate_step(
    repo: Path,
    work: Path,
    merge: str,
    target: str,
    chain: list,
    partial_files: bool,
) -> dict:
    before_ref = git(repo, "rev-parse", "--short", f"{merge}^1")
    after_ref = git(repo, "rev-parse", "--short", merge)
    before = work / "before"
    after = work / "after"
    export(repo, before_ref, before)
    export(repo, after_ref, after)

    detected = detect_version(before, chain).version
    # Pipelines from before nf-core/tools 3.0 have no stamp to start from.
    current = read_version(before) or detected
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

    step["detected"] = detected
    workspace = Workspace(before, pipeline_variables(before))
    report = run_migrations(
        workspace,
        migrations,
        allow_conflicts=True,
        partial_files=partial_files,
    )
    outcomes: Counter = Counter()
    conflicts: list[str] = []
    for migration_report in report.migrations:
        for result in migration_report.results:
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
        superseded_manual_steps=report.superseded_manual_steps,
        outcomes=dict(outcomes),
        conflicts=conflicts,
        touched=len(touched),
        identical=len(identical),
        differs=[path for path in touched if path not in identical],
    )
    return step


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--partial-files", action="store_true")
    arguments = parser.parse_args()

    repo = arguments.repo
    chain = load_migrations(BUNDLED_MIGRATIONS)
    revisions = {migration.revision for migration in chain}

    steps = [
        evaluate_step(
            repo, arguments.work, merge, target, chain, arguments.partial_files
        )
        for merge, target in template_merges(repo, revisions)
    ]
    dev_commit = git(repo, "rev-parse", "origin/dev")
    result = {"pipeline": repo.name, "dev": dev_commit, "steps": steps}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
