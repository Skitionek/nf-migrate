"""Edit one YAML value by its key path, leaving the rest of the file alone.

Pipelines customise their GitHub workflows (extra jobs, steps, matrix
entries), so a template change to one value often has different lines
around it than the template had and a text hunk does not match. The key
path still finds it. Only the value's own text changes: comments, quoting
elsewhere and layout stay as the pipeline wrote them.
"""

import re
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from nf_migrate.operations import OperationResult, Outcome, Workspace

# A part is a mapping key, a list index, or a selector {field: values}
# for the list item whose field has one of those values: pipelines add
# their own CI steps, so a step is found by its id or name, not its
# position. Fields are tried in order; "#" holds the template's position,
# the last resort.
Key = list[str | int | dict[str, list[str] | int]]

# Values maintainers bump even when they had pinned their own: versions
# and pinned actions.
VERSION_LIKE = re.compile(r"^v?\d+(\.\d+)+([.-]\w+)*$|^[\w.-]+/[\w./-]+@\S+$")


class YamlPathError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class YamlSet:
    """Set, add or remove one scalar at `key`.

    `value` and `old` are YAML text as the template writes it (quotes
    included); a value of None removes the key, an old of None means the
    template adds it, after the sibling key `after` (first if None).

    A changed value is set when the pipeline still has the template's old
    one. A pipeline's own value is only overwritten for versions and pinned
    actions, which maintainers bump anyway; anything else is a conflict.
    """

    path: str
    key: Key
    value: str | None
    old: str | None = None
    after: str | None = None

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        key = [_expand_part(part, workspace) for part in self.key]
        value = None if self.value is None else workspace.expand(self.value)
        old = None if self.old is None else workspace.expand(self.old)
        change = f"{_render_key(key)}: {old} -> {value}"

        content = workspace.read(path)
        if content is None:
            message = "file does not exist"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        try:
            root = yaml.compose(content)
            parent, node_key, node = _find(root, key)
        except (yaml.YAMLError, YamlPathError) as error:
            message = f"cannot find {_render_key(key)}: {error}"
            return OperationResult(path, Outcome.CONFLICT, message, change)

        if value is None:
            if node is None:
                return OperationResult(
                    path, Outcome.ALREADY_APPLIED, "", change
                )
            updated = _remove(content, node_key, node)
            if updated is None:
                message = f"cannot remove {_render_key(key)} here"
                return OperationResult(path, Outcome.CONFLICT, message, change)
            workspace.write(path, updated)
            return OperationResult(path, Outcome.APPLIED, "", change)

        if node is None:
            updated = _insert(content, parent, key[-1], value, self.after)
            if updated is None:
                message = f"cannot add {_render_key(key)} here"
                return OperationResult(path, Outcome.CONFLICT, message, change)
            workspace.write(path, updated)
            return OperationResult(path, Outcome.APPLIED, "", change)

        if not isinstance(node, yaml.ScalarNode) or _is_multiline(node):
            message = f"{_render_key(key)} is not a one-line value"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        current = node.value
        if current == _scalar_value(value):
            return OperationResult(path, Outcome.ALREADY_APPLIED, "", change)
        if old is None:
            message = "the pipeline sets its own value"
            return OperationResult(
                path, Outcome.ALREADY_APPLIED, message, change
            )
        is_template_value = current == _scalar_value(old)
        new_value = _scalar_value(value)
        is_bump = bool(VERSION_LIKE.match(current)) and bool(
            VERSION_LIKE.match(new_value)
        )
        if is_bump and _is_newer(current, new_value):
            message = f"the pipeline has a newer {current!r}"
            return OperationResult(
                path, Outcome.ALREADY_APPLIED, message, change
            )
        if not is_template_value and not is_bump:
            message = f"the pipeline has {current!r} here"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        start = node.start_mark.index
        end = node.end_mark.index
        workspace.write(path, content[:start] + value + content[end:])
        return OperationResult(path, Outcome.APPLIED, "", change)


def _expand_part(part, workspace: Workspace):
    if isinstance(part, str):
        return workspace.expand(part)
    if isinstance(part, dict):
        return {
            field: values
            if isinstance(values, int)
            else [workspace.expand(value) for value in values]
            for field, values in part.items()
        }
    return part


def _render_key(key: Key) -> str:
    def render(part) -> str:
        if isinstance(part, dict):
            field, values = next(iter(part.items()))
            if field == "#":
                return str(values)
            return f"[{field}={values[0]}]"
        return str(part)

    return ".".join(render(part) for part in key)


