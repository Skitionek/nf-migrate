from pathlib import Path

from nf_migrate.variables import (
    expand,
    pipeline_variables,
    template_variables,
    templatize,
)

NF_CORE_YML = """\
# Held below the synced template version
nf_core_version: 4.0.3
repository_type: pipeline
template:
  author: "Harshil Patel, Phil Ewels"
  description: RNA sequencing analysis pipeline.
  is_nfcore: true
  name: rnaseq
  org: nf-core
  version: 3.28.0dev
"""


def test_template_variables_are_read_from_nf_core_yml() -> None:
    # Given
    content = NF_CORE_YML

    # When
    variables = template_variables(content)

    # Then
    assert variables == {
        "pipeline_name": "rnaseq",
        "PIPELINE_NAME": "RNASEQ",
        "Pipeline_name": "Rnaseq",
        "pipeline_author": "Harshil Patel, Phil Ewels",
        "pipeline_description": "RNA sequencing analysis pipeline.",
        "pipeline_version": "3.28.0dev",
    }


def test_templatize_and_expand_round_trip_between_pipelines() -> None:
    # Given
    sentinel = {
        "pipeline_name": "sentinelpipe",
        "PIPELINE_NAME": "SENTINELPIPE",
    }
    rnaseq = {"pipeline_name": "rnaseq", "PIPELINE_NAME": "RNASEQ"}
    rendered = "include { SENTINELPIPE } from './workflows/sentinelpipe'\n"

    # When
    template = templatize(rendered, sentinel)
    expanded = expand(template, rnaseq)

    # Then
    assert template == (
        "include { {{PIPELINE_NAME}} } from './workflows/{{pipeline_name}}'\n"
    )
    assert expanded == "include { RNASEQ } from './workflows/rnaseq'\n"


def test_the_capitalised_name_of_tools_2_workflow_classes_round_trips() -> None:
    # Given lib/Workflow<Name>.groovy as nf-core/tools 2.x renders it
    sentinel = template_variables(
        "template:\n  name: sentinelpipe\n  author: Sentinel Author\n"
    )
    rnaseq = template_variables("template:\n  name: rnaseq\n")
    rendered = "WorkflowSentinelpipe.initialise(params, log)\n"

    # When
    template = templatize(rendered, sentinel)
    expanded = expand(template, rnaseq)

    # Then
    assert template == "Workflow{{Pipeline_name}}.initialise(params, log)\n"
    assert expanded == "WorkflowRnaseq.initialise(params, log)\n"


# Pipelines from before nf-core/tools 3.0
NEXTFLOW_CONFIG = """\
params {
  name = false
}

manifest {
  name = 'nf-core/slamseq'
  author = 'Tobias Neumann'
  homePage = 'https://github.com/nf-core/slamseq'
  description = "SLAMSeq processing and analysis pipeline"
  version = '1.0.0'
}
"""


def test_variables_come_from_the_manifest_without_a_template_section(
    tmp_path: Path,
) -> None:
    # Given
    (tmp_path / ".nf-core.yml").write_text("repository_type: pipeline\n")
    (tmp_path / "nextflow.config").write_text(NEXTFLOW_CONFIG)

    # When
    variables = pipeline_variables(tmp_path)

    # Then
    assert variables == {
        "pipeline_name": "slamseq",
        "PIPELINE_NAME": "SLAMSEQ",
        "Pipeline_name": "Slamseq",
        "pipeline_author": "Tobias Neumann",
        "pipeline_description": "SLAMSeq processing and analysis pipeline",
        "pipeline_version": "1.0.0",
    }


def test_variables_come_from_the_manifest_without_nf_core_yml(
    tmp_path: Path,
) -> None:
    # Given
    (tmp_path / "nextflow.config").write_text(NEXTFLOW_CONFIG)

    # When
    variables = pipeline_variables(tmp_path)

    # Then
    assert variables["pipeline_name"] == "slamseq"


def test_the_template_section_wins_over_the_manifest(tmp_path: Path) -> None:
    # Given
    (tmp_path / ".nf-core.yml").write_text(NF_CORE_YML)
    (tmp_path / "nextflow.config").write_text(NEXTFLOW_CONFIG)

    # When
    variables = pipeline_variables(tmp_path)

    # Then
    assert variables["pipeline_name"] == "rnaseq"
    assert variables["pipeline_version"] == "3.28.0dev"


def test_manifest_values_may_use_triple_quotes(tmp_path: Path) -> None:
    # Given a manifest as nf-core/tools 2.7 renders it
    (tmp_path / "nextflow.config").write_text(
        "manifest {\n"
        "    name            = 'nf-core/hgtseq'\n"
        '    description     = """A pipeline to investigate HGT"""\n'
        "}\n"
    )

    # When
    variables = pipeline_variables(tmp_path)

    # Then
    assert variables["pipeline_description"] == "A pipeline to investigate HGT"
