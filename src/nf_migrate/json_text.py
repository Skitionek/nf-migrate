"""Edit JSON text one member at a time, keeping the rest byte for byte.

`json.loads` and `json.dumps` would reformat the whole file, which in an
nf-core pipeline is formatted by prettier. Here the text is parsed only to
learn where each member starts and ends, so an edit touches just that
member and the file keeps its layout.
"""

import json
from dataclasses import dataclass, field


class JsonTextError(Exception):
    pass


@dataclass(slots=True)
class Node:
    """A JSON value and its [start, end) offsets in the text."""

    start: int
    end: int
    members: list["Member"] = field(default_factory=list)
    is_object: bool = False


@dataclass(slots=True)
class Member:
    """An object member: `"key": value`, with the key's start offset."""

    key: str
    key_start: int
    value: Node


def parse(text: str) -> Node:
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        raise JsonTextError(str(error)) from error
    reader = _Reader(text)
    return reader.read_value()


def find_member(root: Node, pointer: list[str]) -> Member | None:
    """The member at `pointer`, a list of object keys from the root."""
    node = root
    member = None
    for key in pointer:
        if not node.is_object:
            return None
        member = next((item for item in node.members if item.key == key), None)
        if member is None:
            return None
        node = member.value
    return member


def replace_value(text: str, member: Member, value_text: str) -> str:
    indent = line_indent(text, member.key_start)
    value = indent_continuation_lines(value_text, indent)
    return text[: member.value.start] + value + text[member.value.end :]


def delete_member(text: str, root: Node, member: Member) -> str:
    parent = _parent_of(root, member)
    if parent is None:
        raise JsonTextError(f"no object holds {member.key!r}")
    members = parent.members
    index = members.index(member)

    if len(members) == 1:
        return text[: parent.start + 1] + text[parent.end - 1 :]
    if index > 0:
        # From the end of the previous value: takes the comma, the line
        # break and the member itself.
        previous = members[index - 1]
        return text[: previous.value.end] + text[member.value.end :]
    following = members[1]
    return text[: member.key_start] + text[following.key_start :]


def insert_member(
    text: str, parent: Node, key: str, value_text: str, after: str | None
) -> str:
    """Add `"key": value` after the member `after`, or after the last one."""
    anchor = next((item for item in parent.members if item.key == after), None)
    if anchor is None and parent.members:
        anchor = parent.members[-1]

    if anchor is not None:
        indent = line_indent(text, anchor.key_start)
        value = indent_continuation_lines(value_text, indent)
        member_text = f",\n{indent}{json.dumps(key)}: {value}"
        position = anchor.value.end
        return text[:position] + member_text + text[position:]

    parent_indent = line_indent(text, parent.start)
    indent = parent_indent + _indent_unit(text)
    value = indent_continuation_lines(value_text, indent)
    inner = f"\n{indent}{json.dumps(key)}: {value}\n{parent_indent}"
    return text[: parent.start + 1] + inner + text[parent.end - 1 :]


def line_indent(text: str, offset: int) -> str:
    line_start = text.rfind("\n", 0, offset) + 1
    line = text[line_start:offset]
    return line[: len(line) - len(line.lstrip())]


def indent_continuation_lines(value_text: str, indent: str) -> str:
    """Indent every line but the first, which follows `"key": `."""
    lines = value_text.split("\n")
    indented = [lines[0]] + [
        indent + line if line else line for line in lines[1:]
    ]
    return "\n".join(indented)


def dedent_continuation_lines(value_text: str, indent: str) -> str:
    """The inverse of `indent_continuation_lines`."""
    lines = value_text.split("\n")
    dedented = [lines[0]]
    for line in lines[1:]:
        dedented.append(
            line[len(indent) :] if line.startswith(indent) else line
        )
    return "\n".join(dedented)


def _indent_unit(text: str) -> str:
    indents = [
        len(line) - len(line.lstrip(" "))
        for line in text.splitlines()
        if line.startswith(" ")
    ]
    return " " * (min(indents) if indents else 4)


def _parent_of(node: Node, member: Member) -> Node | None:
    if member in node.members:
        return node
    for child in node.members:
        parent = _parent_of(child.value, member)
        if parent is not None:
            return parent
    return None


class _Reader:
    """Recursive descent over text `json.loads` has already accepted."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.position = 0

    def read_value(self) -> Node:
        self._skip_whitespace()
        start = self.position
        character = self.text[start]
        if character == "{":
            return self._read_object()
        if character == "[":
            self._read_array()
        elif character == '"':
            self._read_string()
        else:
            self._read_literal()
        return Node(start, self.position)

    def _read_object(self) -> Node:
        node = Node(self.position, self.position, is_object=True)
        self.position += 1
        self._skip_whitespace()
        while self.text[self.position] != "}":
            key_start = self.position
            self._read_string()
            key = json.loads(self.text[key_start : self.position])
            self._skip_whitespace()
            self.position += 1  # the colon
            value = self.read_value()
            node.members.append(Member(key, key_start, value))
            self._skip_whitespace()
            if self.text[self.position] == ",":
                self.position += 1
                self._skip_whitespace()
        self.position += 1
        node.end = self.position
        return node

    def _read_array(self) -> None:
        self.position += 1
        self._skip_whitespace()
        while self.text[self.position] != "]":
            self.read_value()
            self._skip_whitespace()
            if self.text[self.position] == ",":
                self.position += 1
                self._skip_whitespace()
        self.position += 1

    def _read_string(self) -> None:
        self.position += 1
        while self.text[self.position] != '"':
            if self.text[self.position] == "\\":
                self.position += 1
            self.position += 1
        self.position += 1

    def _read_literal(self) -> None:
        while (
            self.position < len(self.text)
            and self.text[self.position] not in ",}] \t\r\n"
        ):
            self.position += 1

    def _skip_whitespace(self) -> None:
        while (
            self.position < len(self.text)
            and self.text[self.position] in " \t\r\n"
        ):
            self.position += 1
