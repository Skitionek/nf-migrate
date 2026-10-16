from editops import find, first_of, load, migration_path, original_source, regex, replace_ops

path = migration_path("3.4.0")
operations = load(path).operations
utils = "subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf"


def append_arguments(call: str, arguments: list[str]) -> str:
    """Pattern and replacement adding arguments after a call's last one."""
    pattern = (
        rf"^([ \t]*{call}\s*\(\n(?:(?![ \t]*\)\s*\n)[^\n]*\n)*?)"
        r"([ \t]+)([^\n]*?[^,\s])[ \t]*\n([ \t]*\)[ \t]*\n)"
    )
    added = "".join(rf",\n\2{argument}" for argument in arguments)
    return pattern, rf"\1\2\3{added}\n\4"


call = find(operations, "main.nf", old_equals="        params.input\n")
pattern, replacement = append_arguments(
    "PIPELINE_INITIALISATION", ["params.help", "params.help_full", "params.show_hidden"]
)
take = find(operations, utils, new_contains="    help_full         // boolean")
help_lines = operations[take].new[len(operations[take].old):]
plugin = find(operations, utils, old_equals="        null\n")
plugin_pattern, plugin_replacement = append_arguments(
    "UTILS_NFSCHEMA_PLUGIN",
    ["help", "help_full", "show_hidden", "before_text", "after_text", "command"],
)
reason = (
    "Hand-edited: pipelines pass their own arguments too, so the new ones\n"
    "go after the last argument, in the call and in take: alike."
)
replace_ops(path, {
    call: first_of("main.nf", [
        original_source(path, call),
        regex("main.nf", pattern, replacement,
              r"\A(?=[\s\S]*params\.help_full)[\s\S]*", ""),
    ], reason),
    take: first_of(utils, [
        original_source(path, take),
        regex(utils,
              r"\A(?P<take>[\s\S]*?^[ \t]*take:\n(?:(?![ \t]*main:)[^\n]*\n)*?)(?=\n?[ \t]*main:\n)",
              r"\g<take>" + help_lines,
              r"\A(?=[\s\S]*^[ \t]*help_full\b)[\s\S]*", ""),
    ], reason),
    plugin: first_of(utils, [
        original_source(path, plugin),
        regex(utils, plugin_pattern, plugin_replacement,
              r"\A(?=[\s\S]*UTILS_NFSCHEMA_PLUGIN\s*\([^)]*help_full)[\s\S]*", ""),
    ], reason),
})
