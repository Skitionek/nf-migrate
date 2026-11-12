"""The shared pr-comment.yml poster of nf-core 4.0.3, as nf-migrate writes it.

The poster runs with a write token and takes the pull request number and the
comment header from an artifact that the workflow of a fork PR uploads. The
migration hardens its metadata step; these tests run that step's script.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from nf_migrate.cli import BUNDLED_MIGRATIONS
from nf_migrate.migrations import load_migrations
from nf_migrate.operations import FirstOf, Outcome, Workspace

POSTER = ".github/workflows/pr-comment.yml"
# The poster as nf-core 4.0.3 released it, before the hardening.
TEMPLATE = (
    Path(__file__).parent / "data" / "nf_core_4_0_3_pr_comment.yml"
).read_text()
TEMPLATE_STEP_START = "      - name: Read comment metadata\n"
TEMPLATE_STEP_END = "      - name: Post PR comment\n"
BASE_REPOSITORY = "nf-core/demo"

needs_tools = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("jq") is None,
    reason="needs bash and jq to run the workflow step",
)


def poster_operation() -> FirstOf:
    chain = load_migrations(BUNDLED_MIGRATIONS)
    migration = next(item for item in chain if item.revision == "4.0.3")
    return next(
        operation
        for operation in migration.operations
        if getattr(operation, "path", None) == POSTER
    )


def hardened_poster() -> str:
    return poster_operation().operations[0].content


def make_workspace(tmp_path: Path, content: str | None) -> Workspace:
    if content is not None:
        file_path = tmp_path / POSTER
        file_path.parent.mkdir(parents=True)
        file_path.write_text(content)
    return Workspace(tmp_path)


def metadata_step() -> dict:
    workflow = yaml.safe_load(hardened_poster())
    steps = workflow["jobs"]["post-comment"]["steps"]
    return next(step for step in steps if step.get("id") == "meta")


# The migration
def test_poster_is_created_hardened_in_a_pipeline_without_one(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, None)

    # When
    result = poster_operation().apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read(POSTER) == hardened_poster()
    assert workspace.read(POSTER) != TEMPLATE


def test_template_poster_gets_only_its_metadata_step_replaced(
    tmp_path: Path,
) -> None:
    # Given a pipeline that kept the poster of nf-core 4.0.3 as it was
    workspace = make_workspace(tmp_path, TEMPLATE)

    # When
    result = poster_operation().apply(workspace)

    # Then
    start = TEMPLATE.index(TEMPLATE_STEP_START)
    end = TEMPLATE.index(TEMPLATE_STEP_END)
    updated = workspace.read(POSTER)
    assert result.outcome is Outcome.APPLIED
    assert updated == hardened_poster()
    assert updated.startswith(TEMPLATE[:start])
    assert updated.endswith(TEMPLATE[end:])


def test_poster_with_bumped_pins_is_hardened_in_place(tmp_path: Path) -> None:
    # Given a pipeline whose poster has other pins than the template's
    bumped = TEMPLATE.replace(
        "b6e2e70617bc3265edd6dab6c906732b2f1ae151 # v21",
        "0123456789abcdef0123456789abcdef01234567 # v22",
    ).replace(
        "5770ad5eb8f42dd2c4f34da00c94c5381e49af88 # v3.0.5",
        "89abcdef0123456789abcdef0123456789abcdef # v3.1.0",
    )
    assert bumped != TEMPLATE
    workspace = make_workspace(tmp_path, bumped)

    # When
    result = poster_operation().apply(workspace)

    # Then the pins stay and the step is the hardened one
    updated = workspace.read(POSTER)
    assert result.outcome is Outcome.APPLIED
    assert "0123456789abcdef0123456789abcdef01234567 # v22" in updated
    assert "89abcdef0123456789abcdef0123456789abcdef # v3.1.0" in updated
    hardened_step = hardened_poster()[
        hardened_poster().index(TEMPLATE_STEP_START) : hardened_poster().index(
            TEMPLATE_STEP_END
        )
    ]
    assert hardened_step in updated


def test_hardened_poster_is_already_applied(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, hardened_poster())

    # When
    result = poster_operation().apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_hardened_step_in_an_edited_poster_is_already_applied(
    tmp_path: Path,
) -> None:
    # Given a pipeline that adds a producer to the hardened poster
    edited = hardened_poster().replace(
        '      - "Run nf-test"\n', '      - "Run nf-test"\n      - "Extra"\n'
    )
    assert edited != hardened_poster()
    workspace = make_workspace(tmp_path, edited)

    # When
    result = poster_operation().apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_poster_with_an_edited_metadata_step_is_a_conflict(
    tmp_path: Path,
) -> None:
    # Given a pipeline that changed the template's metadata step
    edited = TEMPLATE.replace("Will post comment", "Posting comment")
    assert edited != TEMPLATE
    workspace = make_workspace(tmp_path, edited)

    # When
    result = poster_operation().apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read(POSTER) == edited


# The metadata step
def test_step_takes_the_run_values_from_the_environment(tmp_path: Path) -> None:
    # Given the step of the poster
    step = metadata_step()

    # Then nothing from the event is put into the script itself
    assert "${{" not in step["run"]
    assert step["env"]["RUN_HEAD_REPO"] == (
        "${{ github.event.workflow_run.head_repository.full_name }}"
    )
    assert step["env"]["RUN_HEAD_BRANCH"] == (
        "${{ github.event.workflow_run.head_branch }}"
    )
    assert step["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"


GH_STUB = """\
#!/usr/bin/env bash
# Stands in for `gh api repos/<repo>/pulls/<n> --jq <filter>`: answers from
# pull request files, with the filter run by jq, and 404s for anything else.
echo "$*" >> "$GH_STUB_LOG"
[ "$1" = api ] && [ "$3" = --jq ] || exit 2
case "$2" in
  "repos/$GITHUB_REPOSITORY/pulls/"[0-9]*) ;;
  *) echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
