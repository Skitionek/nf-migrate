from nf_migrate.changelog import release_notes

CHANGELOG = """\
# nf-core/tools: Changelog

## [v3.5.2 - Terne Topi Patch](https://example.org/3.5.2) - [2025-12-01]

### Template

- Bump the template version badge ([#3950](https://github.com/nf-core/tools/pull/3950))

### Linting

- Lint the new badge

## [v3.5.1 - Terne Topi](https://example.org/3.5.1) - [2025-11-19]

### General

- Fix markdown in sync PR message

## v3.5.0

### Template

- Update actions/upload-artifact to v5

## Version updates

- Bump rich
"""


def test_release_notes_keep_only_the_template_section() -> None:
    # Given
    changelog = CHANGELOG

    # When
    notes = release_notes(changelog, "3.5.2")

    # Then
    assert notes == (
        "nf-core/tools CHANGELOG, Template section of\n"
        "[v3.5.2 - Terne Topi Patch](https://example.org/3.5.2) "
        "- [2025-12-01]:\n"
        "\n"
        "- Bump the template version badge "
        "([#3950](https://github.com/nf-core/tools/pull/3950))\n"
    )


def test_release_notes_keep_the_whole_entry_without_a_template_section() -> (
    None
):
    # Given
    changelog = CHANGELOG

    # When
    notes = release_notes(changelog, "3.5.1")

    # Then
    assert notes == (
        "nf-core/tools CHANGELOG, whole entry (it has no Template section) "
        "of\n"
        "[v3.5.1 - Terne Topi](https://example.org/3.5.1) - [2025-11-19]:\n"
        "\n"
        "### General\n"
        "\n"
        "- Fix markdown in sync PR message\n"
    )


def test_release_notes_end_at_the_next_release_not_at_any_heading() -> None:
    # Given a stray level-2 heading inside the release entry
    changelog = CHANGELOG

    # When
    notes = release_notes(changelog, "3.5.0")

    # Then
    assert notes == (
        "nf-core/tools CHANGELOG, Template section of\n"
        "v3.5.0:\n"
        "\n"
        "- Update actions/upload-artifact to v5\n"
    )


def test_release_notes_are_none_for_an_unknown_release() -> None:
    # Given
    changelog = CHANGELOG

    # When
    notes = release_notes(changelog, "3.5")

    # Then
    assert notes is None
