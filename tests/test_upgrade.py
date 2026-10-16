from pathlib import Path

import pytest

from nf_migrate.cli import main
from nf_migrate.migrations import MigrationError, load_migrations
from nf_migrate.operations import Outcome
from nf_migrate.runner import upgrade
from nf_migrate.version import read_version

NF_CORE_YML = "nf_core_version: 3.2.1\nrepository_type: pipeline\n"


def write_migration(
    directory: Path, revision: str, down_revision: str | None, body: str
) -> None:
    source = (
        "from nf_migrate.operations import Replace, CreateFile\n\n"
        f"revision = {revision!r}\n"
        f"down_revision = {down_revision!r}\n\n"
        f"{body}\n"
    )
    file_name = f"v{revision.replace('.', '_')}.py"
    (directory / file_name).write_text(source)


@pytest.fixture
def migrations_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "migrations"
    directory.mkdir()
    write_migration(
        directory,
        "3.3.1",
        "3.2.1",
        "operations = [Replace('base.config', old='retry = 104\\n', "
        "new='retry = 104 + 175\\n')]",
    )
    write_migration(
        directory,
        "3.4.0",
        "3.3.1",
        "operations = [CreateFile('tests/.nftignore', content='*.html\\n')]",
    )
    return directory


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "pipeline"
    directory.mkdir()
    (directory / ".nf-core.yml").write_text(NF_CORE_YML)
    (directory / "base.config").write_text("retry = 104\n")
    return directory


# Loading the migration chain
def test_migrations_load_in_revision_order(migrations_dir: Path) -> None:
    # Given
    write_migration(migrations_dir, "3.2.1", None, "operations = []")

    # When
    chain = load_migrations(migrations_dir)

    # Then
    assert [migration.revision for migration in chain] == [
        "3.2.1",
        "3.3.1",
        "3.4.0",
    ]


def test_branching_migrations_are_rejected(migrations_dir: Path) -> None:
    # Given
    write_migration(migrations_dir, "3.3.2", "3.2.1", "operations = []")

    # When / Then
    with pytest.raises(MigrationError, match="3.2.1"):
        load_migrations(migrations_dir)


# Upgrading a pipeline
def test_upgrade_to_head_applies_all_pending_migrations(
    project_dir: Path, migrations_dir: Path
) -> None:
    # Given
    chain = load_migrations(migrations_dir)

    # When
    report = upgrade(project_dir, chain, target="head")

    # Then
    assert report.succeeded
    assert read_version(project_dir) == "3.4.0"
    assert (project_dir / "base.config").read_text() == "retry = 104 + 175\n"
    assert (project_dir / "tests/.nftignore").read_text() == "*.html\n"


def test_upgrade_stops_at_the_requested_target(
    project_dir: Path, migrations_dir: Path
) -> None:
    # Given
    chain = load_migrations(migrations_dir)

    # When
    upgrade(project_dir, chain, target="3.3.1")

    # Then
    assert read_version(project_dir) == "3.3.1"
    assert not (project_dir / "tests/.nftignore").exists()


def test_conflicting_migration_writes_nothing_and_keeps_version(
    project_dir: Path, migrations_dir: Path
) -> None:
    # Given
    (project_dir / "base.config").write_text("retry = 'custom'\n")
    chain = load_migrations(migrations_dir)

    # When
    report = upgrade(project_dir, chain, target="head")

    # Then
    assert not report.succeeded
    assert report.failed_revision == "3.3.1"
    assert read_version(project_dir) == "3.2.1"
    assert (project_dir / "base.config").read_text() == "retry = 'custom'\n"
    assert not (project_dir / "tests/.nftignore").exists()


def test_dry_run_reports_diff_without_writing(
    project_dir: Path, migrations_dir: Path
) -> None:
    # Given
    chain = load_migrations(migrations_dir)

    # When
    report = upgrade(project_dir, chain, target="head", dry_run=True)

    # Then
    assert report.succeeded
    assert "+retry = 104 + 175" in report.diff
    assert read_version(project_dir) == "3.2.1"
    assert not (project_dir / "tests/.nftignore").exists()


