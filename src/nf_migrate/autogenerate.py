"""Write a migration from two renders of the nf-core template.

The refs are two commits holding the template as rendered by consecutive
nf-core/tools releases: a TEMPLATE branch, or a history built by
scripts/build_template_history.sh. Values from the render's `.nf-core.yml`
template section (pipeline name, author, ...) become {{placeholders}}, so
the migration applies to any pipeline.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from fnmatch import fnmatch
from pathlib import Path

from nf_migrate.changelog import release_notes
from nf_migrate.operations import (
    NF_CORE_MODULES_REPO,
    TODO_NOTE,
    VERSION,
    _version_key,
    find_line_aligned,
    is_inside_match,
)
from nf_migrate.variables import placeholder, template_variables, templatize
from nf_migrate.version import NF_CORE_YML, parse_version, stamp_version
from nf_migrate.yaml_edit import YamlListItem, yaml_changes

MODULES_JSON = "modules.json"
COMPONENT_KINDS = ("modules", "subworkflows")

# Renders of releases before 3.0 keep the version and template values here:
# those releases wrote neither into .nf-core.yml, and adding them there
# would put text into migrations that no real pipeline has.
RENDER_METADATA = ".nf-migrate-render.yml"

# Template changes a release shipped by mistake. Migrations follow what was
# intended, so these are left out: (release, file, text the change adds).
UNINTENDED_CHANGES = (
    # 2.3.1 put an nf-core/tools release note into the pipeline CHANGELOG;
    # 2.3.2 took it out again, and keeps removing it from pipelines that
    # merged it.
    ("2.3.1", "CHANGELOG.md", "Clarified conda usage"),
)

# Files nf-core generates rather than templates. The RO-Crate gets fresh
# timestamps and random IDs on every render, and the container configs
# follow the installed module versions, so their hunks would rarely match a
# pipeline. The migration names the command that rebuilds them instead.
GENERATED_FILE_INSTRUCTIONS = {
    "ro-crate-metadata.json": "regenerate with `nf-core pipelines rocrate`",
    "conf/containers_*.config": (
        "regenerate with `nf-core pipelines lint --fix container_configs`"
    ),
}


@dataclass(frozen=True, slots=True)
class FileChange:
    status: str
    path: str


@dataclass(frozen=True, slots=True)
class GeneratedMigration:
    revision: str
    down_revision: str
    source: str


@dataclass(slots=True)
class Hunk:
    """Consecutive non-equal opcodes plus the context lines around them."""

    first_opcode: int
    last_opcode: int
    context_before: int = 0
    context_after: int = 0


def generate_migration(
    repo: Path, old_ref: str, new_ref: str, changelog: str | None = None
) -> GeneratedMigration:
    """The migration from `old_ref` to `new_ref`.

    With the nf-core/tools `changelog`, the release's notes go into the
    migration's docstring.
    """
    old_metadata = _render_metadata(repo, old_ref)
    new_metadata = _render_metadata(repo, new_ref)
    old_version = parse_version(old_metadata)
    new_version = parse_version(new_metadata)
    if old_version is None or new_version is None:
        raise ValueError(f"{NF_CORE_YML} has no nf_core_version at both refs")
    variables = template_variables(new_metadata)

    old_components = _component_shas(_show(repo, old_ref, MODULES_JSON))
    new_components = _component_shas(_show(repo, new_ref, MODULES_JSON))
    changed_components: set[tuple[str, str]] = {
        component
        for component in old_components.keys() | new_components.keys()
        if old_components.get(component) != new_components.get(component)
    }
    known_components = old_components.keys() | new_components.keys()

    operation_sources: list[str] = []
    generated_file_patterns: set[str] = set()
    for change in _changed_files(repo, old_ref, new_ref):
        # modules.json follows the component updates below.
        if change.path in (MODULES_JSON, RENDER_METADATA):
            continue
        component = _component_for_path(change.path, known_components)
        if component is not None:
            changed_components.add(component)
            continue
        pattern = _generated_file_pattern(change.path)
        if pattern is not None:
            generated_file_patterns.add(pattern)
            continue
        operation_sources.extend(
            _operations_for_change(
                repo, old_ref, new_ref, change, new_version, variables
            )
        )

    for kind, name in sorted(changed_components):
        git_sha = new_components.get((kind, name))
        operation_sources.append(
            _call("NfCoreComponent", kind, name, git_sha=git_sha)
        )
    for pattern in sorted(generated_file_patterns):
        instruction = GENERATED_FILE_INSTRUCTIONS[pattern]
        operation_sources.append(_call("ManualStep", pattern, instruction))

    notes = None
    if changelog is not None:
        notes = release_notes(changelog, new_version)
    source = _render_module(old_version, new_version, operation_sources, notes)
    return GeneratedMigration(new_version, old_version, source)


def _render_metadata(repo: Path, ref: str) -> str:
    """The render's nf_core_version and template values, as YAML."""
    metadata = _show(repo, ref, RENDER_METADATA)
    if metadata is not None:
        return metadata
    return _show(repo, ref, NF_CORE_YML) or ""


