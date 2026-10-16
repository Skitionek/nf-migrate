from editops import find, first_of, load, migration_path, original_source, regex, replace_ops

path = migration_path("4.1.0")
operations = load(path).operations
utils = "subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf"
plugin = find(operations, utils, old_equals="        command\n", new_equals="        command,\n        false\n")
call = r"^([ \t]*UTILS_NFSCHEMA_PLUGIN\s*\(\n(?:(?![ \t]*\)\s*\n)[^\n]*\n)*?)"
replace_ops(path, {
    plugin: first_of(utils, [
        original_source(path, plugin),
        regex(
            utils,
            call + r"([ \t]+)([^\n]*?[^,\s])[ \t]*\n([ \t]*\)[ \t]*\n)",
            r"\1\2\3,\n\2false\n\4",
            call + r"[ \t]+false[ \t]*\n[ \t]*\)[ \t]*\n",
            "",
        ),
    ], "Hand-edited: pipelines that kept fewer arguments do not end the call\n"
       "with command; false goes after the last argument either way."),
})