def _version_numbers(text: str) -> tuple[int, ...] | None:
    match = re.match(r"^v?(\d+(?:\.\d+)+)$", text)
    if match is None:
        return None
    return tuple(int(number) for number in match.group(1).split("."))


def _is_newer(current: str, wanted: str) -> bool:
    current_numbers = _version_numbers(current)
    wanted_numbers = _version_numbers(wanted)
    if current_numbers is None or wanted_numbers is None:
        return False
    return current_numbers > wanted_numbers


def _scalar_value(text: str) -> str:
    node = yaml.compose(text)
    if not isinstance(node, yaml.ScalarNode):
        raise YamlPathError(f"{text!r} is not a scalar")
    return node.value


def _is_multiline(node: yaml.Node) -> bool:
    return node.start_mark.line != node.end_mark.line or node.style in (
        "|",
        ">",
    )


def _find(
    root: yaml.Node | None, key: Key
) -> tuple[yaml.Node, yaml.Node | None, yaml.Node | None]:
    """(parent of the last key part, its key node, its value node or None)."""
    if root is None:
        raise YamlPathError("empty document")
    node = root
    for depth, part in enumerate(key):
        is_last = depth == len(key) - 1
        child_key, child = _child(node, part)
        if child is None:
            if is_last:
                return node, None, None
            raise YamlPathError(f"no {part!r}")
        if is_last:
            return node, child_key, child
        node = child
    raise YamlPathError("empty key")


def _child(
    node: yaml.Node, part: str | int
) -> tuple[yaml.Node | None, yaml.Node | None]:
    if isinstance(part, dict):
        if not isinstance(node, yaml.SequenceNode):
            raise YamlPathError("a selector looks up a non-list")
        item = _select(node, part, use_position=True)
        if item is None:
            raise YamlPathError(f"no item like {part}")
        return None, item
    if isinstance(part, int):
        if not isinstance(node, yaml.SequenceNode):
            raise YamlPathError(f"{part} indexes a non-list")
        if part >= len(node.value):
            return None, None
        return None, node.value[part]
    if not isinstance(node, yaml.MappingNode):
        raise YamlPathError(f"{part!r} looks up a non-mapping")
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == part:
            return key_node, value_node
    return None, None


