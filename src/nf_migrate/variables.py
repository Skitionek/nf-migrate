"""Pipeline-specific values, swapped for placeholders in migrations.

The nf-core template bakes the pipeline's name, author, description and
version into its files. Migrations store those spots as `{{variable}}`
placeholders, filled in from the target pipeline's `.nf-core.yml`, so one
migration chain serves every pipeline.
"""

import yaml


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


def template_variables(nf_core_yml: str) -> dict[str, str]:
    """Placeholder values from the `template:` section of `.nf-core.yml`.

    Keys the section lacks are left out; `expand` reports them only if a
    migration actually needs them.
    """
    config = yaml.safe_load(nf_core_yml) or {}
    template = config.get("template") or {}

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
                f"migration needs {token}, but .nf-core.yml has no "
                f"template.{source_key}"
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