def _component_shas(modules_json: str | None) -> dict[tuple[str, str], str]:
    """(kind, name) -> git_sha for the nf-core components in modules.json."""
    if modules_json is None:
        return {}
    repos = json.loads(modules_json).get("repos", {})
    nf_core_repo = repos.get(NF_CORE_MODULES_REPO, {})

    shas: dict[tuple[str, str], str] = {}
    for kind in COMPONENT_KINDS:
        components = nf_core_repo.get(kind, {}).get("nf-core", {})
        for name, entry in components.items():
            shas[(kind, name)] = entry.get("git_sha")
    return shas


def _component_for_path(
    path: str, known_components: set[tuple[str, str]]
) -> tuple[str, str] | None:
    """The nf-core module or subworkflow a file belongs to, if any."""
    for kind in COMPONENT_KINDS:
        prefix = f"{kind}/nf-core/"
        if not path.startswith(prefix):
            continue
        # Longest known name first: samtools/sort before samtools.
        names = sorted(
            (
                name
                for known_kind, name in known_components
                if known_kind == kind
            ),
            key=len,
            reverse=True,
        )
        for name in names:
            if path.startswith(f"{prefix}{name}/"):
                return (kind, name)
        # Not in either modules.json: fall back to the first path segment.
        return (kind, path[len(prefix) :].split("/", 1)[0])
    return None


def _generated_file_pattern(path: str) -> str | None:
    for pattern in GENERATED_FILE_INSTRUCTIONS:
        if fnmatch(path, pattern):
            return pattern
    return None


def _operations_for_change(
    repo: Path,
    old_ref: str,
    new_ref: str,
    change: FileChange,
    version: str,
    variables: dict[str, str],
) -> list[str]:
    path = templatize(change.path, variables)
    if change.status == "binary":
        instruction = "binary file changed in the template; copy it by hand"
        return [_call("ManualStep", path, instruction)]

    old_text = _show(repo, old_ref, change.path)
    new_text = _show(repo, new_ref, change.path)
    for text in (old_text, new_text):
        _reject_placeholder_lookalikes(change.path, text, variables)

    # The runner stamps nf_core_version itself, creating .nf-core.yml if
    # need be, so the stamp line is the same on both sides and never part of
    # a change; diffing it would tie hunks to its quoting and position.
    if change.path == NF_CORE_YML:
        old_text = stamp_version(old_text or "", version)
        new_text = stamp_version(new_text or "", version)

    if old_text is None and new_text is not None:
        content = templatize(new_text, variables)
        return [_call("CreateFile", path, content=content)]
    if new_text is None and old_text is not None:
        expected_content = templatize(old_text, variables)
        return [_call("DeleteFile", path, expected_content=expected_content)]
    if old_text is None or new_text is None:
        return []

    operations: list[str] = []
    is_yaml = change.path.endswith((".yml", ".yaml"))
    # The template file as the blocks so far leave it.
    current_text = old_text
    is_prose = change.path.endswith(PROSE_SUFFIXES)
    for block in diff_blocks(old_text, new_text, is_prose):
        old_block, new_block = block.old, block.new
        text_before_block = current_text
        current_text = _apply_block(current_text, block)
        unintended = _unintended_change(
            version, change.path, old_block, new_block
        )
        if unintended is not None:
            operations.append(
                f"    # Left out: {version} added {unintended!r} to "
                f"{change.path} by mistake."
            )
            continue
        # Values in YAML are found by key path, whatever the lines around.
        if is_yaml:
            yaml_operations = yaml_changes(text_before_block, current_text)
            if yaml_operations is not None:
                operations.extend(
                    _yaml_call(path, operation, variables)
                    for operation in yaml_operations
                )
                continue
        old = templatize(old_block, variables)
        if new_block is None:
            operations.append(_call("RemoveText", path, text=old))
            continue
        new = templatize(new_block, variables)
        context = {}
        if block.context_before:
            context["context_before"] = templatize(
                block.context_before, variables
            )
        if block.context_after:
            context["context_after"] = templatize(
                block.context_after, variables
            )
        # Pipelines copy CI steps; a bump of one line applies to every copy.
        if change.path.startswith(".github/") and not block.has_own_context:
            context["every"] = True
        added_lines = set(new_block.splitlines()) - set(old_block.splitlines())
        # Only for boilerplate (prose, or nothing but comments), and only
        # where the template file has such notes already, or even an
        # untouched template would skip it.
        adds_note = any(TODO_NOTE in line for line in added_lines)
        is_boilerplate = change.path.endswith(".md") or all(
            _is_comment(line) for line in added_lines if line.strip()
        )
        if adds_note and is_boilerplate and TODO_NOTE in old_text:
            context["requires"] = TODO_NOTE
        replace = _call("Replace", path, old=old, new=new, **context)
        bump = _version_bump(old, new)
        if bump is not None:
            prefix, old_version, new_version = bump
            fallback = _call(
                "BumpVersion",
                path,
                prefix=prefix,
                old=old_version,
                new=new_version,
            )
            operations.append(_first_of_call(path, [replace, fallback]))
            continue
        segment = _segment_change(old_block, new_block, old_text)
        if segment is not None:
            old_segment, new_segment = (
                templatize(part, variables) for part in segment
            )
            fallback = _call(
                "RegexReplace",
                path,
                pattern=_pattern_literal(old_segment),
                replacement=new_segment.replace("\\", "\\\\"),
                applied=_pattern_literal(new_segment),
            )
            operations.append(_first_of_call(path, [replace, fallback]))
            continue
        operations.append(replace)
    return operations


