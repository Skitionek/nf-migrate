import os
import subprocess
from pathlib import Path

import pytest

from nf_migrate.cli import main
from nf_migrate.merge_template import merge_template
from nf_migrate.migrations import MigrationError


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def commit_files(repo: Path, files: dict[str, str], message: str) -> str:
    for relative_path, content in files.items():
        file_path = repo / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "v3_3_1.py").write_text(
        "from nf_migrate.operations import ManualStep, Replace\n"
        "revision = '3.3.1'\n"
        "down_revision = '3.2.1'\n"
        "operations = [\n"
        "    Replace('base.config', old='retry = 104\\n',"
        " new='retry = 104 + 175\\n'),\n"
        "    ManualStep('ro-crate-metadata.json', 'run rocrate'),\n"
        "]\n"
    )
    return directory


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A pipeline on `dev` and a template sync on `TEMPLATE`."""
    repo = tmp_path / "pipeline"
    repo.mkdir()
    git(repo, "init", "-q", "--initial-branch=dev")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    commit_files(
        repo,
        {
            ".nf-core.yml": "nf_core_version: 3.2.1\n",
            "base.config": "retry = 104\n",
            "README.md": "pipeline readme\n",
        },
        "dev",
    )
    git(repo, "checkout", "-q", "--orphan", "TEMPLATE")
    git(repo, "rm", "-r", "-f", "-q", ".")
    commit_files(
        repo,
        {
            ".nf-core.yml": "nf_core_version: 3.3.1\n",
            "base.config": "retry = 104 + 175\n",
            "README.md": "template readme\n",
        },
        "Template update for nf-core/tools version 3.3.1",
    )
    git(repo, "checkout", "-q", "dev")
    return repo


def test_clean_upgrade_becomes_a_merge_commit_of_dev_and_template(
    repo: Path, migrations_dir: Path
) -> None:
    # Given
    dev_sha = git(repo, "rev-parse", "dev")
    template_sha = git(repo, "rev-parse", "TEMPLATE")

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.report.succeeded
    assert result.target_version == "3.3.1"
    assert result.commit is not None
    parents = git(repo, "rev-list", "--parents", "-n", "1", result.commit)
    assert parents.split()[1:] == [dev_sha, template_sha]
    assert git(repo, "show", f"{result.commit}:base.config") == (
        "retry = 104 + 175"
    )
    assert git(repo, "show", f"{result.commit}:README.md") == (
        "pipeline readme"
    )
    assert git(repo, "show", f"{result.commit}:.nf-core.yml") == (
        "nf_core_version: 3.3.1"
    )


def test_merge_leaves_the_checkout_and_worktrees_untouched(
    repo: Path, migrations_dir: Path
) -> None:
    # Given
    status_before = git(repo, "status", "--porcelain")

    # When
    merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert git(repo, "status", "--porcelain") == status_before
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "dev"
    assert len(git(repo, "worktree", "list").splitlines()) == 1


def test_conflicting_upgrade_creates_no_commit(
    repo: Path, migrations_dir: Path
) -> None:
    # Given
    commit_files(repo, {"base.config": "retry = 'custom'\n"}, "customise")

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.commit is None
    assert not result.report.succeeded
    assert "base.config" in result.report.render_markdown()


def test_markdown_report_lists_manual_steps_as_a_checklist(
    repo: Path, migrations_dir: Path
) -> None:
    # Given / When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)
    markdown = result.report.render_markdown()

    # Then
    assert "- [ ] `ro-crate-metadata.json`: run rocrate" in markdown


def test_cli_prints_the_merge_commit_and_writes_the_report(
    repo: Path, migrations_dir: Path, tmp_path: Path, capsys
) -> None:
    # Given
    report_file = tmp_path / "report.md"

    # When
    exit_code = main(
        [
            "--migrations",
            str(migrations_dir),
            "merge-template",
            "--repo",
            str(repo),
            "--report-file",
            str(report_file),
            "dev",
            "TEMPLATE",
        ]
    )

    # Then
    commit = capsys.readouterr().out.strip()
    assert exit_code == 0
    assert git(repo, "cat-file", "-t", commit) == "commit"
    assert "3.3.1" in report_file.read_text()


def test_report_warns_when_files_disagree_with_the_stamp(
    repo: Path, migrations_dir: Path
) -> None:
    # Given dev already carries the 3.3.1 change but is stamped 3.2.1
    commit_files(repo, {"base.config": "retry = 104 + 175\n"}, "cherry-pick")

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.report.succeeded
    assert result.detection.version == "3.3.1"
    markdown = result.render_markdown()
    assert "nf_core_version" in markdown
    assert "3.3.1" in markdown


def test_allow_conflicts_still_creates_the_merge_commit(
    repo: Path, migrations_dir: Path
) -> None:
    # Given
    commit_files(repo, {"base.config": "retry = 'custom'\n"}, "customise")

    # When
    result = merge_template(
        repo, "dev", "TEMPLATE", migrations_dir, allow_conflicts=True
    )

    # Then
    assert not result.report.succeeded
    assert result.commit is not None
    assert git(repo, "show", f"{result.commit}:.nf-core.yml") == (
        "nf_core_version: 3.3.1"
    )


def test_unstamped_base_upgrades_from_the_detected_version(
    repo: Path, migrations_dir: Path
) -> None:
    # Given dev from before nf-core/tools wrote .nf-core.yml
    git(repo, "rm", "-q", ".nf-core.yml")
    git(repo, "commit", "-q", "-m", "no .nf-core.yml")

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.report.succeeded
    assert result.start_version == "3.2.1"
    assert git(repo, "show", f"{result.commit}:base.config") == (
        "retry = 104 + 175"
    )
    markdown = result.render_markdown()
    assert "has no `nf_core_version`" in markdown


def replace_template_head(repo: Path, files: dict[str, str], subject: str):
    """Commit a template with `files` (and no other) on top of TEMPLATE."""
    git(repo, "checkout", "-q", "TEMPLATE")
    git(repo, "rm", "-r", "-f", "-q", ".")
    commit_files(repo, files, subject)
    git(repo, "checkout", "-q", "dev")


def test_template_without_nf_core_yml_takes_its_version_from_the_subject(
    repo: Path, migrations_dir: Path
) -> None:
    # Given a template from before nf-core/tools wrote .nf-core.yml
    replace_template_head(
        repo,
        {"base.config": "retry = 104 + 175\n"},
        "Template update for nf-core/tools version 3.3.1",
    )

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.report.succeeded
    assert result.target_version == "3.3.1"
    assert git(repo, "show", f"{result.commit}:base.config") == (
        "retry = 104 + 175"
    )


def test_template_with_unversioned_nf_core_yml_uses_the_subject(
    repo: Path, migrations_dir: Path
) -> None:
    # Given a template whose .nf-core.yml has no nf_core_version yet
    replace_template_head(
        repo,
        {
            ".nf-core.yml": "repository_type: pipeline\n",
            "base.config": "retry = 104 + 175\n",
        },
        "Template update for nf-core/tools, version 3.3.1",
    )

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.target_version == "3.3.1"
    assert result.commit is not None


def test_template_with_no_version_anywhere_names_where_it_looked(
    repo: Path, migrations_dir: Path
) -> None:
    # Given a template that says nothing about its version
    replace_template_head(
        repo, {"base.config": "retry = 104 + 175\n"}, "sync the template"
    )

    # When
    with pytest.raises(MigrationError) as error:
        merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    message = str(error.value)
    assert ".nf-core.yml" in message
    assert "nf-core/tools, version" in message


@pytest.fixture
def fake_nf_core(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `uvx` on PATH; `nf-core@V pipelines lint --dir D --fix NAME` writes
    `D/NAME.fixed` and redraws `D/nf-core-pipeline_logo_light.png`."""
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    executable = bin_directory / "uvx"
    executable.write_text(
        "#!/bin/sh\n"
        'echo "$@" >> "$FAKE_NF_CORE_LOG"\n'
        'while [ "$1" != "--dir" ]; do shift; done\n'
        'directory="$2"\n'
        'while [ "$1" != "--fix" ]; do shift; done\n'
        'echo fixed > "$directory/$2.fixed"\n'
        'echo redrawn > "$directory/nf-core-pipeline_logo_light.png"\n'
        # nf-core formats a file with prettier when it is installed.
        'if [ "$2" = files_unchanged ] && [ -n "$FAKE_NF_CORE_REFORMAT" ]\n'
        "then\n"
        '  echo "prettier formatted" > "$directory/$FAKE_NF_CORE_REFORMAT"\n'
        "fi\n"
        # nf-core exits 1 when other lint tests still fail.
        "exit 1\n"
    )
    executable.chmod(0o755)
    log = tmp_path / "nf-core.log"
    monkeypatch.setenv("FAKE_NF_CORE_LOG", str(log))
    monkeypatch.setenv("PATH", f"{bin_directory}:/usr/bin:/bin")
    return log