esac
file="$GH_STUB_PULLS/${2##*/}.json"
[ -f "$file" ] || { echo "gh: Not Found (HTTP 404)" >&2; exit 1; }
exec jq -r "$4" "$file"
"""


def pull_request(head_repo: str | None, head_ref: str, sha: str = "a" * 40):
    repo = None if head_repo is None else {"full_name": head_repo}
    return {"head": {"repo": repo, "ref": head_ref, "sha": sha}}


class Step:
    """Runs the metadata step the way a runner does, with a stubbed gh."""

    def __init__(self, tmp_path: Path) -> None:
        self.work = tmp_path / "work"
        self.work.mkdir()
        self.pulls = tmp_path / "pulls"
        self.pulls.mkdir()
        self.log = tmp_path / "gh.log"
        self.output = tmp_path / "github_output"
        self.output.write_text("")
        stub = tmp_path / "bin" / "gh"
        stub.parent.mkdir()
        stub.write_text(GH_STUB)
        stub.chmod(0o755)
        self.script = tmp_path / "step.sh"
        self.script.write_text(metadata_step()["run"])
        self.path = f"{stub.parent}{os.pathsep}{os.environ['PATH']}"
        self.home = tmp_path

    def artifact(
        self,
        pr_number: bytes | None = b"7\n",
        header: bytes | None = b"lint\n",
        comment: bytes | None = b"body\n",
    ) -> None:
        directory = self.work / "pr-comment"
        directory.mkdir()
        for name, content in (
            ("pr_number.txt", pr_number),
            ("header.txt", header),
            ("comment.md", comment),
        ):
            if content is not None:
                (directory / name).write_bytes(content)

    def pull(self, number: int, **fields) -> None:
        (self.pulls / f"{number}.json").write_text(
            json.dumps(pull_request(**fields))
        )

    def run(
        self,
        repo: str = "fork-owner/demo",
        branch: str = "feature",
    ) -> subprocess.CompletedProcess:
        env = {
            "PATH": self.path,
            "HOME": str(self.home),
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_REPOSITORY": BASE_REPOSITORY,
            "GH_TOKEN": "token",
            "GH_STUB_LOG": str(self.log),
            "GH_STUB_PULLS": str(self.pulls),
            "RUN_HEAD_REPO": repo,
            "RUN_HEAD_BRANCH": branch,
        }
        return subprocess.run(
            ["bash", "-e", str(self.script)],
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
        )

    def outputs(self) -> dict[str, str]:
        lines = self.output.read_text().splitlines()
        return dict(line.split("=", 1) for line in lines)

    def looked_up(self) -> bool:
        return self.log.exists()


@needs_tools
def test_step_posts_to_the_pull_request_that_triggered_the_run(
    tmp_path: Path,
) -> None:
    # Given an artifact naming the pull request the run belongs to
    step = Step(tmp_path)
    step.artifact()
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature")

    # When
    result = step.run()

    # Then
    assert result.returncode == 0, result.stdout + result.stderr
    assert step.outputs() == {
        "pr_number": "7",
        "header": "lint",
        "post": "true",
    }
    assert step.log.read_text() == (
        f"api repos/{BASE_REPOSITORY}/pulls/7 --jq "
        '.head.repo.full_name + " " + .head.ref\n'
    )


@needs_tools
def test_step_posts_for_a_run_on_a_head_that_was_pushed_over(
    tmp_path: Path,
) -> None:
    # Given a pull request that got more commits after the run started: its
    # head sha is no longer the run's, its head repository and branch are
    step = Step(tmp_path)
    step.artifact()
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature", sha="b" * 40)

    # When
    result = step.run()

    # Then the results of the run are still posted
    assert result.returncode == 0, result.stdout + result.stderr
    assert step.outputs()["post"] == "true"


@needs_tools
def test_step_refuses_a_pull_request_from_another_fork_with_the_same_branch(
    tmp_path: Path,
) -> None:
    # Given a fork PR whose artifact names a pull request from another fork
    # that happens to use the same branch name
    step = Step(tmp_path)
    step.artifact(pr_number=b"7\n")
    step.pull(7, head_repo="someone-else/demo", head_ref="main")

    # When
    result = step.run(repo="fork-owner/demo", branch="main")

    # Then
    assert result.returncode == 1
    assert step.outputs() == {}


@needs_tools
def test_step_refuses_a_pull_request_from_the_base_repository(
    tmp_path: Path,
) -> None:
    # Given an artifact naming a maintainer's PR from a branch of the base
    # repository that has the branch name the fork PR used
    step = Step(tmp_path)
    step.artifact(pr_number=b"7\n")
    step.pull(7, head_repo=BASE_REPOSITORY, head_ref="dev")

    # When
    result = step.run(repo="fork-owner/demo", branch="dev")

    # Then
    assert result.returncode == 1
    assert step.outputs() == {}


@needs_tools
def test_step_refuses_another_branch_of_the_same_fork(tmp_path: Path) -> None:
    # Given
    step = Step(tmp_path)
    step.artifact()
    step.pull(7, head_repo="fork-owner/demo", head_ref="other")

    # When
    result = step.run(repo="fork-owner/demo", branch="feature")

    # Then
    assert result.returncode == 1
    assert step.outputs() == {}


@needs_tools
def test_step_refuses_a_pull_request_whose_head_repository_is_gone(
    tmp_path: Path,
) -> None:
    # Given
    step = Step(tmp_path)
    step.artifact()
    step.pull(7, head_repo=None, head_ref="feature")

    # When
    result = step.run()

    # Then
    assert result.returncode == 1
    assert step.outputs() == {}


@needs_tools
def test_step_refuses_an_issue_number(tmp_path: Path) -> None:
    # Given a number that is no pull request, so the API has none to return
    step = Step(tmp_path)
    step.artifact(pr_number=b"9\n")
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature")

    # When
    result = step.run()

    # Then
    assert result.returncode == 1
    assert step.outputs() == {}


@needs_tools
@pytest.mark.parametrize(
    ("repo", "branch"), [("", "feature"), ("fork-owner/demo", ""), ("", "")]
)
def test_step_refuses_a_run_without_head_repository_or_branch(
    tmp_path: Path, repo: str, branch: str
) -> None:
    # Given
    step = Step(tmp_path)
    step.artifact()
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature")

    # When
    result = step.run(repo=repo, branch=branch)

    # Then
    assert result.returncode == 1
    assert step.outputs() == {}


@needs_tools
def test_step_keeps_a_branch_name_out_of_the_shell(tmp_path: Path) -> None:
    # Given a branch name made of shell syntax, which git allows
    branch = 'x$(touch pwned)`touch pwned2`";touch pwned3;"'
    step = Step(tmp_path)
    step.artifact()
    step.pull(7, head_repo="fork-owner/demo", head_ref=branch)

    # When
    result = step.run(branch=branch)

    # Then it is compared as text only
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(path.name for path in step.work.iterdir()) == ["pr-comment"]


@needs_tools
@pytest.mark.parametrize(
    "pr_number",
    [
        b"",
        b"\n",
        b"7a\n",
        b"-7\n",
        b"7 8\n",
        b"7\n8\n",
        b"../../issues/9\n",
        b"7/../9\n",
        b"7?x=1\n",
        b"$(id)\n",
    ],
    ids=[
        "empty",
        "newline",
        "letters",
        "negative",
        "space",
        "two-lines",
        "path",
        "dot-dot",
        "query",
        "substitution",
    ],
)
def test_step_refuses_a_pr_number_that_is_not_digits(
    tmp_path: Path, pr_number: bytes
) -> None:
    # Given
    step = Step(tmp_path)
    step.artifact(pr_number=pr_number)
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature")

    # When
    result = step.run()

    # Then no pull request is looked up
    assert result.returncode == 1
    assert step.outputs() == {}
    assert not step.looked_up()


@needs_tools
@pytest.mark.parametrize(
    "header",
    [
        b"lint\npost=false\n",
        b"lint\r\n",
        b"a b\n",
        b"a=b\n",
        b"a/b\n",
        b"a.b\n",
        b"$(id)\n",
        b"`id`\n",
        b"a;b\n",
        b"\n\n::error::x\n",
        "lïnt\n".encode(),
    ],
    ids=[
        "second-output-line",
        "carriage-return",
        "space",
        "equals",
        "slash",
        "dot",
        "substitution",
        "backticks",
        "semicolon",
        "workflow-command",
        "non-ascii",
    ],
)
def test_step_refuses_a_header_outside_the_allowed_characters(
    tmp_path: Path, header: bytes
) -> None:
    # Given
    step = Step(tmp_path)
    step.artifact(header=header)
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature")

    # When
    result = step.run()

    # Then nothing reaches the outputs or the log of the run
    assert result.returncode == 1
    assert step.outputs() == {}
    assert "::error::x" not in result.stdout
    assert not step.looked_up()


@needs_tools
@pytest.mark.parametrize(
    "header",
    [b"lint\n", b"nf-test\n", b"template-version\n", b"Branch_Protection2\n"],
)
def test_step_accepts_the_headers_of_the_producers(
    tmp_path: Path, header: bytes
) -> None:
    # Given
    step = Step(tmp_path)
    step.artifact(header=header)
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature")

    # When
    result = step.run()

    # Then
    assert result.returncode == 0, result.stdout + result.stderr
    assert step.outputs()["header"] == header.decode().strip()


@needs_tools
@pytest.mark.parametrize("header", [b"", b"\n"], ids=["empty", "newline"])
def test_step_still_accepts_an_empty_header(
    tmp_path: Path, header: bytes
) -> None:
    # Given a producer that sends no header, which the sticky comment takes
    step = Step(tmp_path)
    step.artifact(header=header)
    step.pull(7, head_repo="fork-owner/demo", head_ref="feature")

    # When
    result = step.run()

    # Then
    assert result.returncode == 0, result.stdout + result.stderr
    assert step.outputs() == {"pr_number": "7", "header": "", "post": "true"}


@needs_tools
def test_step_posts_nothing_without_an_artifact(tmp_path: Path) -> None:
    # Given a run that uploaded no pr-comment artifact
    step = Step(tmp_path)

    # When
    result = step.run()

    # Then
    assert result.returncode == 0, result.stdout + result.stderr
    assert step.outputs() == {}
    assert not step.looked_up()


@needs_tools
def test_step_posts_nothing_without_a_comment(tmp_path: Path) -> None:
    # Given an artifact that has no comment.md
    step = Step(tmp_path)
    step.artifact(comment=None)

    # When
    result = step.run()

    # Then
    assert result.returncode == 0, result.stdout + result.stderr
    assert step.outputs() == {}
    assert not step.looked_up()
