from pathlib import Path

import yaml

from nf_migrate.cli import main
from nf_migrate.version import read_version, stamp_version


def test_stamp_quotes_a_version_yaml_would_read_as_a_number() -> None:
    # Given
    content = "repository_type: pipeline\n"

    # When
    stamped = stamp_version(content, "1.10")

    # Then
    assert stamped == "nf_core_version: '1.10'\nrepository_type: pipeline\n"
    assert yaml.safe_load(stamped)["nf_core_version"] == "1.10"


def test_stamp_leaves_a_dotted_version_unquoted() -> None:
    # Given
    content = "nf_core_version: '1.10'\n"

    # When
    stamped = stamp_version(content, "3.3.1")

    # Then
    assert stamped == "nf_core_version: 3.3.1\n"


def test_a_pipeline_without_nf_core_yml_has_no_version(tmp_path: Path) -> None:
    # Given a pipeline from before nf-core/tools wrote .nf-core.yml
    (tmp_path / "nextflow.config").write_text("manifest {}\n")

    # When
    version = read_version(tmp_path)

    # Then
    assert version is None


def test_cli_stamp_creates_nf_core_yml_when_missing(tmp_path: Path) -> None:
    # Given a pipeline from before nf-core/tools wrote .nf-core.yml
    (tmp_path / "nextflow.config").write_text("manifest {}\n")

    # When
    exit_code = main(["--project", str(tmp_path), "stamp", "1.9"])

    # Then
    assert exit_code == 0
    assert read_version(tmp_path) == "1.9"


def test_cli_stamp_refuses_a_nf_core_yml_symlinked_outside_the_pipeline(
    tmp_path: Path, capsys
) -> None:
    # Given
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / ".nf-core.yml").symlink_to(tmp_path / "planted.yml")

    # When
    exit_code = main(["--project", str(pipeline), "stamp", "1.9"])

    # Then
    assert exit_code == 2
    assert "leads outside" in capsys.readouterr().err
    assert not (tmp_path / "planted.yml").exists()