def _select(
    sequence: yaml.SequenceNode, selector: dict, use_position: bool
) -> yaml.Node | None:
    """The one item the selector picks; None if none does.

    Fields are tried in order. With `use_position`, the template's
    position ("#") is the last resort.
    """
    for field, values in selector.items():
        if field == "#":
            continue
        matches = [
            item
            for item in sequence.value
            if isinstance(item, yaml.MappingNode)
            and any(
                isinstance(k, yaml.ScalarNode)
                and k.value == field
                and isinstance(v, yaml.ScalarNode)
                and v.value in values
                for k, v in item.value
            )
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise YamlPathError(f"{len(matches)} items with this {field}")
    position = selector.get("#")
    if use_position and isinstance(position, int):
        if position < len(sequence.value):
            return sequence.value[position]
    return None


def _line_start(content: str, index: int) -> int:
    return content.rfind("\n", 0, index) + 1


def _line_end(content: str, index: int) -> int:
    end = content.find("\n", index)
    return len(content) if end == -1 else end + 1


def _is_block_key(content: str, key_node: yaml.Node) -> bool:
    """Whether the key starts its line, bar indentation or a list dash."""
    start = _line_start(content, key_node.start_mark.index)
    prefix = content[start : key_node.start_mark.index]
    return prefix.strip() in ("", "-")


def _remove(
    content: str, key_node: yaml.Node | None, value_node: yaml.Node
) -> str | None:
    if key_node is None or not isinstance(value_node, yaml.ScalarNode):
        return None
    if _is_multiline(value_node) or not _is_block_key(content, key_node):
        return None
    start = _line_start(content, key_node.start_mark.index)
    if content[start : key_node.start_mark.index].strip() == "-":
        return None
    end = _line_end(content, value_node.end_mark.index)
    return content[:start] + content[end:]


def _insert(
    content: str,
    parent: yaml.Node,
    name: str | int,
    value: str,
    after: str | None,
) -> str | None:
    if not isinstance(parent, yaml.MappingNode) or not isinstance(name, str):
        return None
    if not parent.value or parent.flow_style:
        return None
    first_key = parent.value[0][0]
    if not _is_block_key(content, first_key):
        return None
    indent = " " * first_key.start_mark.column
    line = f"{indent}{name}: {value}\n"

    if after is None:
        position = first_key.start_mark.index
        # A first key on a "- " line: the new key goes on the next line.
        if content[_line_start(content, position) : position].strip() == "-":
            end = _line_end(content, parent.value[0][1].end_mark.index)
            if not isinstance(parent.value[0][1], yaml.ScalarNode):
                return None
            return content[:end] + line + content[end:]
        start = _line_start(content, position)
        return content[:start] + line + content[start:]

    for key_node, value_node in parent.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == after:
            if not isinstance(value_node, yaml.ScalarNode):
                return None
            if _is_multiline(value_node):
                return None
            end = _line_end(content, value_node.end_mark.index)
            return content[:end] + line + content[end:]
    return None


@dataclass(frozen=True, slots=True)
class YamlListItem:
    """Make sure one list item, usually a CI step, is there or gone.

    `match` finds the item the way a key path selector does, but never by
    position. `item` is its YAML text as the template writes it, from its
    "- " line through the blank lines after it, or None to remove it. A
    new item goes after the one `after` selects (first if None), indented
    like the pipeline's own items. A pipeline that has the item already,
    in whatever version, keeps it.
    """

    path: str
    key: Key
    item: str | None
    match: dict
    after: dict | None = None

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        key = [_expand_part(part, workspace) for part in self.key]
        match = _expand_part(self.match, workspace)
        after = (
            None if self.after is None else _expand_part(self.after, workspace)
        )
        item = None if self.item is None else workspace.expand(self.item)
        action = "remove" if item is None else "add"
        change = f"{_render_key(key)}: {action} {_render_key([match])}"

        content = workspace.read(path)
        if content is None:
            if item is None:
                return OperationResult(
                    path, Outcome.ALREADY_APPLIED, "", change
                )
            message = "file does not exist"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        try:
            _, _, sequence = _find(yaml.compose(content), key)
            if sequence is not None and not isinstance(
                sequence, yaml.SequenceNode
            ):
                raise YamlPathError("not a list")
            existing = None
            if sequence is not None:
                existing = _select(sequence, match, use_position=False)
        except (yaml.YAMLError, YamlPathError) as error:
            message = f"cannot find {_render_key(key)}: {error}"
            return OperationResult(path, Outcome.CONFLICT, message, change)

        if item is None:
            if existing is None:
                return OperationResult(
                    path, Outcome.ALREADY_APPLIED, "", change
                )
            span = _item_span(content, sequence, existing)
            if span is None:
                message = "cannot remove this item here"
                return OperationResult(path, Outcome.CONFLICT, message, change)
            start, end = span
            workspace.write(path, content[:start] + content[end:])
            return OperationResult(path, Outcome.APPLIED, "", change)

        if existing is not None:
            return OperationResult(path, Outcome.ALREADY_APPLIED, "", change)
        if sequence is None or not sequence.value:
            message = f"no list at {_render_key(key)}"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        position = _insert_position(content, sequence, after)
        column = _dash_column(content, sequence.value[0])
        if position is None or column is None:
            message = "cannot find where the item goes"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        text = _shift(item, column - _leading_spaces(item))
        if text is None:
            message = "cannot indent the item like the pipeline's"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        workspace.write(path, content[:position] + text + content[position:])
        return OperationResult(path, Outcome.APPLIED, "", change)


def _leading_spaces(text: str) -> int:
    first_line = text.lstrip("\n").splitlines()[0]
    return len(first_line) - len(first_line.lstrip(" "))


def _shift(text: str, delta: int) -> str | None:
    lines = []
    for line in text.splitlines(keepends=True):
        if not line.strip():
            lines.append(line)
            continue
        if delta < 0:
            if len(line) - len(line.lstrip(" ")) < -delta:
                return None
            lines.append(line[-delta:])
        else:
            lines.append(" " * delta + line)
    return "".join(lines)


def _dash_column(content: str, item: yaml.Node) -> int | None:
    start = _line_start(content, item.start_mark.index)
    prefix = content[start : item.start_mark.index]
    if prefix.strip() != "-":
        return None
    return prefix.index("-")


def _last_index(node: yaml.Node) -> int:
    if isinstance(node, yaml.ScalarNode):
        return node.end_mark.index
    children: list[yaml.Node] = []
    if isinstance(node, yaml.SequenceNode):
        children = list(node.value)
    elif isinstance(node, yaml.MappingNode):
        children = [part for pair in node.value for part in pair]
    if not children:
        return node.end_mark.index
    return max(_last_index(child) for child in children)


def _item_span(
    content: str, sequence: yaml.SequenceNode, item: yaml.Node
) -> tuple[int, int] | None:
    """From the item's "- " line to where the next item starts."""
    if _dash_column(content, item) is None:
        return None
    start = _line_start(content, item.start_mark.index)
    position = next(
        index for index, other in enumerate(sequence.value) if other is item
    )
    if position + 1 < len(sequence.value):
        following = sequence.value[position + 1]
        return start, _line_start(content, following.start_mark.index)
    last = _last_index(item)
    if last > 0 and content[last - 1] == "\n":
        return start, last
    return start, _line_end(content, last)


def _insert_position(
    content: str, sequence: yaml.SequenceNode, after: dict | None
) -> int | None:
    if after is None:
        return _line_start(content, sequence.value[0].start_mark.index)
    try:
        previous = _select(sequence, after, use_position=True)
    except YamlPathError:
        return None
    if previous is None:
        return None
    span = _item_span(content, sequence, previous)
    return None if span is None else span[1]


# Fields that name a CI step or list item, best first.
SELECTOR_FIELDS = ("id", "name", "uses")


def yaml_changes(
    old_text: str, new_text: str
) -> list[YamlSet | YamlListItem] | None:
    """Operations turning one YAML text into another, if they fit.

    Values, keys holding one-line values and whole list items (CI steps)
    are expressible; anything else is None, and the caller keeps its text
    replacement. The result is checked by applying it to `old_text`.
    """
    try:
        old_root = yaml.compose(old_text)
        new_root = yaml.compose(new_text)
    except yaml.YAMLError:
        return None
    if old_root is None or new_root is None:
        return None
    operations: list[YamlSet | YamlListItem] = []
    differ = _Differ(old_text, new_text, operations)
    if not differ.diff(old_root, new_root, []) or not operations:
        return None

    workspace = Workspace(_NOWHERE)
    workspace.write("file.yml", old_text)
    for operation in operations:
        moved = replace(operation, path="file.yml")
        if moved.apply(workspace).outcome is not Outcome.APPLIED:
            return None
    if workspace.read("file.yml") != new_text:
        return None
    return operations


@dataclass(slots=True)
class _Differ:
    old_text: str
    new_text: str
    operations: list

    def source(self, text: str, node: yaml.Node) -> str:
        return text[node.start_mark.index : node.end_mark.index]

    def diff(self, old: yaml.Node, new: yaml.Node, key: Key) -> bool:
        if isinstance(old, yaml.ScalarNode) and isinstance(
            new, yaml.ScalarNode
        ):
            old_source = self.source(self.old_text, old)
            new_source = self.source(self.new_text, new)
            if old_source == new_source:
                return True
            if _is_multiline(old) or _is_multiline(new):
                return False
            self.operations.append(YamlSet("", key, new_source, old=old_source))
            return True
        if isinstance(old, yaml.MappingNode) and isinstance(
            new, yaml.MappingNode
        ):
            return self.diff_mappings(old, new, key)
        if isinstance(old, yaml.SequenceNode) and isinstance(
            new, yaml.SequenceNode
        ):
            return self.diff_sequences(old, new, key)
        return False

    def diff_mappings(
        self, old: yaml.MappingNode, new: yaml.MappingNode, key: Key
    ) -> bool:
        old_items = _mapping_items(old)
        new_items = _mapping_items(new)
        if old_items is None or new_items is None:
            return False
        for name, value in old_items.items():
            if name in new_items:
                continue
            if not _is_one_line_scalar(value):
                return False
            source = self.source(self.old_text, value)
            self.operations.append(YamlSet("", [*key, name], None, old=source))
        previous = None
        for name, value in new_items.items():
            if name in old_items:
                if not self.diff(old_items[name], value, [*key, name]):
                    return False
            else:
                if not _is_one_line_scalar(value):
                    return False
                source = self.source(self.new_text, value)
                self.operations.append(
                    YamlSet("", [*key, name], source, after=previous)
                )
            previous = name
        return True

    def diff_sequences(
        self, old: yaml.SequenceNode, new: yaml.SequenceNode, key: Key
    ) -> bool:
        are_mappings = all(
            isinstance(item, yaml.MappingNode)
            for item in [*old.value, *new.value]
        )
        if not are_mappings or not old.value or not new.value:
            if len(old.value) != len(new.value):
                return False
            return all(
                self.diff(old_item, new_item, [*key, index])
                for index, (old_item, new_item) in enumerate(
                    zip(old.value, new.value, strict=True)
                )
            )

        pairs = _align(old.value, new.value, self.old_text, self.new_text)
        matched_old = {old_index for old_index, _ in pairs.values()}
        for old_index, item in enumerate(old.value):
            if old_index in matched_old:
                continue
            identity = _identity(item)
            if not identity:
                return False
            self.operations.append(YamlListItem("", key, None, match=identity))
        previous = None
        for new_index, item in enumerate(new.value):
            if new_index in pairs:
                old_index, _ = pairs[new_index]
                old_item = old.value[old_index]
                selector = _pair_selector(old_item, item, old_index)
                if not self.diff(old_item, item, [*key, selector]):
                    return False
                previous = selector
                continue
            identity = _identity(item)
            span = _item_span(self.new_text, new, item)
            if not identity or span is None:
                return False
            text = self.new_text[span[0] : span[1]]
            self.operations.append(
                YamlListItem("", key, text, match=identity, after=previous)
            )
            previous = identity
        return True


def _mapping_items(node: yaml.MappingNode) -> dict[str, yaml.Node] | None:
    items: dict[str, yaml.Node] = {}
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode):
            return None
        items[key_node.value] = value_node
    return items


