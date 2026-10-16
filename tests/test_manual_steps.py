import json
from pathlib import Path

from nf_migrate.operations import (
    ManualStep,
    NfCoreComponent,
    Outcome,
    Workspace,
)

MODULES_URL = "https://github.com/nf-core/modules.git"


def write_modules_json(
    root: Path, modules: dict[str, str], subworkflows: dict[str, str]
) -> None:
    def entries(shas: dict[str, str]) -> dict:
        return {name: {"git_sha": sha} for name, sha in shas.items()}

    content = {
        "repos": {
            MODULES_URL: {
                "modules": {"nf-core": entries(modules)},
                "subworkflows": {"nf-core": entries(subworkflows)},
            }
        }
    }
    (root / "modules.json").write_text(json.dumps(content))


# ManualStep
def test_manual_step_reports_its_instruction(tmp_path: Path) -> None:
    # Given
    workspace = Workspace(tmp_path)
    operation = ManualStep(
        "ro-crate-metadata.json", "run `nf-core pipelines rocrate`"
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.MANUAL
    assert result.message == "run `nf-core pipelines rocrate`"
    assert workspace.changed_paths() == []


# NfCoreComponent
def test_component_at_template_version_is_already_applied(
    tmp_path: Path,
) -> None:
    # Given
    write_modules_json(tmp_path, {"multiqc": "abc123"}, {})
    operation = NfCoreComponent("modules", "multiqc", git_sha="abc123")

    # When
    result = operation.apply(Workspace(tmp_path))

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


def test_component_at_other_version_asks_for_an_update(
    tmp_path: Path,
) -> None:
    # Given
    write_modules_json(tmp_path, {"multiqc": "old000"}, {})
    operation = NfCoreComponent("modules", "multiqc", git_sha="abc123")

    # When
    result = operation.apply(Workspace(tmp_path))

    # Then
    assert result.outcome is Outcome.MANUAL
    assert "nf-core modules update multiqc" in result.message
    assert "old000" in result.message


def test_missing_component_asks_for_an_install(tmp_path: Path) -> None:
    # Given
    write_modules_json(tmp_path, {}, {})
    operation = NfCoreComponent(
        "subworkflows", "utils_nfschema_plugin", git_sha="abc123"
    )

    # When
    result = operation.apply(Workspace(tmp_path))

    # Then
    assert result.outcome is Outcome.MANUAL
    assert "nf-core subworkflows install utils_nfschema_plugin" in (
        result.message
    )


def test_component_dropped_by_template_asks_for_removal(
    tmp_path: Path,
) -> None:
    # Given
    write_modules_json(tmp_path, {}, {"utils_nfvalidation_plugin": "a1"})
    operation = NfCoreComponent(
        "subworkflows", "utils_nfvalidation_plugin", git_sha=None
    )

    # When
    result = operation.apply(Workspace(tmp_path))

    # Then
    assert result.outcome is Outcome.MANUAL
    assert "nf-core subworkflows remove utils_nfvalidation_plugin" in (
        result.message
    )


def test_component_dropped_by_template_and_pipeline_is_already_applied(
    tmp_path: Path,
) -> None:
    # Given
    write_modules_json(tmp_path, {}, {})
    operation = NfCoreComponent(
        "subworkflows", "utils_nfvalidation_plugin", git_sha=None
    )

    # When
    result = operation.apply(Workspace(tmp_path))

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


def test_invalid_modules_json_is_a_conflict_not_a_crash(
    tmp_path: Path,
) -> None:
    # Given a modules.json left broken by a merge
    (tmp_path / "modules.json").write_text('{"repos": {"a": 1 "b": 2}}\n')
    operation = NfCoreComponent("modules", "multiqc", git_sha="abc123")

    # When
    result = operation.apply(Workspace(tmp_path))

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "modules.json is not valid JSON" in result.message
