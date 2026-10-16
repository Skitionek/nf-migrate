from editops import find, load, migration_path, regex, replace_ops

path = migration_path("2.10")
operations = load(path).operations
multiqc = find(operations, "conf/modules.config", new_contains="withName: 'MULTIQC'")
dump = find(operations, "workflows/{{pipeline_name}}.nf", new_contains="NfcoreTemplate.dump_parameters")
block = operations[multiqc].new[: -len("\n}\n")]
assert block.startswith("\n    withName: 'MULTIQC'")
replace_ops(path, {
    dump: regex(
        "workflows/{{pipeline_name}}.nf",
        r"^([ \t]*)NfcoreTemplate\.summary\(workflow, params, log\)\n",
        r"\1NfcoreTemplate.dump_parameters(workflow, params)\n\g<0>",
        r"\A(?=[\s\S]*NfcoreTemplate\.dump_parameters\()[\s\S]*",
        "Hand-edited: pipelines nest the completion handlers in their own\n"
        "blocks; the new call goes before the summary at its indentation.",
    ),
    multiqc: regex(
        "conf/modules.config",
        r"\n\}\n*\Z",
        block.replace("\\", "\\\\") + "\n}\n",
        r"\A(?=[\s\S]*withName:\s*'MULTIQC')[\s\S]*",
        "Hand-edited: pipelines end modules.config with their own processes;\n"
        "the MultiQC settings go last, unless the pipeline sets its own.",
    ),
})
