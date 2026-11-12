"""Check migrations against the template renders they were made from.

For each migration: applied to its down_revision's render it must give its
own render (every scored text file identical) with no conflict, and on its
own render every operation must be already applied.

usage: check_renders.py HISTORY_REPO MIGRATIONS_DIR [VERSION ...]
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evaluate import History, is_scored  # noqa: E402
from gitread import GitWorkspace  # noqa: E402

from nf_migrate.migrations import load_migrations  # noqa: E402
from nf_migrate.operations import Outcome  # noqa: E402
from nf_migrate.runner import stamp_workspace  # noqa: E402
from nf_migrate.version import NF_CORE_YML, stamp_version  # noqa: E402


def check(history: History, migration) -> list[str]:
    problems: list[str] = []
    old, new = migration.down_revision, migration.revision
    variables = history.render_variables(new)

    # Upgrading the previous render gives this render.
    workspace = GitWorkspace(history.reader, f"v{old}", variables)
    stamp_workspace(workspace, new)
    for index, operation in enumerate(migration.operations):
        result = operation.apply(workspace)
        if result.outcome is Outcome.CONFLICT:
            problems.append(
                f"{new} on v{old}: op {index} {result.path} conflicts: "
                f"{result.message}"
            )
    changed = subprocess.run(
        [
            "git",
            "-C",
            str(history.repo),
            "diff",
            "--name-only",
            "-z",
            f"v{old}",
            f"v{new}",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    candidates = {path for path in changed if path} | set(
        workspace.changed_paths()
    )
    for path in sorted(candidates):
        if not is_scored(path) or path == ".nf-migrate-render.yml":
            continue
        expected = history.reader.read(f"v{new}", path)
        actual = workspace.read(path)
        # Renders before 3.0 carry no stamp; the runner always writes one.
        if path == NF_CORE_YML:
            expected = stamp_version(expected or "", new)
        # Left out on purpose: autogenerate.UNINTENDED_CHANGES.
        if (new, path) == ("2.3.1", "CHANGELOG.md"):
            continue
        if expected != actual:
            problems.append(f"{new} on v{old}: {path} differs from v{new}")

    # On its own render, everything is already there.
    workspace = GitWorkspace(history.reader, f"v{new}", variables)
    stamp_workspace(workspace, new)
    for index, operation in enumerate(migration.operations):
        result = operation.apply(workspace)
        if result.outcome in (Outcome.APPLIED, Outcome.CONFLICT):
            problems.append(
                f"{new} on v{new}: op {index} {result.path} "
                f"{result.outcome.name} {result.message}"
            )
    return problems


def main() -> None:
    history = History(Path(sys.argv[1]))
    chain = load_migrations(Path(sys.argv[2]))
    wanted = set(sys.argv[3:])
    problems: list[str] = []
    for migration in chain:
        if wanted and migration.revision not in wanted:
            continue
        problems.extend(check(history, migration))
    print("\n".join(problems) or "all renders consistent")
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
