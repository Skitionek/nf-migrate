"""The pipeline's template version, kept where nf-core/tools keeps it."""

import re
from pathlib import Path

import yaml

NF_CORE_YML = ".nf-core.yml"

# A line-level edit keeps the rest of .nf-core.yml (comments, key order)
# exactly as the pipeline wrote it, which a YAML round trip would not.
VERSION_LINE = re.compile(r"^nf_core_version:[ \t]*(\S+)[ \t]*$", re.MULTILINE)

# Before tools 2.14 a template commit's subject, not .nf-core.yml, says which
# release made it: "Template update for nf-core/tools version 2.7.2".
SUBJECT_VERSION = re.compile(r"nf-core/tools,? version (\S+)")


def read_version(project: Path) -> str | None:
    """The stamped version; None before tools wrote one, or .nf-core.yml."""
    nf_core_yml = project / NF_CORE_YML
    if not nf_core_yml.exists():
        return None
    return parse_version(nf_core_yml.read_text())


def parse_version(content: str) -> str | None:
    match = VERSION_LINE.search(content)
    if match is None:
        return None
    return match.group(1).strip("'\"")


def parse_subject_version(subject: str) -> str | None:
    match = SUBJECT_VERSION.search(subject)
    if match is None:
        return None
    return match.group(1).rstrip(".,")


def stamp_version(content: str, version: str) -> str:
    new_line = f"nf_core_version: {_yaml_string(version)}"
    if VERSION_LINE.search(content) is None:
        return f"{new_line}\n{content}"
    return VERSION_LINE.sub(new_line, content, count=1)


def _yaml_string(version: str) -> str:
    # Unquoted, YAML reads 1.10 as the number 1.1, and nf-core/tools with it.
    if isinstance(yaml.safe_load(version), str):
        return version
    return f"'{version}'"
