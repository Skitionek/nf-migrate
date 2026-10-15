from pathlib import Path

import pytest

from nf_migrate.cli import main
from nf_migrate.detect import detect_version
from nf_migrate.migrations import load_migrations
from nf_migrate.runner import upgrade
from nf_migrate.version import read_version


def write_migration(
    directory: Path, revision: str, down_revision: str, path: str, old: str
) -> None:
    new = old.replace("old", "new")
    (directory / f"v{revision.replace('.', '_')}.py").write_text(
        "from nf_migrate.operations import Replace\n"
        f"revision = {revision!r}\n"
        f"down_revision = {down_revision!r}\n"
        f"operations = [Replace({path!r}, old={old!r}, new={new!r})]\n"
    )


@pytest.fixture
def chain(tmp_path: Path) -> list:
    """3.2.1 -> 3.3.1 edits a.txt, -> 3.4.0 edits b.txt, -> 3.5.0 c.txt."""
    directory = tmp_path / "migrations"
    directory.mkdir()
    write_migration(directory, "3.3.1", "3.2.1", "a.txt", "a old\n")
    write_migration(directory, "3.4.0", "3.3.1", "b.txt", "b old\n")
    write_migration(directory, "3.5.0", "3.4.0", "c.txt", "c old\n")
    return load_migrations(directory)


def make_pipeline(tmp_path: Path, stamped: str, files: dict[str, str]) -> Path:
    project = tmp_path / "pipeline"
    project.mkdir(parents=True)
    (project / ".nf-core.yml").write_text(f"nf_core_version: {stamped}\n")
    for name, content in files.items():
        (project / name).write_text(content)
    return project


def test_detects_the_version_the_files_are_at_despite_the_stamp(
    tmp_path: Path, chain: list
) -> None:
    # Given a pipeline stamped 3.4.0 whose 3.4.0 update was reverted
    project = make_pipeline(
        tmp_path,
        "3.4.0",
        {"a.txt": "a new\n", "b.txt": "b old\n", "c.txt": "c old\n"},
    )

    # When
    detection = detect_version(project, chain)

    # Then
    assert detection.stamped == "3.4.0"
    assert detection.version == "3.3.1"
    assert not detection.matches_stamp


def test_detects_the_chain_root_and_head(tmp_path: Path, chain: list) -> None:
    # Given
    old_pipeline = make_pipeline(
        tmp_path / "old",
        "3.2.1",
        {"a.txt": "a old\n", "b.txt": "b old\n", "c.txt": "c old\n"},
    )
    new_pipeline = make_pipeline(
        tmp_path / "new",
        "3.5.0",
        {"a.txt": "a new\n", "b.txt": "b new\n", "c.txt": "c new\n"},
    )

    # When
    old_detection = detect_version(old_pipeline, chain)
    new_detection = detect_version(new_pipeline, chain)

    # Then
    assert old_detection.version == "3.2.1"
    assert new_detection.version == "3.5.0"
    assert old_detection.matches_stamp
    assert new_detection.matches_stamp


def test_without_evidence_the_stamp_wins(tmp_path: Path, chain: list) -> None:
    # Given a pipeline that customised every file the chain touches
    project = make_pipeline(
        tmp_path,
        "3.4.0",
        {"a.txt": "mine\n", "b.txt": "mine\n", "c.txt": "mine\n"},
    )

    # When
    detection = detect_version(project, chain)

    # Then
    assert detection.version == "3.4.0"


def test_detection_reports_evidence_per_migration(
    tmp_path: Path, chain: list
) -> None:
    # Given
    project = make_pipeline(
        tmp_path,
        "3.4.0",
        {"a.txt": "a new\n", "b.txt": "b old\n", "c.txt": "mine\n"},
    )

    # When
    detection = detect_version(project, chain)

    # Then
    evidence = {item.revision: item for item in detection.evidence}
    assert evidence["3.3.1"].already_applied == 1
    assert evidence["3.4.0"].applicable == 1
    assert evidence["3.5.0"].conflicts == 1


def test_upgrade_can_start_from_a_detected_version(
    tmp_path: Path, chain: list
) -> None:
    # Given
    project = make_pipeline(
        tmp_path,
        "3.4.0",
        {"a.txt": "a new\n", "b.txt": "b old\n", "c.txt": "c old\n"},
    )

    # When
    report = upgrade(project, chain, target="head", current="3.3.1")

    # Then
    assert report.succeeded, report.render()
    assert (project / "b.txt").read_text() == "b new\n"
    assert (project / "c.txt").read_text() == "c new\n"
    assert read_version(project) == "3.5.0"


# Choosing where an upgrade starts
def test_upgrade_starts_from_a_detected_version_older_than_the_stamp(
    tmp_path: Path, chain: list
) -> None:
    # Given a pipeline stamped 3.4.0 that lacks the 3.4.0 changes
    project = make_pipeline(
        tmp_path,
        "3.4.0",
        {"a.txt": "a new\n", "b.txt": "b old\n", "c.txt": "c old\n"},
    )

    # When
    detection = detect_version(project, chain)

    # Then
    assert detection.upgrade_from == "3.3.1"


def test_upgrade_never_starts_past_the_stamp(
    tmp_path: Path, chain: list
) -> None:
    # Given a pipeline stamped 3.3.1 that already took the 3.4.0 changes
    project = make_pipeline(
        tmp_path,
        "3.3.1",
        {"a.txt": "a new\n", "b.txt": "b new\n", "c.txt": "c old\n"},
    )

    # When
    detection = detect_version(project, chain)

    # Then
    assert detection.version == "3.4.0"
    assert detection.upgrade_from == "3.3.1"


def test_cli_upgrade_with_detect_applies_the_missing_release(
    tmp_path: Path, chain: list
) -> None:
    # Given
    project = make_pipeline(
        tmp_path,
        "3.4.0",
        {"a.txt": "a new\n", "b.txt": "b old\n", "c.txt": "c old\n"},
    )
    migrations_dir = chain[0].source.parent

    # When
    exit_code = main(
        [
            "--project",
            str(project),
            "--migrations",
            str(migrations_dir),
            "upgrade",
            "--detect",
        ]
    )

    # Then
    assert exit_code == 0
    assert (project / "b.txt").read_text() == "b new\n"
    assert read_version(project) == "3.5.0"
