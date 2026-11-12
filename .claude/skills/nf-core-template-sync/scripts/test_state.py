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


# Template sync PR provenance
#
# The title of a sync PR can be copied by a PR from a fork, so every script
# checks who opened the PR and where it comes from before it fetches the tree.

LIST_SCRIPT = SCRIPTS / "list-open-prs.sh"
FIX_SCRIPT = SCRIPTS / "fix-template-pr.sh"

GOOD_PR = {
    "author": {"login": "nf-core-bot"},
    "isCrossRepository": False,
    "headRefName": "nf-core-template-merge-4.2.1",
}


def test_a_bot_opened_same_repo_sync_pr_is_accepted() -> None:
    # Given the PR nf-core-bot opens from a branch of the pipeline itself
    # When it is checked
    # Then nothing is refused
    assert state.sync_pr_refusal(GOOD_PR) is None


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"author": {"login": "mallory"}}, "not nf-core-bot"),
        ({"author": None}, "not nf-core-bot"),
        ({"isCrossRepository": True}, "fork"),
        ({"headRefName": "dev"}, "not a nf-core-template-merge-*"),
        ({"headRefName": "TEMPLATE"}, "not a nf-core-template-merge-*"),
        ({"headRefName": "x-nf-core-template-merge-1"}, "not a nf-core"),
    ],
)
def test_a_pr_failing_any_one_check_is_refused(
    change: dict, reason: str
) -> None:
    # Given a PR that passes all checks but one
    pr = {**GOOD_PR, **change}

    # When it is checked
    refusal = state.sync_pr_refusal(pr)

    # Then it is refused, and the reason names the failed check
    assert refusal is not None and reason in refusal


@pytest.mark.parametrize("missing", list(GOOD_PR))
def test_a_pr_missing_a_checked_field_is_refused(missing: str) -> None:
    # Given a reply without one of the fields that decide the check
    pr = {key: value for key, value in GOOD_PR.items() if key != missing}

    # When it is checked
    # Then an absent field fails the check instead of passing it
    assert state.sync_pr_refusal(pr) is not None


def test_a_reply_that_is_not_a_pr_object_is_refused() -> None:
    assert state.sync_pr_refusal(None) is not None
    assert state.sync_pr_refusal([GOOD_PR]) is not None