# A changed stretch of one line this long is specific enough to find on
# its own, whatever the pipeline did to the rest of the line.
SEGMENT_CHARACTERS = 8


def _segment_change(
    old: str, new: str, old_text: str
) -> tuple[str, str] | None:
    """(old, new) stretch of the one line a block changes, if distinctive.

    The stretch runs from the first to the last differing character,
    widened to whole words. It must occur once in the template file.
    """
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    if len(old_lines) != len(new_lines):
        return None
    changed = [
        (old_line, new_line)
        for old_line, new_line in zip(old_lines, new_lines, strict=True)
        if old_line != new_line
    ]
    if len(changed) != 1:
        return None
    old_line, new_line = changed[0]
    start = 0
    while (
        start < min(len(old_line), len(new_line))
        and old_line[start] == new_line[start]
    ):
        start += 1
    end = 0
    while (
        end < min(len(old_line), len(new_line)) - start
        and old_line[-1 - end] == new_line[-1 - end]
    ):
        end += 1
    while start > 0 and _is_word(old_line[start - 1]):
        start -= 1
    while end > 0 and _is_word(old_line[len(old_line) - end]):
        end -= 1
    old_segment = old_line[start : len(old_line) - end]
    new_segment = new_line[start : len(new_line) - end]
    has_content = sum(c.isalnum() for c in old_segment) >= 3
    if len(old_segment) < SEGMENT_CHARACTERS or not has_content:
        return None
    if old_text.count(old_segment) != 1 or new_segment in old_text:
        return None
    return old_segment, new_segment


def _is_word(character: str) -> bool:
    return character.isalnum() or character == "_"


def _pattern_literal(text: str) -> str:
    """`text` as a pattern, its {{placeholders}} left to be filled."""
    escaped = re.sub(r"([.^$*+?{}\[\]\\|()])", r"\\\1", text)
    return escaped.replace(r"\{\{", "{{").replace(r"\}\}", "}}")


