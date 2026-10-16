"""Pipeline-specific values, swapped for placeholders in migrations.

The nf-core template bakes the pipeline's name, author, description and
version into its files. Migrations store those spots as `{{variable}}`
placeholders, filled in from the target pipeline's `.nf-core.yml`, so one
migration chain serves every pipeline.

Before nf-core/tools 3.0, `.nf-core.yml` had no `template:` section and
sync took the values from the `manifest` in `nextflow.config`, so that is
the fallback for older pipelines.
"""

import re
from pathlib import Path

import yaml

from nf_migrate.version import NF_CORE_YML


class TemplateVariableError(Exception):
    pass


# Placeholder name -> the `template:` key in .nf-core.yml it comes from.
VARIABLE_SOURCES = {
    "pipeline_name": "name",
    "PIPELINE_NAME": "name",
    "pipeline_author": "author",
    "pipeline_description": "description",
    "pipeline_version": "version",
}

NEXTFLOW_CONFIG = "nextflow.config"

MANIFEST_BLOCK = re.compile(r"^manifest\s*\{(.*?)^\}", re.MULTILINE | re.DOTALL)


def pipeline_variables(project: Path) -> dict[str, str]:
    """Placeholder values for a pipeline, falling back to its manifest."""
    nf_core_yml = project / NF_CORE_YML
    nextflow_config = project / NEXTFLOW_CONFIG

    variables = {}
    if nextflow_config.exists():
        variables = manifest_variables(nextflow_config.read_text())
    if nf_core_yml.exists():
        variables.update(template_variables(nf_core_yml.read_text()))
    return variables


def manifest_variables(nextflow_config: str) -> dict[str, str]:
    """Placeholder values from `manifest { ... }` in nextflow.config."""
    block = MANIFEST_BLOCK.search(nextflow_config)
    if block is None:
        return {}

    template: dict[str, str] = {}
    for key in set(VARIABLE_SOURCES.values()):
        # Triple quotes first: tools 2.7 to 2.14 render """author""".
        assignment = re.search(
            rf"^\s*{key}\s*=\s*(\"\"\"|'|\")(.*?)\1",
            block.group(1),
            re.MULTILINE,
        )
        if assignment is not None:
            template[key] = assignment.group(2)
    # The manifest names the repository; the template uses the bare name.
    if "name" in template:
        template["name"] = template["name"].rsplit("/", 1)[-1]
    return _variables_from_template(template)


def template_variables(nf_core_yml: str) -> dict[str, str]:
    """Placeholder values from the `template:` section of `.nf-core.yml`.

    Keys the section lacks are left out; `expand` reports them only if a
    migration actually needs them.
    """
    config = yaml.safe_load(nf_core_yml) or {}
    template = config.get("template") or {}
    return _variables_from_template(template)


def _variables_from_template(template: dict) -> dict[str, str]:
    variables: dict[str, str] = {}
    for name, key in VARIABLE_SOURCES.items():
        value = template.get(key)
        if value:
            variables[name] = str(value)
    if "PIPELINE_NAME" in variables:
        variables["PIPELINE_NAME"] = variables["PIPELINE_NAME"].upper()
    return variables


def expand(text: str, variables: dict[str, str]) -> str:
    for name, source_key in VARIABLE_SOURCES.items():
        token = placeholder(name)
        if token not in text:
            continue
        if name not in variables:
            raise TemplateVariableError(
                f"migration needs {token}, but neither .nf-core.yml "
                f"template.{source_key} nor the nextflow.config manifest "
                "sets it"
            )
        text = text.replace(token, variables[name])
    return text


def templatize(text: str, variables: dict[str, str]) -> str:
    # Longest values first, so a value that contains another one (a
    # description mentioning the name) is replaced as a whole.
    by_length = sorted(variables.items(), key=lambda item: -len(item[1]))
    for name, value in by_length:
        text = text.replace(value, placeholder(name))
    return text


def placeholder(name: str) -> str:
    return "{{" + name + "}}"
