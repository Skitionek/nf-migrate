#!/usr/bin/env python3
"""Shared attempt state for the nf-core template sync skill.

The state lives in the *common* git directory, so every worktree of this
checkout sees the same records and the same claims. `git rev-parse
--git-common-dir` resolves to the one shared `.git` from any worktree, which
is where git itself keeps worktree-shared metadata.

It is deliberately not committed. This is run bookkeeping; the durable
conclusion of a failure is a migration fallback and its test, not a note in a
JSON file.

Layout, under <common-git-dir>/nf-core-template-sync/:

    claims/<slug>.claim    held only while an attempt runs
    attempts/<slug>.json   one record per attempt

One file per attempt means two concurrent agents never write the same file, so
there is no read-modify-write race on a shared blob.

Usage:
    state.py record <key> <status> [--pr URL] [--merge-pr URL] [--notes TEXT]
    state.py get <key>
    state.py list
    state.py migrate <old-state.json> [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

STATUSES = ("success", "failed", "skipped")

# .claude/skills/<skill>/scripts/state.py -> the checkout root.
REPO_ROOT = Path(__file__).resolve().parents[4]


def state_dir() -> Path:
    """The shared state directory, identical from every worktree.

    `NF_TEMPLATE_SYNC_STATE_DIR` overrides it, for tests and for pointing the
    state at a directory that syncs between machines.
    """
    override = os.environ.get("NF_TEMPLATE_SYNC_STATE_DIR")
    if override:
        return Path(override)
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    common = Path(completed.stdout.strip())
    # Returned relative from the main checkout, absolute from a worktree.
    if not common.is_absolute():
        common = REPO_ROOT / common
    return common.resolve() / "nf-core-template-sync"


def claims_dir() -> Path:
    return state_dir() / "claims"


def attempts_dir() -> Path:
    return state_dir() / "attempts"


OPT_OUT_FILE = Path(__file__).resolve().parent.parent / "opt-out.txt"


def opt_outs() -> set[str]:
    """Pipelines that asked not to receive nf-migrate PRs."""
    if not OPT_OUT_FILE.is_file():
        return set()
    repos = set()
    for raw_line in OPT_OUT_FILE.read_text().splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            repos.add(line)
    return repos


def is_opted_out(repo: str) -> bool:
    return repo in opt_outs()


# The checks action.yml makes before it pushes to a sync PR's branch. The title
# of a PR proves nothing, since anyone can give a PR from a fork the sync
# title, and the scripts push a commit built from the PR's tree to the pipeline.
BOT_LOGIN = "nf-core-bot"
SYNC_BRANCH_PREFIX = "nf-core-template-merge-"


def sync_pr_refusal(pr: object) -> str | None:
    """Why this PR is not a sync PR opened by the bot, or None if it is.

    `pr` is the JSON of `gh pr view --json
    author,isCrossRepository,headRefName`. A missing or unexpected field fails
    the check; it never passes it.
    """
    if not isinstance(pr, dict):
        return "unreadable PR data"
    author = pr.get("author")
    login = author.get("login") if isinstance(author, dict) else None
    if login != BOT_LOGIN:
        return f"opened by {login!r}, not {BOT_LOGIN}"
    if pr.get("isCrossRepository") is not False:
        return "comes from a fork"
    head = pr.get("headRefName")
    if not isinstance(head, str) or not head.startswith(SYNC_BRANCH_PREFIX):
        return f"head branch {head!r} is not a {SYNC_BRANCH_PREFIX}* branch"
    return None


def key_slug(key: str) -> str:
    """`nf-core/rnaseq#1980` -> `nf-core_rnaseq_1980`, safe as a filename."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", key)


def record_path(key: str) -> Path:
    return attempts_dir() / f"{key_slug(key)}.json"


