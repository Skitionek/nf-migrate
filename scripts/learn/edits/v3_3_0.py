from editops import find, first_of, load, migration_path, original_source, regex, replace_ops

path = migration_path("3.3.0")
operations = load(path).operations
gpu = find(operations, "nextflow.config", new_contains="    gpu {\n")
label = find(operations, "conf/base.config", new_contains="withLabel: process_gpu")
gpu_block = operations[gpu].new[len("    }\n") : operations[gpu].new.index("    test      {")]
label_block = operations[label].new[len("    }\n") : -len("}\n")]
replace_ops(path, {
    gpu: first_of("nextflow.config", [
        original_source(path, gpu),
        regex(
            "nextflow.config",
            r"^[ \t]*test\s*\{\s*includeConfig\s+'conf/test\.config'\s*\}\n",
            gpu_block.replace("\\", "\\\\") + r"\g<0>",
            r"\A(?=[\s\S]*^[ \t]*gpu\s*\{)[\s\S]*",
            "",
        ),
    ], "Hand-edited: pipelines add profiles before test, where this was\n"
       "anchored; the gpu profile goes right before test either way."),
    label: first_of("conf/base.config", [
        original_source(path, label),
        regex(
            "conf/base.config",
            r"\n\}\n*\Z",
            "\n" + label_block.replace("\\", "\\\\") + "}\n",
            r"\A(?=[\s\S]*withLabel:\s*process_gpu)[\s\S]*",
            "",
        ),
    ], "Hand-edited: pipelines end base.config with their own labels; the\n"
       "gpu label goes last either way."),
})
