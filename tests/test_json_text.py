import pytest

from nf_migrate.json_text import (
    JsonTextError,
    delete_member,
    find_member,
    insert_member,
    parse,
    replace_value,
)

SCHEMA = """\
{
    "$defs": {
        "options": {
            "properties": {
                "outdir": {
                    "type": "string",
                    "format": "directory-path"
                },
                "email": {
                    "type": "string"
                }
            }
        }
    }
}
"""

PROPERTIES = ["$defs", "options", "properties"]


# Reading members with their positions
def test_find_member_returns_the_value_text() -> None:
    # Given
    document = parse(SCHEMA)

    # When
    member = find_member(document, [*PROPERTIES, "outdir", "format"])

    # Then
    assert member is not None
    assert SCHEMA[member.value.start : member.value.end] == '"directory-path"'


def test_find_member_is_none_for_a_missing_key() -> None:
    # Given
    document = parse(SCHEMA)

    # When
    member = find_member(document, [*PROPERTIES, "outdir", "pattern"])

    # Then
    assert member is None


def test_invalid_json_is_rejected() -> None:
    # When / Then
    with pytest.raises(JsonTextError):
        parse('{"a": }')


# Editing members in place
def test_replace_value_keeps_the_rest_of_the_text() -> None:
    # Given
    document = parse(SCHEMA)
    member = find_member(document, [*PROPERTIES, "email", "type"])

    # When
    edited = replace_value(SCHEMA, member, '"integer"')

    # Then
    assert edited == SCHEMA.replace(
        '"email": {\n                    "type": "string"',
        '"email": {\n                    "type": "integer"',
    )


def test_delete_member_removes_its_line_and_comma() -> None:
    # Given
    document = parse(SCHEMA)
    member = find_member(document, [*PROPERTIES, "outdir", "format"])

    # When
    edited = delete_member(SCHEMA, document, member)

    # Then
    assert edited == SCHEMA.replace(
        '"type": "string",\n                    "format": "directory-path"',
        '"type": "string"',
    )


def test_delete_the_first_member() -> None:
    # Given
    document = parse(SCHEMA)
    member = find_member(document, [*PROPERTIES, "outdir"])

    # When
    edited = delete_member(SCHEMA, document, member)

    # Then
    assert parse(edited)
    assert '"outdir"' not in edited
    assert edited.startswith('{\n    "$defs": {\n        "options": {\n')
    assert '"properties": {\n                "email": {' in edited


def test_insert_member_after_a_sibling_with_its_indentation() -> None:
    # Given a new member whose value spans lines
    document = parse(SCHEMA)
    parent = find_member(document, [*PROPERTIES])
    value = '{\n    "type": "boolean"\n}'

    # When
    edited = insert_member(SCHEMA, parent.value, "validate", value, "outdir")

    # Then
    assert (
        "                },\n"
        '                "validate": {\n'
        '                    "type": "boolean"\n'
        "                },\n"
        '                "email": {'
    ) in edited
