"""The pipeline's template version, kept where nf-core/tools keeps it."""

import re
from pathlib import Path

NF_CORE_YML = ".nf-core.yml"

# A line-level edit keeps the rest of .nf-core.yml (comments, key order)
# exactly as the pipeline wrote it, which a YAML round trip would not.
VERSION_LINE = re.compile(r"^nf_core_version:[ \t]*(\S+)[ \t]*$", re.MULTILINE)


def read_version(project: Path) -> str | None:
    content = (project / NF_CORE_YML).read_text()
    return parse_version(content)


def parse_version(content: str) -> str | None:
    match = VERSION_LINE.search(content)
    if match is None:
        return None
    return match.group(1).strip("'\"")


def stamp_version(content: str, version: str) -> str:
    new_line = f"nf_core_version: {version}"
    if VERSION_LINE.search(content) is None:
        return f"{new_line}\n{content}"
    return VERSION_LINE.sub(new_line, content, count=1)
