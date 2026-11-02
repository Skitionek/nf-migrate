#!/usr/bin/env python3
"""Tests for the shared attempt state.

Not picked up by the repository suite (`testpaths = ["tests"]` covers the
package only). Run them explicitly:

    uv run pytest .claude/skills/nf-core-template-sync/scripts/test_state.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import state  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
STATE_LIB = SCRIPTS / "state-lib.sh"


def bash(script: str, env_dir: Path | None = None) -> str:
    """Run a snippet with state-lib.sh sourced, and return its stdout."""
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(Path.home())}
    if env_dir is not None:
        env["NF_TEMPLATE_SYNC_STATE_DIR"] = str(env_dir)
    completed = subprocess.run(
        ["bash", "-c", f'source "{STATE_LIB}"\n{script}'],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return completed.stdout


# key_slug


def test_key_slug_makes_a_pr_key_safe_as_a_filename() -> None:
    # Given a key with the separators nf-core keys use
    key = "nf-core/rnaseq#1980"

    # When it is slugged
    slug = state.key_slug(key)

    # Then it is a single filename-safe token
    assert slug == "nf-core_rnaseq_1980"
    assert "/" not in slug and "#" not in slug


def test_key_slug_agrees_between_python_and_bash() -> None:
    # Given the same key handed to both implementations
    key = "nf-core/rnaseq#1980"

    # When each slugs it
    from_python = state.key_slug(key)
    from_bash = bash(f'nf_key_slug "{key}"').strip()

    # Then they agree, so a claim and its record share one name
    assert from_python == from_bash


# state_dir


def test_state_dir_points_at_the_shared_git_dir_not_the_worktree() -> None:
    # Given a checkout that may itself be a linked worktree
    common = subprocess.run(
        ["git", "-C", str(state.REPO_ROOT), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = state.REPO_ROOT / common_path

    # When the state directory is resolved
    resolved = state.state_dir()

    # Then it sits under the common git dir, which every worktree shares,
    # and never under this worktree's own private git dir
    assert resolved.is_absolute()
    assert resolved.is_relative_to(common_path.resolve())
    assert "worktrees" not in resolved.parts


def test_state_dir_honours_the_env_override(tmp_path: Path) -> None:
    # Given an override pointing somewhere else
    import os

    os.environ["NF_TEMPLATE_SYNC_STATE_DIR"] = str(tmp_path)
    try:
        # When the state directory is resolved
        resolved = state.state_dir()

        # Then the override wins
        assert resolved == tmp_path
    finally:
        del os.environ["NF_TEMPLATE_SYNC_STATE_DIR"]


# opt-outs


def test_oncoanalyser_is_opted_out() -> None:
    # Given the shipped opt-out list
    # When oncoanalyser is checked
    # Then it is opted out, so no agent will attempt it
    assert state.is_opted_out("nf-core/oncoanalyser")


def test_a_pipeline_that_never_asked_is_not_opted_out() -> None:
    # Given the shipped opt-out list
    # When a pipeline that never asked is checked
    # Then it is not opted out
    assert not state.is_opted_out("nf-core/rnaseq")


def test_comments_and_blank_lines_are_not_read_as_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a list with comments, a trailing comment and blank lines
    opt_out = tmp_path / "opt-out.txt"
    opt_out.write_text(
        "# a heading\n"
        "\n"
        "nf-core/oncoanalyser\n"
        "nf-core/sarek  # asked on some date\n"
    )
    monkeypatch.setattr(state, "OPT_OUT_FILE", opt_out)

    # When the list is read
    repos = state.opt_outs()

    # Then only the repository names survive
    assert repos == {"nf-core/oncoanalyser", "nf-core/sarek"}


def test_a_missing_opt_out_file_means_nobody_opted_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given no opt-out file at all
    monkeypatch.setattr(state, "OPT_OUT_FILE", tmp_path / "absent.txt")

    # When the list is read
    # Then it is empty rather than an error
    assert state.opt_outs() == set()


# records


def test_recording_an_attempt_then_loading_it_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given an empty shared state directory
    monkeypatch.setattr(state, "state_dir", lambda: tmp_path)

    # When one attempt is recorded
    state.record(
        "nf-core/rnaseq#1980",
        "success",
        pr="https://github.com/nf-core/rnaseq/pull/1981",
    )

    # Then it comes back under its original key
    records = state.load_all()
    assert list(records) == ["nf-core/rnaseq#1980"]
    assert records["nf-core/rnaseq#1980"]["status"] == "success"
    assert records["nf-core/rnaseq#1980"]["pr"].endswith("/1981")


def test_notes_keep_characters_that_used_to_corrupt_the_state_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a note with the quoting that broke the old heredoc writer
    monkeypatch.setattr(state, "state_dir", lambda: tmp_path)
    notes = 'old text not found: "nf_core_version" and a \\ and $(whoami)'

    # When it is recorded
    state.record("nf-core/rnaseq#1980", "failed", notes=notes)

    # Then it is stored verbatim, unexpanded
    stored = state.load_all()["nf-core/rnaseq#1980"]["notes"]
    assert stored == notes


def test_an_unknown_status_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given an empty shared state directory
    monkeypatch.setattr(state, "state_dir", lambda: tmp_path)

    # When a status outside the vocabulary is recorded
    # Then it is refused rather than silently stored
    with pytest.raises(ValueError, match="status must be one of"):
        state.record("nf-core/rnaseq#1980", "attempted")


def test_concurrent_agents_get_exactly_one_claim(tmp_path: Path) -> None:
    # Given eight agents racing for the same PR, as a batch does
    script = """
    for i in $(seq 1 8); do
        ( nf_claim "nf-core/rnaseq#1980" >/dev/null && echo won ) &
    done
    wait
    """

    # When they all try to claim it
    output = bash(script, env_dir=tmp_path)

    # Then exactly one wins, so only one agent opens a PR
    assert output.count("won") == 1
    assert len(list((tmp_path / "claims").glob("*.claim"))) == 1


# migration


def test_migrating_a_two_pr_entry_keeps_the_migration_pr_as_the_pr() -> None:
    # Given a record from the era that opened a no-op merge PR first
    old = {
        "status": "success",
        "pr1": "https://github.com/nf-core/bamtofastq/pull/162",
        "pr2": "https://github.com/nf-core/bamtofastq/pull/163",
        "attempted_at": "2026-10-27",
        "notes": "",
    }

    # When it is migrated
    entry = state._migrate_entry("nf-core/bamtofastq#161", old)

    # Then the migration PR becomes `pr` and the merge PR is kept apart
    assert entry["pr"].endswith("/163")
    assert entry["merge_pr"].endswith("/162")
    assert entry["status"] == "success"
    assert entry["attempted_at"] == "2026-10-27"


def test_migrating_a_one_pr_entry_leaves_no_merge_pr() -> None:
    # Given a record written after the single-PR change
    old = {
        "status": "success",
        "pr1": "https://github.com/nf-core/rnaseq/pull/1981",
        "pr2": "",
        "attempted_at": "2026-11-01",
        "notes": "",
    }

    # When it is migrated
    entry = state._migrate_entry("nf-core/rnaseq#1980", old)

    # Then its only PR is the migration PR
    assert entry["pr"].endswith("/1981")
    assert entry["merge_pr"] == ""


def test_migrating_a_legacy_attempted_entry_records_the_original_word() -> None:
    # Given the older shape, which used a status outside today's vocabulary
    old = {
        "status": "attempted",
        "my_migration_pr": "https://github.com/nf-core/circdna/pull/105",
        "my_migration_pr_state": "open",
        "attempted_at": "2026-10",
        "notes": "Migrate to the 4.0.3 template with nf-migrate",
    }

    # When it is migrated
    entry = state._migrate_entry("nf-core/circdna#98", old)

    # Then a PR having been opened makes it a success, the original status is
    # kept so the rewrite stays auditable, and the coarse date is not invented
    assert entry["status"] == "success"
    assert entry["legacy_status"] == "attempted"
    assert entry["pr"].endswith("/105")
    assert entry["attempted_at"] == "2026-10"


def test_a_legacy_attempted_entry_with_no_pr_becomes_a_failure() -> None:
    # Given a legacy entry that never opened a PR
    old = {"status": "attempted", "notes": "conflicts"}

    # When it is migrated
    entry = state._migrate_entry("nf-core/x#1", old)

    # Then it is a failure, not a success
    assert entry["status"] == "failed"
    assert entry["pr"] == ""


def test_migrating_a_whole_file_writes_one_record_per_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a legacy state.json holding both shapes
    monkeypatch.setattr(state, "state_dir", lambda: tmp_path)
    old_file = tmp_path / "state.json"
    old_file.write_text(
        json.dumps(
            {
                "attempted": {
                    "nf-core/rnaseq#1980": {
                        "status": "success",
                        "pr1": "https://github.com/nf-core/rnaseq/pull/1981",
                        "pr2": "https://github.com/nf-core/rnaseq/pull/1982",
                        "attempted_at": "2026-10-27",
                        "notes": "",
                    },
                    "nf-core/circdna#98": {
                        "status": "attempted",
                        "my_migration_pr": "https://github.com/nf-core/circdna/pull/105",
                        "attempted_at": "2026-10",
                        "notes": "",
                    },
                }
            }
        )
    )

    # When the file is migrated
    migrated, unclassified = state.migrate(old_file)

    # Then every attempt has its own file and none were dropped
    assert migrated == 2
    assert unclassified == []
    assert set(state.load_all()) == {
        "nf-core/rnaseq#1980",
        "nf-core/circdna#98",
    }


# patch-migration-pr.sh guards


PATCH_SCRIPT = SCRIPTS / "patch-migration-pr.sh"


def run_patch_script(
    repo: str,
    pr: str,
    env_dir: Path,
) -> subprocess.CompletedProcess:
    """Run patch-migration-pr.sh with an overridden state dir."""
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(Path.home()),
        "NF_TEMPLATE_SYNC_STATE_DIR": str(env_dir),
    }
    return subprocess.run(
        ["bash", str(PATCH_SCRIPT), repo, pr],
        capture_output=True,
        text=True,
        env=env,
    )


def test_patch_script_exits_3_for_an_opted_out_repo(tmp_path: Path) -> None:
    # Given a repo that is in the shipped opt-out list
    # When the patch script is called for that repo
    result = run_patch_script("nf-core/oncoanalyser", "42", tmp_path)

    # Then it exits 3 before cloning or creating a claim
    assert result.returncode == 3
    assert not (tmp_path / "claims").exists()


def test_patch_script_exits_2_when_claim_already_held(tmp_path: Path) -> None:
    # Given an existing claim file for the same repo and PR
    claim_dir = tmp_path / "claims"
    claim_dir.mkdir()
    (claim_dir / "nf-core_rnaseq_1980.claim").touch()

    # When the patch script is called for that same repo and PR
    result = run_patch_script("nf-core/rnaseq", "1980", tmp_path)

    # Then it exits 2 without modifying the claim directory
    assert result.returncode == 2
    assert len(list(claim_dir.glob("*.claim"))) == 1