def _version_bump(old: str, new: str) -> tuple[str, str, str] | None:
    """(prefix pattern, old, new) when one line differs only in a version.

    Pipelines edit the rest of such lines (a comment after a plugin id,
    their own options), which the exact replacement would not survive.
    """
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    if len(old_lines) != len(new_lines):
        return None
    changed = [
        (old_line, new_line)
        for old_line, new_line in zip(old_lines, new_lines, strict=True)
        if old_line != new_line
    ]
    if len(changed) != 1:
        return None
    old_line, new_line = changed[0]
    old_parts = re.split(f"({VERSION})", old_line)
    new_parts = re.split(f"({VERSION})", new_line)
    if len(old_parts) != len(new_parts):
        return None
    differing = [
        index
        for index, (a, b) in enumerate(zip(old_parts, new_parts, strict=True))
        if a != b
    ]
    # re.split puts captured versions at odd indexes.
    if len(differing) != 1 or differing[0] % 2 == 0:
        return None
    index = differing[0]
    old_version, new_version = old_parts[index], new_parts[index]
    if _version_key(new_version) <= _version_key(old_version):
        return None
    before_version = "".join(old_parts[:index]).lstrip()
    if sum(character.isalpha() for character in before_version) < 3:
        return None
    escaped = re.escape(before_version)
    escaped = re.sub(r"(\\ )+", r"\\s+", escaped)
    escaped = escaped.replace(r"\{\{", "{{").replace(r"\}\}", "}}")
    return r"^[ \t]*" + escaped, old_version, new_version


def _first_of_call(path: str, sources: list[str]) -> str:
    """FirstOf source; the nested sources keep their own layout, as
    re-indenting them would change template text in triple quotes."""
    body = "\n".join(sources)
    return (
        f"    FirstOf(\n        {path!r},\n        operations=(\n"
        f"{body}\n        ),\n    ),"
    )


def _apply_block(text: str, block: "Block") -> str:
    """`text` with one generated block applied, as the runner would."""
    new = "" if block.new is None else block.new
    positions = find_line_aligned(text, block.old)
    if len(positions) != 1:
        return text
    start = positions[0]
    return text[:start] + new + text[start + len(block.old) :]


def _yaml_call(path: str, operation, variables: dict[str, str]) -> str:
    """Source for a YamlSet or YamlListItem, with placeholders."""

    def templatized(value):
        if isinstance(value, str):
            return templatize(value, variables)
        if isinstance(value, list):
            return [templatized(item) for item in value]
        if isinstance(value, dict):
            return {name: templatized(item) for name, item in value.items()}
        return value

    keyword: dict = {"key": templatized(operation.key)}
    if isinstance(operation, YamlListItem):
        keyword["item"] = templatized(operation.item)
        keyword["match"] = templatized(operation.match)
    else:
        keyword["value"] = templatized(operation.value)
        if operation.old is not None:
            keyword["old"] = templatized(operation.old)
    if operation.after is not None:
        keyword["after"] = templatized(operation.after)
    return _call(type(operation).__name__, path, **keyword)


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith(("//", "#", "<!--", "/*", "*"))


def _unintended_change(
    version: str, path: str, old_block: str, new_block: str | None
) -> str | None:
    for release, release_path, added_text in UNINTENDED_CHANGES:
        is_added_here = (
            new_block is not None
            and added_text in new_block
            and added_text not in old_block
        )
        if release == version and release_path == path and is_added_here:
            return added_text
    return None


def _reject_placeholder_lookalikes(
    path: str, text: str | None, variables: dict[str, str]
) -> None:
    """Refuse templates that already contain a placeholder's spelling.

    The runner would fill such text with the pipeline's values, changing a
    file the template meant to ship verbatim.
    """
    if text is None:
        return
    for name in variables:
        if placeholder(name) in text:
            raise ValueError(f"{path} already contains {placeholder(name)}")


# Template lines kept around a block to tell apart repeated occurrences.
DISAMBIGUATION_LINES = 2


@dataclass(frozen=True, slots=True)
class Block:
    old: str
    # None removes one paragraph of a large deletion.
    new: str | None
    context_before: str = ""
    context_after: str = ""
    # Whether old carries context lines of its own, beyond the change.
    has_own_context: bool = False


def diff_hunks(old_text: str, new_text: str) -> list[tuple[str, str | None]]:
    """The (old, new) pairs of diff_blocks."""
    return [(block.old, block.new) for block in diff_blocks(old_text, new_text)]