def test_upgrade_from_unknown_version_is_rejected(
    project_dir: Path, migrations_dir: Path
) -> None:
    # Given
    (project_dir / ".nf-core.yml").write_text("nf_core_version: 2.0\n")
    chain = load_migrations(migrations_dir)

    # When / Then
    with pytest.raises(MigrationError, match="2.0"):
        upgrade(project_dir, chain, target="head")


def test_manual_steps_are_reported_without_blocking_the_upgrade(
    project_dir: Path, tmp_path: Path
) -> None:
    # Given
    directory = tmp_path / "manual_migrations"
    directory.mkdir()
    (directory / "v3_3_2.py").write_text(
        "from nf_migrate.operations import ManualStep\n"
        "revision = '3.3.2'\n"
        "down_revision = '3.2.1'\n"
        "operations = [ManualStep('ro-crate-metadata.json', 'regenerate')]\n"
    )

    # When
    report = upgrade(project_dir, load_migrations(directory), target="head")

    # Then
    assert report.succeeded
    assert read_version(project_dir) == "3.3.2"
    assert "MANUAL ro-crate-metadata.json: regenerate" in report.render()


# Applying what fits
def test_allow_conflicts_applies_what_fits_and_reports_the_rest(
    project_dir: Path, tmp_path: Path
) -> None:
    # Given a release with one change that fits and one, in another file,
    # that does not
    directory = tmp_path / "partial_migrations"
    directory.mkdir()
    (directory / "v3_3_1.py").write_text(
        "from nf_migrate.operations import Replace\n"
        "revision = '3.3.1'\n"
        "down_revision = '3.2.1'\n"
        "operations = [\n"
        "    Replace('base.config', old='retry = 104\\n',"
        " new='retry = 104 + 175\\n'),\n"
        "    Replace('other.config', old='missing\\n', new='added\\n'),\n"
        "]\n"
    )

    # When
    report = upgrade(
        project_dir,
        load_migrations(directory),
        target="head",
        allow_conflicts=True,
    )

    # Then
    assert not report.succeeded
    assert (project_dir / "base.config").read_text() == "retry = 104 + 175\n"
    assert read_version(project_dir) == "3.3.1"
    markdown = report.render_markdown()
    assert "-missing" in markdown
    assert "+added" in markdown


def test_allow_conflicts_leaves_a_file_with_a_conflict_untouched(
    project_dir: Path, tmp_path: Path
) -> None:
    # Given a release that edits igenomes.config twice, the second edit
    # conflicting, and base.config once
    (project_dir / "igenomes.config").write_text("params {\ncustom\n}\n")
    directory = tmp_path / "partial_migrations"
    directory.mkdir()
    (directory / "v3_3_1.py").write_text(
        "from nf_migrate.operations import Replace\n"
        "revision = '3.3.1'\n"
        "down_revision = '3.2.1'\n"
        "operations = [\n"
        "    Replace('igenomes.config', old='params {\\n',"
        " new='params.genomes = [\\n'),\n"
        "    Replace('igenomes.config', old='template\\n}\\n',"
        " new='template\\n]\\n'),\n"
        "    Replace('base.config', old='retry = 104\\n',"
        " new='retry = 104 + 175\\n'),\n"
        "]\n"
    )

    # When
    report = upgrade(
        project_dir,
        load_migrations(directory),
        target="head",
        allow_conflicts=True,
    )

    # Then the half-convertible file is left alone, the other file is not
    assert (project_dir / "igenomes.config").read_text() == (
        "params {\ncustom\n}\n"
    )
    assert (project_dir / "base.config").read_text() == "retry = 104 + 175\n"
    conflicts = report.migrations[0].conflicts
    assert [conflict.path for conflict in conflicts] == [
        "igenomes.config",
        "igenomes.config",
    ]
    assert "held back" in conflicts[0].message


