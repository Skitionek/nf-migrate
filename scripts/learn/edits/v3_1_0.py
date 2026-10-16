from editops import find, first_of, load, migration_path, original_source, regex, replace_ops

path = migration_path("3.1.0")
operations = load(path).operations
mono = find(operations, "nextflow.config", new_contains="    monochromeLogs = params.monochrome_logs\n")
replace_ops(path, {
    mono: first_of("nextflow.config", [
        original_source(path, mono),
        regex(
            "nextflow.config",
            r"^([ \t]*)defaultIgnoreParams\s*=.*\n",
            r"\g<0>\1monochromeLogs = params.monochrome_logs\n",
            r"\A(?=[\s\S]*^[ \t]*monochromeLogs\s*=)[\s\S]*",
            "",
        ),
    ], "Hand-edited: pipelines ignore their own parameters in\n"
       "defaultIgnoreParams, which this was anchored on."),
})
