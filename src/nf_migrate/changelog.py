"""Release notes from the nf-core/tools CHANGELOG, kept in each migration.

A migration is easier to review and to edit by hand next to what the
release meant to change, so `nf-migrate revision` copies the release's
`### Template` notes into the migration's docstring. Patch releases often
have no such section; their whole entry is copied instead.
"""

import re

# "## [v3.5.0 - Terne Topi](...) - [2025-11-19]", or just "## v3.5.2".
RELEASE_HEADING = re.compile(
    r"^## \[?v(?P<version>\d[\w.]*)\b.*$", re.MULTILINE
)
TEMPLATE_HEADING = re.compile(r"^### Template\b.*$", re.MULTILINE)
# Also ends a section: the 3.0.0 entry has a stray "## Version updates".
SECTION_HEADING = re.compile(r"^#{2,3} .*$", re.MULTILINE)


def release_notes(changelog: str, version: str) -> str | None:
    """The CHANGELOG notes for `version`, None if it has no entry."""
    headings = list(RELEASE_HEADING.finditer(changelog))
    for index, heading in enumerate(headings):
        if heading.group("version") != version:
            continue
        entry_end = len(changelog)
        if index + 1 < len(headings):
            entry_end = headings[index + 1].start()
        entry = changelog[heading.end() : entry_end]
        title = heading.group(0).removeprefix("## ")
        return _notes_for_entry(title, entry)
    return None


def _notes_for_entry(title: str, entry: str) -> str:
    template_heading = TEMPLATE_HEADING.search(entry)
    if template_heading is None:
        body = entry.strip()
        source = "whole entry (it has no Template section) of"
    else:
        section = entry[template_heading.end() :]
        next_heading = SECTION_HEADING.search(section)
        if next_heading is not None:
            section = section[: next_heading.start()]
        body = section.strip()
        source = "Template section of"
    return f"nf-core/tools CHANGELOG, {source}\n{title}:\n\n{body}\n"
