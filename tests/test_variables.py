from nf_migrate.variables import (
    expand,
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
