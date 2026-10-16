"""List every merged template update of every pipeline clone.

A template update is a first-parent commit on the integration branch (dev,
else the default branch) that makes new TEMPLATE commits reachable. Its
from-version is the newest TEMPLATE commit its first parent already had,
its to-version the newest one it brings in.

usage: collect.py PIPELINES_DIR > merges.jsonl
"""

import json
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from nf_migrate.version import parse_version

SUBJECT_VERSION = re.compile(r"nf-core/tools,? version (\S+)")
PULL_REQUEST = re.compile(r"Merge pull request #(\d+)")


def git(repo: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def is_ancestor(repo: Path, ancestor: str, commit: str) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "merge-base",
            "--is-ancestor",
            ancestor,
            commit,
        ]
    )
    return completed.returncode == 0


def template_version(repo: Path, commit: str) -> str | None:
    nf_core_yml = git(repo, "show", f"{commit}:.nf-core.yml", check=False)
    version = parse_version(nf_core_yml) if nf_core_yml else None
    if version is None:
        subject = git(repo, "log", "-1", "--format=%s", commit)
        match = SUBJECT_VERSION.search(subject)
        version = match.group(1) if match else None
    if version is None:
        return None
    return version.strip("\"'").removeprefix("v").rstrip(".,")


def integration_branch(repo: Path) -> str | None:
    branches = git(repo, "branch", "-r", "--format=%(refname:short)")
    names = set(branches.splitlines())
    for candidate in ("origin/dev", "origin/master", "origin/main"):
        if candidate in names:
            return candidate
    return None


def first_containing(
    repo: Path, commits: list[str], template_commit: str, low: int
) -> int | None:
    """Index of the first first-parent commit containing template_commit.

    Containment only grows along first-parent history, so bisect.
    """
    high = len(commits) - 1
    if low > high or not is_ancestor(repo, template_commit, commits[high]):
        return None
    while low < high:
        middle = (low + high) // 2
        if is_ancestor(repo, template_commit, commits[middle]):
            high = middle
        else:
            low = middle + 1
    return low


def collect(repo: Path) -> list[dict]:
    branch = integration_branch(repo)
    has_template = git(
        repo, "rev-parse", "-q", "--verify", "origin/TEMPLATE", check=False
    )
    if branch is None or not has_template:
        return []
    first_parents = git(
        repo, "rev-list", "--first-parent", "--reverse", branch
    ).splitlines()
    template_commits = git(
        repo, "rev-list", "--reverse", "--first-parent", "origin/TEMPLATE"
    ).splitlines()

    # Hand-made fixes on TEMPLATE carry the release before them.
    versions: dict[str, str | None] = {}
    last_version = None
    for template_commit in template_commits:
        last_version = template_version(repo, template_commit) or last_version
        versions[template_commit] = last_version

    # merge index -> template commits it brings in, oldest first
    merged_by: dict[int, list[str]] = {}
    for template_commit in template_commits:
        index = first_containing(repo, first_parents, template_commit, 0)
        if index is None:
            continue
        merged_by.setdefault(index, []).append(template_commit)

    merges: list[dict] = []
    previous_template: str | None = None
    for index in sorted(merged_by):
        newest = merged_by[index][-1]
        commit = first_parents[index]
        # A pipeline created from the template starts at the TEMPLATE
        # commit (or a commit on top of it): no merge to replay.
        parents = git(repo, "rev-list", "--parents", "-n", "1", commit).split()
        is_merge = len(parents) > 2
        if is_merge and previous_template is not None:
            message = git(repo, "log", "-1", "--format=%B", commit)
            pull_request = PULL_REQUEST.search(message)
            merges.append(
                {
                    "pipeline": repo.name,
                    "branch": branch,
                    "merge": commit,
                    "before": parents[1],
                    "template_commit": newest,
                    "previous_template_commit": previous_template,
                    "from": versions[previous_template],
                    "to": versions[newest],
                    "pr": int(pull_request.group(1)) if pull_request else None,
                    "date": git(repo, "log", "-1", "--format=%cs", commit),
                }
            )
        previous_template = newest
    return merges


def main() -> None:
    pipelines = sorted(
        path for path in Path(sys.argv[1]).iterdir() if (path / ".git").is_dir()
    )
    with ProcessPoolExecutor(max_workers=8) as executor:
        for merges in executor.map(collect, pipelines):
            for merge in merges:
                print(json.dumps(merge))


if __name__ == "__main__":
    main()