def _is_one_line_scalar(node: yaml.Node) -> bool:
    return isinstance(node, yaml.ScalarNode) and not _is_multiline(node)


def _field_values(item: yaml.Node) -> dict[str, str]:
    values = {}
    if isinstance(item, yaml.MappingNode):
        for key_node, value_node in item.value:
            if (
                isinstance(key_node, yaml.ScalarNode)
                and key_node.value in SELECTOR_FIELDS
                and isinstance(value_node, yaml.ScalarNode)
            ):
                values[key_node.value] = value_node.value
    return values


def _identity(item: yaml.Node) -> dict[str, list[str]]:
    values = _field_values(item)
    return {
        field: [values[field]] for field in SELECTOR_FIELDS if field in values
    }


def _uses_base(value: str) -> str:
    return value.split("@", 1)[0]


def _align(
    old_items: list[yaml.Node],
    new_items: list[yaml.Node],
    old_text: str,
    new_text: str,
) -> dict[int, tuple[int, None]]:
    """new index -> (old index, None) for items that are the same step.

    Lists of the same length whose items keep their ids and names pair
    up by position; otherwise items pair by id, name or action, and the
    rest by identical text.
    """
    old_fields = [_field_values(item) for item in old_items]
    new_fields = [_field_values(item) for item in new_items]
    if len(old_items) == len(new_items) and all(
        _same_identity(a, b)
        for a, b in zip(old_fields, new_fields, strict=True)
    ):
        return {index: (index, None) for index in range(len(new_items))}
    used: set[int] = set()
    pairs: dict[int, tuple[int, None]] = {}
    for new_index, item in enumerate(new_items):
        fields = _field_values(item)
        for field in SELECTOR_FIELDS:
            if field not in fields:
                continue
            wanted = fields[field]
            candidates = [
                old_index
                for old_index, values in enumerate(old_fields)
                if old_index not in used
                and field in values
                and (
                    _uses_base(values[field]) == _uses_base(wanted)
                    if field == "uses"
                    else values[field] == wanted
                )
            ]
            if len(candidates) == 1:
                used.add(candidates[0])
                pairs[new_index] = (candidates[0], None)
                break
    old_sources = [_node_source(old_text, item) for item in old_items]
    for new_index, item in enumerate(new_items):
        if new_index in pairs:
            continue
        source = _node_source(new_text, item)
        candidates = [
            old_index
            for old_index, old_source in enumerate(old_sources)
            if old_index not in used and old_source == source
        ]
        if len(candidates) == 1:
            used.add(candidates[0])
            pairs[new_index] = (candidates[0], None)
    return pairs


def _same_identity(old_fields: dict, new_fields: dict) -> bool:
    """Whether two items are the same step, allowing a changed version."""
    shared = old_fields.keys() & new_fields.keys()
    if old_fields.keys() != new_fields.keys():
        return False
    return all(
        old_fields[field] == new_fields[field]
        or (
            field == "uses"
            and _uses_base(old_fields[field]) == _uses_base(new_fields[field])
        )
        or field == "name"
        for field in shared
    )


def _node_source(text: str, node: yaml.Node) -> str:
    return text[node.start_mark.index : _last_index(node)]


def _pair_selector(
    old_item: yaml.Node, new_item: yaml.Node, old_index: int
) -> dict:
    old_values = _field_values(old_item)
    new_values = _field_values(new_item)
    selector: dict = {}
    for field in SELECTOR_FIELDS:
        values = []
        for source in (old_values, new_values):
            if field in source and source[field] not in values:
                values.append(source[field])
        if values:
            selector[field] = values
    selector["#"] = old_index
    return selector


# The check above runs in memory; nothing is read from or written here.
_NOWHERE = Path("/nonexistent-nf-migrate-workspace")
