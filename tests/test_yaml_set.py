from pathlib import Path

from nf_migrate.operations import Outcome, Workspace
from nf_migrate.yaml_edit import YamlListItem, YamlSet, yaml_changes

NF_TEST = """\
name: nf-test
jobs:
  nf-test:
    # Pipelines tune the matrix
    strategy:
      matrix:
        NXF_VER:
          - "24.10.5"
          - "latest-everything"
    steps:
      - name: Run nf-test
        uses: ./.github/actions/nf-test
        env:
          NFT_DIFF: ${{ env.NFT_DIFF }}
          SENTIEON: yes
"""


def make_workspace(tmp_path: Path, content: str) -> Workspace:
    (tmp_path / "nf-test.yml").write_text(content)
    return Workspace(tmp_path)


def test_yaml_set_bumps_a_version_the_pipeline_pinned_differently(
    tmp_path: Path,
) -> None:
    # Given a pipeline on a different Nextflow pin than the template had
    workspace = make_workspace(tmp_path, NF_TEST)
    operation = YamlSet(
        "nf-test.yml",
        key=["jobs", "nf-test", "strategy", "matrix", "NXF_VER", 0],
        value='"25.10.4"',
        old='"25.04.0"',
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("nf-test.yml") == NF_TEST.replace(
        '"24.10.5"', '"25.10.4"'
    )


def test_yaml_set_keeps_a_customised_value_that_is_no_version(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, NF_TEST)
    operation = YamlSet(
        "nf-test.yml",
        key=["jobs", "nf-test", "steps", 0, "name"],
        value="nf-test run",
        old="Run tests",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.changed_paths() == []


def test_yaml_set_adds_a_key_after_its_template_sibling(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, NF_TEST)
    operation = YamlSet(
        "nf-test.yml",
        key=["jobs", "nf-test", "steps", 0, "id"],
        value="run_nf_test",
        after="name",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("nf-test.yml") == NF_TEST.replace(
        "      - name: Run nf-test\n",
        "      - name: Run nf-test\n        id: run_nf_test\n",
    )


def test_yaml_set_removes_a_key_and_is_then_already_applied(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, NF_TEST)
    operation = YamlSet(
        "nf-test.yml",
        key=["jobs", "nf-test", "steps", 0, "env", "NFT_DIFF"],
        value=None,
        old="${{ env.NFT_DIFF }}",
    )

    # When
    first = operation.apply(workspace)
    second = operation.apply(workspace)

    # Then
    assert first.outcome is Outcome.APPLIED
    assert second.outcome is Outcome.ALREADY_APPLIED
    assert workspace.read("nf-test.yml") == NF_TEST.replace(
        "          NFT_DIFF: ${{ env.NFT_DIFF }}\n", ""
    )


def test_yaml_set_is_already_applied_for_the_same_value_quoted_otherwise(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, NF_TEST)
    operation = YamlSet(
        "nf-test.yml",
        key=["jobs", "nf-test", "strategy", "matrix", "NXF_VER", 0],
        value="'24.10.5'",
        old='"24.04.0"',
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


def test_yaml_set_conflicts_when_the_parent_is_missing(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, NF_TEST)
    operation = YamlSet(
        "nf-test.yml",
        key=["jobs", "lint", "runs-on"],
        value="ubuntu-latest",
        old="ubuntu-20.04",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT


def test_yaml_set_finds_a_step_by_name_when_pipelines_add_steps(
    tmp_path: Path,
) -> None:
    # Given a pipeline with an extra step before the template's
    content = (
        "jobs:\n  lint:\n    steps:\n"
        "      - name: Install dependencies\n        run: pip install x\n"
        "      - name: Run nf-core lint\n        run: nf-core lint\n"
    )
    workspace = make_workspace(tmp_path, content)
    operation = YamlSet(
        "nf-test.yml",
        key=[
            "jobs",
            "lint",
            "steps",
            {"name": ["Run nf-core lint", "Run nf-core pipelines lint"]},
            "name",
        ],
        value="Run nf-core pipelines lint",
        old="Run nf-core lint",
    )

    # When
    first = operation.apply(workspace)
    second = operation.apply(workspace)

    # Then
    assert first.outcome is Outcome.APPLIED
    assert second.outcome is Outcome.ALREADY_APPLIED
    assert workspace.read("nf-test.yml") == content.replace(
        "name: Run nf-core lint", "name: Run nf-core pipelines lint"
    )


def test_yaml_set_keeps_a_newer_version_the_pipeline_has(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, 'env:\n  NFT_VER: "0.9.5"\n')
    operation = YamlSet(
        "nf-test.yml", key=["env", "NFT_VER"], value='"0.9.4"', old='"0.9.3"'
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert "newer" in result.message


# YamlListItem
LINT = """\
jobs:
  nf-core:
    steps:
      - name: Check out pipeline code
        uses: actions/checkout@v4

      - name: Our own setup
        run: make setup

      - name: Install dependencies
        run: pip install nf-core
"""

READ_STEP = """\
      - name: read .nf-core.yml
        uses: pietrobolcato/action-read-yaml@1.1.0
        id: read_yml

"""


def test_yaml_list_item_adds_a_step_after_its_template_neighbour(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, LINT)
    operation = YamlListItem(
        "nf-test.yml",
        key=["jobs", "nf-core", "steps"],
        item=READ_STEP,
        match={"id": ["read_yml"], "name": ["read .nf-core.yml"]},
        after={"name": ["Our own setup", "Set up Python"], "#": 0},
    )

    # When
    first = operation.apply(workspace)
    second = operation.apply(workspace)

    # Then
    assert first.outcome is Outcome.APPLIED
    assert second.outcome is Outcome.ALREADY_APPLIED
    assert workspace.read("nf-test.yml") == LINT.replace(
        "      - name: Install dependencies\n",
        READ_STEP + "      - name: Install dependencies\n",
    )


def test_yaml_list_item_leaves_a_step_the_pipeline_already_has(
    tmp_path: Path,
) -> None:
    # Given the step with a newer action than the template inserts
    content = LINT.replace(
        "      - name: Install dependencies\n",
        READ_STEP.replace("1.1.0", "1.2.0")
        + "      - name: Install dependencies\n",
    )
    workspace = make_workspace(tmp_path, content)
    operation = YamlListItem(
        "nf-test.yml",
        key=["jobs", "nf-core", "steps"],
        item=READ_STEP,
        match={"id": ["read_yml"]},
        after={"name": ["Our own setup"]},
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_yaml_list_item_removes_a_step(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, LINT)
    operation = YamlListItem(
        "nf-test.yml",
        key=["jobs", "nf-core", "steps"],
        item=None,
        match={"name": ["Our own setup"]},
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("nf-test.yml") == LINT.replace(
        "      - name: Our own setup\n        run: make setup\n\n", ""
    )


def test_yaml_changes_turn_a_new_step_into_a_list_item(tmp_path: Path) -> None:
    # Given a template release that adds a step
    old_text = LINT
    new_text = LINT.replace(
        "      - name: Install dependencies\n",
        READ_STEP + "      - name: Install dependencies\n",
    )

    # When
    operations = yaml_changes(old_text, new_text)

    # Then
    assert operations is not None
    assert [type(operation).__name__ for operation in operations] == [
        "YamlListItem"
    ]
