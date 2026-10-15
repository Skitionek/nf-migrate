from pathlib import Path

from nf_migrate.operations import (
    CreateFile,
    DeleteFile,
    Outcome,
    Replace,
    Workspace,
)


def make_workspace(tmp_path: Path, files: dict[str, str]) -> Workspace:
    for relative_path, content in files.items():
        file_path = tmp_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    return Workspace(tmp_path)


# Replace
def test_replace_applies_when_old_text_occurs_once(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "x = 1\ny = 2\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("a.config") == "x = 1\ny = 3\n"


def test_replace_is_already_applied_when_only_new_text_is_present(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y = 3\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_replace_conflicts_when_neither_text_is_present(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y = 42\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("a.config") == "y = 42\n"


def test_replace_conflicts_when_old_text_is_ambiguous(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y = 2\ny = 2\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "2 times" in result.message


def test_replace_only_matches_whole_lines(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "line 13\nline 3\n"})
    operation = Replace("a.txt", old="line 3\n", new="line three\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("a.txt") == "line 13\nline three\n"


def test_replace_conflicts_when_file_is_missing(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT


# CreateFile
def test_create_file_writes_a_missing_file(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = CreateFile("tests/nextflow.config", content="params {}\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("tests/nextflow.config") == "params {}\n"


def test_create_file_is_already_applied_for_identical_file(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "same\n"})
    operation = CreateFile("a.txt", content="same\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


def test_create_file_conflicts_with_a_different_existing_file(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "local\n"})
    operation = CreateFile("a.txt", content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("a.txt") == "local\n"


# DeleteFile
def test_delete_file_removes_an_unmodified_file(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"old.yml": "template\n"})
    operation = DeleteFile("old.yml", expected_content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("old.yml") is None


def test_delete_file_conflicts_when_file_was_customised(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"old.yml": "customised\n"})
    operation = DeleteFile("old.yml", expected_content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("old.yml") == "customised\n"


def test_delete_file_is_already_applied_when_file_is_gone(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = DeleteFile("old.yml", expected_content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


# Workspace
def test_workspace_only_touches_disk_on_commit(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "before\n", "b.txt": "x"})
    workspace.write("a.txt", "after\n")
    workspace.delete("b.txt")
    workspace.write("new/c.txt", "c\n")

    # When
    content_before_commit = (tmp_path / "a.txt").read_text()
    workspace.commit()

    # Then
    assert content_before_commit == "before\n"
    assert (tmp_path / "a.txt").read_text() == "after\n"
    assert not (tmp_path / "b.txt").exists()
    assert (tmp_path / "new/c.txt").read_text() == "c\n"


# Template variables
def test_operations_expand_template_variables_from_the_workspace(
    tmp_path: Path,
) -> None:
    # Given
    make_workspace(tmp_path, {"workflows/rnaseq.nf": "workflow RNASEQ {\n"})
    workspace = Workspace(
        tmp_path,
        variables={"pipeline_name": "rnaseq", "PIPELINE_NAME": "RNASEQ"},
    )
    operation = Replace(
        "workflows/{{pipeline_name}}.nf",
        old="workflow {{PIPELINE_NAME}} {\n",
        new="workflow {{PIPELINE_NAME}} {\n    main:\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert result.path == "workflows/rnaseq.nf"
    assert workspace.read("workflows/rnaseq.nf") == (
        "workflow RNASEQ {\n    main:\n"
    )
