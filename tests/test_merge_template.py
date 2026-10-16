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


@pytest.fixture
def fake_nf_core(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An `nf-core` on PATH; `lint --dir D --fix NAME` writes `D/NAME.fixed`."""
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    executable = bin_directory / "nf-core"
    executable.write_text(
        "#!/bin/sh\n"
        'echo "$@" >> "$FAKE_NF_CORE_LOG"\n'
        'while [ "$1" != "--dir" ]; do shift; done\n'
        'directory="$2"\n'
        'while [ "$1" != "--fix" ]; do shift; done\n'
        'echo fixed > "$directory/$2.fixed"\n'
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
