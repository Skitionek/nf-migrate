from pathlib import Path

from nf_migrate.operations import (
    CreateFile,
    DeleteFile,
    JsonEdit,
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


def test_replace_is_already_applied_when_old_text_only_occurs_inside_new(
    tmp_path: Path,
) -> None:
    # Given a template change that appended a line at the end of the file
    workspace = make_workspace(tmp_path, {".gitattributes": "a\nb\n"})
    operation = Replace(".gitattributes", old="a\n", new="a\nb\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.read(".gitattributes") == "a\nb\n"


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


# Replace, tolerating whitespace
def test_replace_follows_a_block_the_pipeline_indented_deeper(
    tmp_path: Path,
) -> None:
    # Given the template block nested two spaces deeper in the pipeline
    workspace = make_workspace(
        tmp_path, {"ci.yml": "jobs:\n    test:\n      runs-on: old\n"}
    )
    operation = Replace(
        "ci.yml",
        old="  test:\n    runs-on: old\n",
        new="  test:\n    runs-on: new\n    timeout: 5\n",
    )

    # When
    result = operation.apply(workspace)

    # Then the change keeps the pipeline's indentation
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("ci.yml") == (
        "jobs:\n    test:\n      runs-on: new\n      timeout: 5\n"
    )


def test_replace_ignores_trailing_whitespace(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "x = 1   \ny = 2\n"})
    operation = Replace("a.config", old="x = 1\ny = 2\n", new="x = 1\ny = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("a.config") == "x = 1\ny = 3\n"


def test_replace_conflicts_when_indentation_changes_unevenly(
    tmp_path: Path,
) -> None:
    # Given lines re-indented by different amounts
    content = "test:\n      runs-on: old\n  timeout: 1\n"
    workspace = make_workspace(tmp_path, {"ci.yml": content})
    operation = Replace(
        "ci.yml",
        old="test:\n  runs-on: old\n  timeout: 1\n",
        new="test:\n  runs-on: new\n  timeout: 1\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("ci.yml") == content


def test_replace_is_already_applied_when_new_text_only_differs_in_whitespace(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(
        tmp_path, {"ci.yml": "jobs:\n    test:\n      runs-on: new\n"}
    )
    operation = Replace(
        "ci.yml",
        old="  test:\n    runs-on: old\n",
        new="  test:\n    runs-on: new\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


# Replace, anchored on one side
def test_insertion_anchors_on_the_line_before_when_the_line_after_moved(
    tmp_path: Path,
) -> None:
    # Given a pipeline that added its own env entries after the anchor
    content = (
        "        env:\n          NFT_WORKDIR: ${{ env.NFT_WORKDIR }}\n"
        "          SENTIEON_AUTH: token\n        with:\n"
    )
    workspace = make_workspace(tmp_path, {"nf-test.yml": content})
    operation = Replace(
        "nf-test.yml",
        old="          NFT_WORKDIR: ${{ env.NFT_WORKDIR }}\n        with:\n",
        new=(
            "          NFT_WORKDIR: ${{ env.NFT_WORKDIR }}\n"
            "          NXF_VERSION: ${{ matrix.NXF_VER }}\n        with:\n"
        ),
    )

    # When
    result = operation.apply(workspace)
    again = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("nf-test.yml") == (
        "        env:\n          NFT_WORKDIR: ${{ env.NFT_WORKDIR }}\n"
        "          NXF_VERSION: ${{ matrix.NXF_VER }}\n"
        "          SENTIEON_AUTH: token\n        with:\n"
    )
    assert again.outcome is Outcome.ALREADY_APPLIED


def test_one_sided_anchor_must_be_more_than_punctuation(
    tmp_path: Path,
) -> None:
    # Given an insertion whose only intact context is a closing brace
    content = "params {\n    a = 1\n}\nmine\n"
    workspace = make_workspace(tmp_path, {"nextflow.config": content})
    operation = Replace(
        "nextflow.config",
        old="}\ntemplate\n",
        new="}\nadded\ntemplate\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("nextflow.config") == content


def test_a_deletion_is_not_taken_as_applied_from_its_anchor_alone(
    tmp_path: Path,
) -> None:
    # Given a pipeline that changed the line the template deletes
    content = "include { FASTQC }\nmy_line\nworkflow {\n"
    workspace = make_workspace(tmp_path, {"main.nf": content})
    operation = Replace(
        "main.nf",
        old="include { FASTQC }\ntemplate_line\nworkflow_end\n",
        new="include { FASTQC }\nworkflow_end\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("main.nf") == content


# JsonEdit
PIPELINE_SCHEMA = """\
{
    "properties": {
        "my_param": {
            "type": "integer"
        },
        "igenomes_base": {
            "type": "string",
            "format": "directory-path",
            "description": "The base path to the igenomes reference files"
        }
    }
}
"""


def test_json_edit_removes_a_key_whatever_its_neighbours(
    tmp_path: Path,
) -> None:
    # Given a schema with a property the template does not have
    workspace = make_workspace(tmp_path, {"schema.json": PIPELINE_SCHEMA})
    operation = JsonEdit(
        "schema.json",
        ["properties", "igenomes_base", "format"],
        old='"directory-path"',
        new=None,
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("schema.json") == PIPELINE_SCHEMA.replace(
        '            "format": "directory-path",\n', ""
    )


def test_json_edit_is_already_applied_when_the_value_is_new(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"schema.json": PIPELINE_SCHEMA})
    operation = JsonEdit(
        "schema.json",
        ["properties", "my_param", "type"],
        old='"string"',
        new='"integer"',
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.read("schema.json") == PIPELINE_SCHEMA


def test_json_edit_conflicts_when_the_pipeline_changed_the_value(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"schema.json": PIPELINE_SCHEMA})
    operation = JsonEdit(
        "schema.json",
        ["properties", "my_param", "type"],
        old='"string"',
        new='"boolean"',
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert '"boolean"' in result.suggestion


def test_json_edit_adds_a_member_after_its_template_sibling(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"schema.json": PIPELINE_SCHEMA})
    operation = JsonEdit(
        "schema.json",
        ["properties", "{{pipeline_name}}_mode"],
        old=None,
        new='{\n    "type": "string"\n}',
        after="my_param",
    )
    workspace.variables = {"pipeline_name": "rnaseq"}

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert (
        "        },\n"
        '        "rnaseq_mode": {\n'
        '            "type": "string"\n'
        "        },\n"
        '        "igenomes_base": {'
    ) in workspace.read("schema.json")


def test_json_edit_falls_back_to_its_text_hunk_when_the_path_is_missing(
    tmp_path: Path,
) -> None:
    # Given a samplesheet schema whose property the pipeline renamed
    schema = (
        '{\n    "properties": {\n        "reads": {\n'
        '            "pattern": "^\\\\S+$",\n'
        '            "errorMessage": "reads 1"\n        }\n    }\n}\n'
    )
    workspace = make_workspace(tmp_path, {"schema.json": schema})
    operation = JsonEdit(
        "schema.json",
        ["properties", "fastq_1", "pattern"],
        old='"^\\\\S+$"',
        new='"^\\\\S+\\\\.gz$"',
        fallback_old='            "pattern": "^\\\\S+$",\n',
        fallback_new='            "pattern": "^\\\\S+\\\\.gz$",\n',
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert '"pattern": "^\\\\S+\\\\.gz$"' in workspace.read("schema.json")


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