def write_record(record: dict) -> Path:
    """Write one record atomically, so a reader never sees a half file."""
    path = record_path(record["key"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)
    return path


def record(
    key: str,
    status: str,
    pr: str = "",
    merge_pr: str = "",
    notes: str = "",
    attempted_at: str | None = None,
    legacy_status: str | None = None,
) -> Path:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, not {status!r}")
    entry = {
        "key": key,
        "status": status,
        "pr": pr,
        "merge_pr": merge_pr,
        "notes": notes,
        "attempted_at": attempted_at or datetime.date.today().isoformat(),
    }
    if legacy_status:
        entry["legacy_status"] = legacy_status
    return write_record(entry)


def load_all() -> dict[str, dict]:
    """Every attempt record, keyed by its original `org/repo#pr` key."""
    directory = attempts_dir()
    if not directory.is_dir():
        return {}
    records = {}
    for path in sorted(directory.glob("*.json")):
        entry = json.loads(path.read_text())
        records[entry["key"]] = entry
    return records


def _migrate_entry(key: str, old: dict) -> dict:
    """Map one legacy `state.json` entry onto the current record shape.

    Two shapes exist in the old file. The modern one carries `pr1`/`pr2`,
    where a non-empty `pr2` means the two-PR era: `pr1` was the no-op merge PR
    and `pr2` the migration. The older one has `status: "attempted"` and
    `my_migration_pr`.
    """
    status = old.get("status", "")
    notes = old.get("notes", "")
    attempted_at = old.get("attempted_at", "")

    if status == "attempted":
        migration_pr = old.get("my_migration_pr", "")
        # A PR exists, so the migration was opened: a success by today's
        # definition. Keep the original word so the rewrite stays auditable.
        return {
            "key": key,
            "status": "success" if migration_pr else "failed",
            "pr": migration_pr,
            "merge_pr": "",
            "notes": notes,
            "attempted_at": attempted_at,
            "legacy_status": status,
        }

    pr1 = old.get("pr1", "") or ""
    pr2 = old.get("pr2", "") or ""
    if pr2:
        migration_pr, merge_pr = pr2, pr1
    else:
        migration_pr, merge_pr = pr1, ""

    return {
        "key": key,
        "status": status,
        "pr": migration_pr,
        "merge_pr": merge_pr,
        "notes": notes,
        "attempted_at": attempted_at,
    }


def migrate(old_file: Path, dry_run: bool = False) -> tuple[int, list[str]]:
    """Convert a legacy `state.json` into one file per attempt.

    Returns the number migrated and the keys that could not be classified.
    """
    attempts = json.loads(old_file.read_text())["attempted"]
    migrated = 0
    unclassified = []
    for key, old in attempts.items():
        entry = _migrate_entry(key, old)
        if entry["status"] not in STATUSES:
            unclassified.append(f"{key}: status={old.get('status')!r}")
            continue
        if not dry_run:
            write_record(entry)
        migrated += 1
    return migrated, unclassified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    record_parser = sub.add_parser("record", help="record one attempt")
    record_parser.add_argument("key", help="e.g. nf-core/rnaseq#1980")
    record_parser.add_argument("status", choices=STATUSES)
    record_parser.add_argument("--pr", default="", help="migration PR URL")
    record_parser.add_argument("--merge-pr", default="", help="legacy merge PR")
    record_parser.add_argument("--notes", default="")

    get_parser = sub.add_parser("get", help="print one record")
    get_parser.add_argument("key")

    sub.add_parser("list", help="print every record as one JSON object")
    sub.add_parser("dir", help="print the shared state directory")
    sub.add_parser("opt-outs", help="print the pipelines that opted out")

    opted_parser = sub.add_parser(
        "is-opted-out", help="exit 0 if this pipeline opted out"
    )
    opted_parser.add_argument("repo", help="e.g. nf-core/oncoanalyser")

    sync_parser = sub.add_parser(
        "check-sync-pr",
        help="read `gh pr view --json author,isCrossRepository,headRefName` "
        "on stdin; print the head branch if it is a bot-opened sync PR, "
        "else say why not and exit 1",
    )
    sync_parser.add_argument("key", help="e.g. nf-core/rnaseq#1980")

    migrate_parser = sub.add_parser("migrate", help="import a legacy file")
    migrate_parser.add_argument("old_file", type=Path)
    migrate_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "record":
        path = record(
            args.key,
            args.status,
            pr=args.pr,
            merge_pr=args.merge_pr,
            notes=args.notes,
        )
        print(f"Recorded {args.key} => {args.status} ({path})")
        return 0

    if args.command == "get":
        records = load_all()
        if args.key not in records:
            print(f"no record for {args.key}", file=sys.stderr)
            return 1
        print(json.dumps(records[args.key], indent=2, sort_keys=True))
        return 0

    if args.command == "list":
        print(json.dumps(load_all(), indent=2, sort_keys=True))
        return 0

    if args.command == "dir":
        print(state_dir())
        return 0

    if args.command == "opt-outs":
        for repo in sorted(opt_outs()):
            print(repo)
        return 0

    if args.command == "is-opted-out":
        return 0 if is_opted_out(args.repo) else 1

    if args.command == "check-sync-pr":
        try:
            pr = json.load(sys.stdin)
        except json.JSONDecodeError:
            pr = None
        reason = sync_pr_refusal(pr)
        if reason:
            print(f"refusing {args.key}: {reason}", file=sys.stderr)
            return 1
        print(pr["headRefName"])
        return 0

    if args.command == "migrate":
        migrated, unclassified = migrate(args.old_file, dry_run=args.dry_run)
        prefix = "would migrate" if args.dry_run else "migrated"
        print(f"{prefix} {migrated} records to {attempts_dir()}")
        for problem in unclassified:
            print(f"UNCLASSIFIED {problem}", file=sys.stderr)
        return 1 if unclassified else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