def test_lint_fix_adds_one_commit_per_fix_on_top_of_the_merge(
    repo: Path, migrations_dir: Path, fake_nf_core: Path
) -> None:
    # Given
    dev_sha = git(repo, "rev-parse", "dev")
    template_sha = git(repo, "rev-parse", "TEMPLATE")

    # When
    result = merge_template(
        repo, "dev", "TEMPLATE", migrations_dir, lint_fix=True
    )

    # Then
    assert result.commit is not None
    subjects = git(repo, "log", "--format=%s", "-3", result.commit).splitlines()
    assert subjects == [
        "chore: regenerate container configs",
        "style: apply nf-core pipelines lint --fix",
        "Merge nf-core/tools 3.3.1 template with nf-migrate",
    ]
    merge_commit = git(repo, "rev-parse", f"{result.commit}~2")
    parents = git(repo, "rev-list", "--parents", "-n", "1", merge_commit)
    assert parents.split()[1:] == [dev_sha, template_sha]
    assert git(repo, "show", f"{result.commit}:files_unchanged.fixed") == (
        "fixed"
    )
    assert git(repo, "show", f"{result.commit}:container_configs.fixed") == (
        "fixed"
    )


def test_lint_fix_is_skipped_unless_asked_for(
    repo: Path, migrations_dir: Path, fake_nf_core: Path
) -> None:
    # Given a repo and an nf-core that would change files

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.commit is not None
    assert not fake_nf_core.exists()
    subject = git(repo, "log", "--format=%s", "-1", result.commit)
    assert subject.startswith("Merge nf-core/tools")