def diff_blocks(
    old_text: str, new_text: str, is_prose: bool = True
) -> list[Block]:
    """Split a file diff into old/new blocks with minimal unique context.

    Each block keeps only as much surrounding context as it needs to occur
    exactly once in its template file, so local edits a few lines away from
    a template change do not make it conflict. A new block of None removes
    one paragraph of a large deletion (see _split_deletion).
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    opcodes = SequenceMatcher(
        None, old_lines, new_lines, autojunk=False
    ).get_opcodes()

    paragraphs_by_opcode: dict[int, list[str]] = {}
    for index, opcode in enumerate(opcodes):
        paragraphs = _split_deletion(
            opcode, old_lines, new_lines, new_text, is_prose
        )
        if paragraphs is not None:
            paragraphs_by_opcode[index] = paragraphs

    # A hunk that has to grow across a split deletion takes it back.
    while True:
        hunks = [
            Hunk(index, index)
            for index, opcode in enumerate(opcodes)
            if opcode[0] != "equal" and index not in paragraphs_by_opcode
        ]
        hunks = _choose_unique_context(hunks, opcodes, old_text, new_text)
        hunks = _merge_overlapping(hunks, opcodes)
        spanned = {
            index
            for hunk in hunks
            for index in paragraphs_by_opcode
            if hunk.first_opcode < index < hunk.last_opcode
        }
        if not spanned:
            break
        for index in spanned:
            del paragraphs_by_opcode[index]

    blocks: list[tuple[int, list[Block]]] = []
    for hunk in hunks:
        old_block, new_block = _hunk_blocks(hunk, opcodes, old_lines, new_lines)
        _, old_start, _, _, _ = opcodes[hunk.first_opcode]
        _, _, old_end, _, _ = opcodes[hunk.last_opcode]
        before_end = old_start - hunk.context_before
        after_start = old_end + hunk.context_after
        before_start = max(before_end - DISAMBIGUATION_LINES, 0)
        context_before = "".join(old_lines[before_start:before_end])
        context_after = "".join(
            old_lines[after_start : after_start + DISAMBIGUATION_LINES]
        )
        has_own_context = bool(hunk.context_before or hunk.context_after)
        block = Block(
            old_block, new_block, context_before, context_after, has_own_context
        )
        blocks.append((hunk.first_opcode, [block]))
    for index, paragraphs in paragraphs_by_opcode.items():
        removals = [Block(paragraph, None) for paragraph in paragraphs]
        blocks.append((index, removals))
    blocks.sort(key=lambda item: item[0])
    return [block for _, items in blocks for block in items]


# Template deletions are removed paragraph by paragraph, as long as each
# paragraph has some content: a lone "}" says nothing about where it was.


def _split_deletion(
    opcode: tuple,
    old_lines: list[str],
    new_lines: list[str],
    new_text: str,
    is_prose: bool = True,
) -> list[str] | None:
    """The paragraphs of a pure deletion, if each can go on its own.

    Pipelines keep some of a deleted section verbatim and rewrite the rest;
    as one block the deletion would not match, while each verbatim
    paragraph can still go. Every paragraph has to be unique where it is
    removed and absent from the new template, so that absence reads as
    applied.
    """
    tag, old_start, old_end, new_start, _ = opcode
    if tag != "delete":
        return None

    paragraphs: list[list[str]] = []
    for line in old_lines[old_start:old_end]:
        starts_paragraph = (
            paragraphs
            and line.strip()
            and not paragraphs[-1][-1].strip()
            and any(_has_content(item) for item in paragraphs[-1])
            and not _is_heading(paragraphs[-1])
        )
        if not paragraphs or starts_paragraph:
            paragraphs.append([])
        paragraphs[-1].append(line)
    # A paragraph that is not unique where it is removed, or that the new
    # template still has, goes together with the paragraphs after it.
    texts: list[str] = []
    position = old_start
    pending: list[str] = []
    for paragraph in paragraphs:
        pending = pending + paragraph
        if _is_removable(
            pending, position, old_lines, new_lines, new_start, new_text
        ):
            texts.append("".join(pending))
            position += len(pending)
            pending = []
    if pending:
        if not texts:
            return None
        # The leftover goes with the removal before it.
        previous = texts.pop().splitlines(keepends=True)
        position -= len(previous)
        merged = previous + pending
        if not _is_removable(
            merged, position, old_lines, new_lines, new_start, new_text
        ):
            return None
        texts.append("".join(merged))
    if not texts or not all(
        any(_has_content(line) for line in text.splitlines()) for text in texts
    ):
        return None
    # In code, removing some paragraphs of a block and not others must not
    # leave an unclosed brace or string behind.
    if not is_prose and not all(_is_balanced(text) for text in texts):
        return None
    return texts


# Files where a paragraph stands on its own, whatever is around it.
PROSE_SUFFIXES = (".md", ".txt")


def _is_balanced(text: str) -> bool:
    """Whether a code fragment closes every bracket and string it opens."""
    if text.count('"""') % 2 or text.count("'''") % 2:
        return False
    return all(
        text.count(opening) == text.count(closing)
        for opening, closing in ("{}", "()", "[]")
    )