class StubGh:
    """A fake `gh` and `git` on PATH, so the scripts run without a network.

    `gh pr view <n> --repo <repo>` answers from `view_<repo>_<n>.json` (slashes
    become underscores) and `gh search prs` from `search.json`. `git` records
    that it was called and fails with 7, which marks how far a script got.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.log = root / "gh.log"
        self.git_log = root / "git.log"
        bin_dir = root / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(
            "#!/usr/bin/env bash\n"
            'echo "$*" >> "$STUB_DIR/gh.log"\n'
            'case "$1 $2" in\n'
            '  "search prs") cat "$STUB_DIR/search.json" ;;\n'
            '  "pr view")\n'
            '    f="$STUB_DIR/view_${5//\\//_}_$3.json"\n'
            '    [ -f "$f" ] && cat "$f" || { echo 404 >&2; exit 1; } ;;\n'
            '  *) echo "unexpected gh call: $*" >&2; exit 99 ;;\n'
            "esac\n"
        )
        git = bin_dir / "git"
        git.write_text(
            '#!/usr/bin/env bash\necho "$*" >> "$STUB_DIR/git.log"\nexit 7\n'
        )
        gh.chmod(0o755)
        git.chmod(0o755)

    def search(self, prs: list[tuple[str, int]]) -> None:
        (self.root / "search.json").write_text(
            json.dumps(
                [{"repository": {"name": name}, "number": n} for name, n in prs]
            )
        )

    def view(self, repo: str, number: int, **change: object) -> None:
        name = f"view_{repo.replace('/', '_')}_{number}.json"
        (self.root / name).write_text(json.dumps({**GOOD_PR, **change}))

    def env(self, state_dir: Path) -> dict[str, str]:
        return {
            "PATH": f"{self.root / 'bin'}:/usr/bin:/bin:/usr/local/bin",
            "HOME": str(Path.home()),
            "NF_TEMPLATE_SYNC_STATE_DIR": str(state_dir),
            "STUB_DIR": str(self.root),
        }

    def run(
        self, script: Path, args: list[str], state_dir: Path
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(script), *args],
            capture_output=True,
            text=True,
            env=self.env(state_dir),
        )


@pytest.fixture
def stub(tmp_path: Path) -> StubGh:
    root = tmp_path / "stub"
    root.mkdir()
    return StubGh(root)


def test_listing_skips_a_forked_pr_and_keeps_the_bots_older_one(
    stub: StubGh, tmp_path: Path
) -> None:
    # Given a fork's PR with a higher number than the bot's, a pipeline whose
    # only PR is on a non-sync branch, and a pipeline that opted out
    stub.search(
        [("rnaseq", 10), ("rnaseq", 12), ("sarek", 5), ("oncoanalyser", 3)]
    )
    stub.view("nf-core/rnaseq", 10)
    stub.view("nf-core/rnaseq", 12, isCrossRepository=True)
    stub.view("nf-core/sarek", 5, headRefName="dev")

    # When the open PRs are listed
    result = stub.run(LIST_SCRIPT, [], tmp_path / "state")

    # Then only the bot's PR is listed, the fork cannot shadow it, and the
    # search itself was narrowed to the bot
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        {"repo": "nf-core/rnaseq", "pr": 10, "key": "nf-core/rnaseq#10"}
    ]
    assert "nf-core/rnaseq#12: comes from a fork" in result.stderr
    assert "nf-core/sarek#5: head branch 'dev'" in result.stderr
    assert "nf-core/oncoanalyser: opted out" in result.stderr
    assert "--author nf-core-bot" in stub.log.read_text()
    assert "oncoanalyser" not in "".join(
        line for line in stub.log.read_text().splitlines() if "pr view" in line
    )


def test_listing_skips_a_pr_it_cannot_read(
    stub: StubGh, tmp_path: Path
) -> None:
    # Given a search hit whose details GitHub does not return
    stub.search([("rnaseq", 10)])

    # When the open PRs are listed
    result = stub.run(LIST_SCRIPT, [], tmp_path / "state")

    # Then it is left out rather than listed unchecked
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []
    assert "nf-core/rnaseq#10: cannot read it" in result.stderr


@pytest.mark.parametrize("script", [FIX_SCRIPT, PATCH_SCRIPT])
@pytest.mark.parametrize(
    "change",
    [
        {"author": {"login": "mallory"}},
        {"isCrossRepository": True},
        {"headRefName": "dev"},
    ],
)
def test_scripts_refuse_a_pr_that_is_not_the_bots_before_any_git_call(
    script: Path, change: dict, stub: StubGh, tmp_path: Path
) -> None:
    # Given a PR with the sync title that fails one provenance check
    stub.view("nf-core/rnaseq", 1980, **change)
    state_dir = tmp_path / "state"

    # When the script is asked to work on it
    result = stub.run(script, ["nf-core/rnaseq", "1980"], state_dir)

    # Then it refuses with exit 2, nothing was cloned or fetched, and the claim
    # it briefly held is gone
    assert result.returncode == 2
    assert "refusing nf-core/rnaseq#1980" in result.stderr
    assert not stub.git_log.exists()
    assert list((state_dir / "claims").glob("*.claim")) == []


@pytest.mark.parametrize("script", [FIX_SCRIPT, PATCH_SCRIPT])
def test_scripts_refuse_a_pr_they_cannot_read(
    script: Path, stub: StubGh, tmp_path: Path
) -> None:
    # Given a PR that GitHub does not return
    # When the script is asked to work on it
    result = stub.run(script, ["nf-core/rnaseq", "1980"], tmp_path / "state")

    # Then it refuses instead of carrying on unchecked
    assert result.returncode == 2
    assert "cannot read nf-core/rnaseq#1980" in result.stderr
    assert not stub.git_log.exists()


@pytest.mark.parametrize("script", [FIX_SCRIPT, PATCH_SCRIPT])
def test_scripts_go_on_to_clone_the_bots_own_sync_pr(
    script: Path, stub: StubGh, tmp_path: Path
) -> None:
    # Given the PR nf-core-bot opens from a branch of the pipeline itself
    stub.view("nf-core/rnaseq", 1980)

    # When the script is asked to work on it
    result = stub.run(script, ["nf-core/rnaseq", "1980"], tmp_path / "state")

    # Then it gets past the check to the clone (the stub git fails with 7)
    assert result.returncode == 7
    assert stub.git_log.read_text().startswith("clone ")