# Pipeline-owned documentation
def test_template_changes_that_do_not_fit_docs_become_suggestions(
    project_dir: Path, tmp_path: Path
) -> None:
    # Given a release that edits base.config and a README the pipeline
    # rewrote, and another README edit that still fits
    (project_dir / "README.md").write_text("# my pipeline\n\nintro\n")
    directory = tmp_path / "docs_migrations"
    directory.mkdir()
    (directory / "v3_3_1.py").write_text(
        "from nf_migrate.operations import Replace\n"
        "revision = '3.3.1'\n"
        "down_revision = '3.2.1'\n"
        "operations = [\n"
        "    Replace('README.md', old='template intro\\n',"
        " new='new template intro\\n'),\n"
        "    Replace('README.md', old='intro\\n', new='intro\\n\\nbadge\\n'),\n"
        "    Replace('base.config', old='retry = 104\\n',"
        " new='retry = 104 + 175\\n'),\n"
        "]\n"
    )

    # When
    report = upgrade(project_dir, load_migrations(directory), target="head")

    # Then the release goes through and the misfit is only suggested
    assert report.succeeded, report.render()
    assert (project_dir / "base.config").read_text() == "retry = 104 + 175\n"
    assert (project_dir / "README.md").read_text() == (
        "# my pipeline\n\nintro\n\nbadge\n"
    )
    assert read_version(project_dir) == "3.3.1"
    assert "SUGGESTED README.md" in report.render()
    assert "+new template intro" in report.render_markdown()


def test_partial_files_keep_the_changes_that_fit_beside_a_conflict(
    project_dir: Path, tmp_path: Path
) -> None:
    # Given a release that edits igenomes.config twice, the second edit
    # conflicting
    (project_dir / "igenomes.config").write_text("params {\ncustom\n}\n")
    directory = tmp_path / "partial_migrations"
    directory.mkdir()
    (directory / "v3_3_1.py").write_text(
        "from nf_migrate.operations import Replace\n"
        "revision = '3.3.1'\n"
        "down_revision = '3.2.1'\n"
        "operations = [\n"
        "    Replace('igenomes.config', old='params {\\n',"
        " new='params.genomes = [\\n'),\n"
        "    Replace('igenomes.config', old='template\\n}\\n',"
        " new='template\\n]\\n'),\n"
        "]\n"
    )

    # When
    report = upgrade(
        project_dir,
        load_migrations(directory),
        target="head",
        allow_conflicts=True,
        partial_files=True,
    )

    # Then the edit that fits is kept and only the misfit is reported
    assert (project_dir / "igenomes.config").read_text() == (
        "params.genomes = [\ncustom\n}\n"
    )
    outcomes = [result.outcome for result in report.migrations[0].results]
    assert outcomes == [Outcome.APPLIED, Outcome.CONFLICT]


def test_cli_partial_files_implies_allowing_conflicts(
    project_dir: Path, tmp_path: Path
) -> None:
    # Given
    (project_dir / "igenomes.config").write_text("params {\ncustom\n}\n")
    directory = tmp_path / "partial_migrations"
    directory.mkdir()
    (directory / "v3_3_1.py").write_text(
        "from nf_migrate.operations import Replace\n"
        "revision = '3.3.1'\n"
        "down_revision = '3.2.1'\n"
        "operations = [\n"
        "    Replace('igenomes.config', old='params {\\n',"
        " new='params.genomes = [\\n'),\n"
        "    Replace('igenomes.config', old='template\\n}\\n',"
        " new='template\\n]\\n'),\n"
        "]\n"
    )

    # When
    exit_code = main(
        [
            "--project",
            str(project_dir),
            "--migrations",
            str(directory),
            "upgrade",
            "--partial-files",
        ]
    )

    # Then
    assert exit_code == 1
    assert (project_dir / "igenomes.config").read_text() == (
        "params.genomes = [\ncustom\n}\n"
    )
    assert read_version(project_dir) == "3.3.1"