def _is_removable(
    paragraph: list[str],
    position: int,
    old_lines: list[str],
    new_lines: list[str],
    new_start: int,
    new_text: str,
) -> bool:
    text = "".join(paragraph)
    text_when_removed = "".join(new_lines[:new_start] + old_lines[position:])
    is_unique = len(find_line_aligned(text_when_removed, text)) == 1
    return is_unique and not find_line_aligned(new_text, text)


def _is_heading(paragraph: list[str]) -> bool:
    """A lone heading or comment line, which belongs to what follows."""
    content_lines = [line for line in paragraph if line.strip()]
    return len(content_lines) == 1 and content_lines[0].lstrip().startswith(
        ("#", "//")
    )


def _has_content(line: str) -> bool:
    return sum(character.isalnum() for character in line) >= 3


def _choose_unique_context(
    hunks: list[Hunk], opcodes: list, old_text: str, new_text: str
) -> list[Hunk]:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    index = 0
    while index < len(hunks):
        hunk = hunks[index]
        max_before = _equal_length(opcodes, hunk.first_opcode - 1)
        max_after = _equal_length(opcodes, hunk.last_opcode + 1)

        found_unique_context = False
        # A replacement whose changed lines are unique needs no context, so
        # local edits to neighbouring lines cannot block it. Insertions and
        # deletions keep one line: without it, already applied is
        # indistinguishable from not applicable.
        first_tag = opcodes[hunk.first_opcode][0]
        last_tag = opcodes[hunk.last_opcode][0]
        is_replacement = first_tag == last_tag == "replace"
        first_context = 0 if is_replacement else 1
        for context in range(first_context, max(max_before, max_after, 1) + 1):
            hunk.context_before = min(context, max_before)
            hunk.context_after = min(context, max_after)
            old_block, new_block = _hunk_blocks(
                hunk, opcodes, old_lines, new_lines
            )
            # Hunks apply top to bottom, so the old block has to be unique
            # in the file with the hunks above it already applied. In the
            # new file it may only remain inside the new block, which
            # Replace reads as applied; anywhere else, running the
            # migration again would apply it twice.
            text_when_applied = _text_before_hunk(
                hunk, opcodes, old_lines, new_lines
            )
            # Nor may the new block be there before the change, or it
            # reads as already applied (a blank line added to blank lines).
            new_block_is_new = not find_line_aligned(
                text_when_applied, new_block
            )
            is_unambiguous = (
                _is_unique(text_when_applied, old_block)
                and _is_unique(new_text, new_block)
                and _only_inside_new_block(new_text, old_block, new_block)
                and new_block_is_new
            )
            if is_unambiguous:
                found_unique_context = True
                break

        # The neighbouring equal blocks are too short to make this hunk
        # unique, so grow it across them into the next or previous hunk.
        if not found_unique_context and len(hunks) > 1:
            if index + 1 < len(hunks):
                hunks[index : index + 2] = [
                    Hunk(hunk.first_opcode, hunks[index + 1].last_opcode)
                ]
            else:
                hunks[index - 1 : index + 1] = [
                    Hunk(hunks[index - 1].first_opcode, hunk.last_opcode)
                ]
                index -= 1
            continue
        index += 1
    return hunks


def _merge_overlapping(hunks: list[Hunk], opcodes: list) -> list[Hunk]:
    merged: list[Hunk] = []
    for hunk in hunks:
        if merged:
            previous = merged[-1]
            gap = _equal_length(opcodes, previous.last_opcode + 1)
            if previous.context_after + hunk.context_before > gap:
                previous.last_opcode = hunk.last_opcode
                previous.context_after = hunk.context_after
                continue
        merged.append(hunk)
    return merged