def test_lint_fix_without_nf_core_installed_is_an_error(
    repo: Path, migrations_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    # When / Then
    with pytest.raises(MigrationError, match="nf-core"):
        merge_template(repo, "dev", "TEMPLATE", migrations_dir, lint_fix=True)


def test_cli_lint_fix_flag_prints_the_last_commit(
    repo: Path, migrations_dir: Path, fake_nf_core: Path, capsys
) -> None:
    # Given the --lint-fix flag

    # When
    exit_code = main(
        [
            "--migrations",
            str(migrations_dir),
            "merge-template",
            "--repo",
            str(repo),
            "--lint-fix",
            "dev",
            "TEMPLATE",
        ]
    )

    # Then
    commit = capsys.readouterr().out.strip()
    assert exit_code == 0
    subject = git(repo, "log", "--format=%s", "-1", commit)
    assert subject == "chore: regenerate container configs"


def test_lint_fix_runs_the_template_release_of_nf_core(
    repo: Path, migrations_dir: Path, fake_nf_core: Path
) -> None:
    # Given a template on 3.3.1

    # When
    merge_template(repo, "dev", "TEMPLATE", migrations_dir, lint_fix=True)

    # Then
    invocations = fake_nf_core.read_text().splitlines()
    assert invocations
    assert all(
        line.startswith("nf-core@3.3.1 pipelines lint") for line in invocations
    )


def test_lint_fix_keeps_template_files_that_nf_core_reformats(
    repo: Path,
    migrations_dir: Path,
    fake_nf_core: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a template file that nf-core would rewrite with prettier, which
    # CI does not run
    commit_files(repo, {"email_template.html": "<BR>\n"}, "add email template")
    git(repo, "checkout", "-q", "TEMPLATE")
    commit_files(
        repo, {"email_template.html": "<br>\n"}, "update email template"
    )
    git(repo, "checkout", "-q", "dev")
    monkeypatch.setenv("FAKE_NF_CORE_REFORMAT", "email_template.html")

    # When
    result = merge_template(
        repo, "dev", "TEMPLATE", migrations_dir, lint_fix=True
    )

    # Then the file is the one of the template branch
    assert result.commit is not None
    assert git(repo, "show", f"{result.commit}:email_template.html") == "<br>"


def test_lint_fix_keeps_the_logos_of_the_template_branch(
    repo: Path, migrations_dir: Path, fake_nf_core: Path
) -> None:
    # Given a template whose logo nf-core would redraw differently
    git(repo, "checkout", "-q", "TEMPLATE")
    commit_files(
        repo, {"nf-core-pipeline_logo_light.png": "template logo\n"}, "add logo"
    )
    git(repo, "checkout", "-q", "dev")

    # When
    result = merge_template(
        repo, "dev", "TEMPLATE", migrations_dir, lint_fix=True
    )

    # Then
    assert result.commit is not None
    assert git(
        repo, "show", f"{result.commit}:nf-core-pipeline_logo_light.png"
    ) == ("template logo")


@pytest.fixture
def fake_nextflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `nextflow` on PATH that logs its call and fails with the message in
    `FAKE_NEXTFLOW_ERROR`, if set. Request it after `fake_nf_core`, which
    replaces PATH."""
    bin_directory = tmp_path / "nextflow-bin"
    bin_directory.mkdir()
    executable = bin_directory / "nextflow"
    executable.write_text(
        "#!/bin/sh\n"
        'echo "ansi=$NXF_ANSI_LOG args=$*" >> "$FAKE_NEXTFLOW_LOG"\n'
        'echo "cwd=$(pwd)" >> "$FAKE_NEXTFLOW_LOG"\n'
        # $4 is the pipeline directory in `inspect -format json DIR`.
        'echo "files=$(ls "$4" | tr "\\n" " ")" >> "$FAKE_NEXTFLOW_LOG"\n'
        'if [ -n "$FAKE_NEXTFLOW_ERROR" ]; then\n'
        '  echo "$FAKE_NEXTFLOW_ERROR" >&2\n'
        "  exit 1\n"
        "fi\n"
        "echo '{\"processes\": []}'\n"
    )
    executable.chmod(0o755)
    log = tmp_path / "nextflow.log"
    monkeypatch.setenv("FAKE_NEXTFLOW_LOG", str(log))
    monkeypatch.setenv("PATH", f"{bin_directory}:{os.environ['PATH']}")
    return log


IM_NOTIFICATION_ERROR = (
    "Error main.nf:1:1: Included name 'imNotification' is not defined in "
    "module 'utils_nfcore_pipeline'"
)


def test_compile_check_passes_when_nextflow_inspects_the_pipeline(
    repo: Path, migrations_dir: Path, fake_nextflow: Path
) -> None:
    # Given
    # a nextflow that compiles the pipeline

    # When
    result = merge_template(
        repo, "dev", "TEMPLATE", migrations_dir, compile_check=True
    )

    # Then
    assert result.commit is not None
    assert result.compile_check is not None
    assert result.compile_check.passed
    assert "compile" not in result.render_markdown().lower()
    log_lines = fake_nextflow.read_text().splitlines()
    assert log_lines[0].startswith("ansi=false args=inspect -format json ")


def test_compile_check_runs_nextflow_outside_the_pipeline_and_checkout(
    repo: Path, migrations_dir: Path, fake_nextflow: Path
) -> None:
    # Given
    # nextflow writes .nextflow/ and work/ into its working directory

    # When
    merge_template(repo, "dev", "TEMPLATE", migrations_dir, compile_check=True)

    # Then
    log_lines = fake_nextflow.read_text().splitlines()
    working_directory = Path(log_lines[1].removeprefix("cwd="))
    assert working_directory != Path.cwd()
    assert working_directory != repo


def test_failed_compile_check_keeps_the_commit_and_reports_a_warning(
    repo: Path,
    migrations_dir: Path,
    fake_nextflow: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a pipeline that Nextflow cannot compile
    monkeypatch.setenv("FAKE_NEXTFLOW_ERROR", IM_NOTIFICATION_ERROR)

    # When
    result = merge_template(
        repo, "dev", "TEMPLATE", migrations_dir, compile_check=True
    )

    # Then
    assert result.commit is not None
    assert git(repo, "cat-file", "-t", result.commit) == "commit"
    assert result.compile_check is not None
    assert not result.compile_check.passed
    markdown = result.render_markdown()
    assert "[!WARNING]" in markdown
    assert "Nextflow could not compile the merged pipeline" in markdown
    assert "Included name 'imNotification' is not defined" in markdown


def test_compile_check_inspects_the_tree_after_the_lint_fix_commits(
    repo: Path,
    migrations_dir: Path,
    fake_nf_core: Path,
    fake_nextflow: Path,
) -> None:
    # Given
    # lint-fix commits files that only exist after the merge

    # When
    merge_template(
        repo,
        "dev",
        "TEMPLATE",
        migrations_dir,
        lint_fix=True,
        compile_check=True,
    )

    # Then
    log_lines = fake_nextflow.read_text().splitlines()
    assert "container_configs.fixed" in log_lines[2]


def test_compile_check_is_off_by_default(
    repo: Path, migrations_dir: Path, fake_nextflow: Path
) -> None:
    # Given
    # a nextflow on PATH

    # When
    result = merge_template(repo, "dev", "TEMPLATE", migrations_dir)

    # Then
    assert result.compile_check is None
    assert not fake_nextflow.exists()


def test_compile_check_without_nextflow_is_an_error_not_a_warning(
    repo: Path, migrations_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given a PATH without nextflow
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    # When
    with pytest.raises(MigrationError) as error:
        merge_template(
            repo, "dev", "TEMPLATE", migrations_dir, compile_check=True
        )

    # Then
    assert "--compile-check needs the nextflow command" in str(error.value)


def test_cli_compile_check_failure_warns_on_stderr_and_exits_zero(
    repo: Path,
    migrations_dir: Path,
    fake_nextflow: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    # Given
    monkeypatch.setenv("FAKE_NEXTFLOW_ERROR", IM_NOTIFICATION_ERROR)

    # When
    exit_code = main(
        [
            "--migrations",
            str(migrations_dir),
            "merge-template",
            "--repo",
            str(repo),
            "--compile-check",
            "dev",
            "TEMPLATE",
        ]
    )

    # Then
    captured = capsys.readouterr()
    assert exit_code == 0
    assert git(repo, "cat-file", "-t", captured.out.strip()) == "commit"
    assert "Included name 'imNotification' is not defined" in captured.err