def _hunk_blocks(
    hunk: Hunk, opcodes: list, old_lines: list[str], new_lines: list[str]
) -> tuple[str, str]:
    _, old_start, _, new_start, _ = opcodes[hunk.first_opcode]
    _, _, old_end, _, new_end = opcodes[hunk.last_opcode]
    old_block = old_lines[
        old_start - hunk.context_before : old_end + hunk.context_after
    ]
    new_block = new_lines[
        new_start - hunk.context_before : new_end + hunk.context_after
    ]
    return "".join(old_block), "".join(new_block)


def _only_inside_new_block(
    new_text: str, old_block: str, new_block: str
) -> bool:
    new_positions = find_line_aligned(new_text, new_block)
    return all(
        is_inside_match(position, len(old_block), new_positions, new_block)
        for position in find_line_aligned(new_text, old_block)
    )


def _text_before_hunk(
    hunk: Hunk, opcodes: list, old_lines: list[str], new_lines: list[str]
) -> str:
    """The file once every change above `hunk` is applied."""
    _, old_start, _, new_start, _ = opcodes[hunk.first_opcode]
    lines_above = new_lines[:new_start]
    lines_from_hunk = old_lines[old_start:]
    return "".join(lines_above + lines_from_hunk)


def _equal_length(opcodes: list, index: int) -> int:
    if index < 0 or index >= len(opcodes):
        return 0
    tag, old_start, old_end, _, _ = opcodes[index]
    if tag != "equal":
        return 0
    return old_end - old_start


def _is_unique(text: str, block: str) -> bool:
    if not block:
        return False
    return len(find_line_aligned(text, block)) == 1


def _changed_files(repo: Path, old_ref: str, new_ref: str) -> list[FileChange]:
    numstat = _git(
        repo, "diff", "--no-renames", "--numstat", "-z", old_ref, new_ref
    )
    changes: list[FileChange] = []
    for entry in numstat.split("\0"):
        if not entry:
            continue
        added, _, path = entry.split("\t", 2)
        status = "binary" if added == "-" else "text"
        changes.append(FileChange(status, path))
    return changes


def _show(repo: Path, ref: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _call(
    operation: str, *positional: str, **keyword: str | bool | list | dict | None
) -> str:
    """Source for one operation, indented as an item of `operations`."""
    arguments = [f"        {_literal(value)}," for value in positional]
    for name, value in keyword.items():
        arguments.append(f"        {name}={_literal(value)},")
    body = "\n".join(arguments)
    return f"    {operation}(\n{body}\n    ),"


def _literal(value: str | bool | list | dict | None) -> str:
    """Multi-line text as a readable triple-quoted literal when safe."""
    if isinstance(value, list | dict):
        return repr(value)
    if not isinstance(value, str) or "\n" not in value:
        return repr(value)
    is_safe = (
        '"""' not in value and "\\" not in value and not value.endswith('"')
    )
    if is_safe:
        return f'"""\\\n{value}"""'
    return repr(value)


def _render_module(
    old_version: str,
    new_version: str,
    operation_sources: list[str],
    notes: str | None = None,
) -> str:
    operations_body = "\n".join(operation_sources)
    return (
        f"{render_docstring(new_version, notes)}\n"
        "# ruff: noqa: E501, F401, W291, W293\n\n"
        "from nf_migrate.operations import (\n"
        "    BumpVersion,\n"
        "    CreateFile,\n"
        "    DeleteFile,\n"
        "    FirstOf,\n"
        "    ManualStep,\n"
        "    NfCoreComponent,\n"
        "    RegexReplace,\n"
        "    RemoveText,\n"
        "    Replace,\n"
        "    ReplaceFile,\n"
        ")\n"
        "from nf_migrate.yaml_edit import YamlListItem, YamlSet\n\n"
        f"revision = {new_version!r}\n"
        f"down_revision = {old_version!r}\n\n"
        f"operations = [\n{operations_body}\n]\n"
    )


def render_docstring(version: str, notes: str | None) -> str:
    """A migration's docstring, holding the release notes if known."""
    notes_paragraph = ""
    if notes is not None:
        notes_paragraph = _docstring_text(notes) + "\n"
    return (
        f'"""Template update for nf-core/tools {version}.\n\n'
        f"{notes_paragraph}"
        "Generated by nf-migrate; edit freely.\n"
        '"""'
    )


def _docstring_text(text: str) -> str:
    """Text as it has to be written inside a triple-quoted docstring."""
    escaped_backslashes = text.replace("\\", "\\\\")
    return escaped_backslashes.replace('"""', '\\"\\"\\"')
