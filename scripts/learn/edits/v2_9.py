from editops import find, load, migration_path, regex, replace_ops

path = migration_path("2.9")
operations = load(path).operations
registry = find(operations, "nextflow.config", new_contains="docker.registry      = 'quay.io'\n")
new = operations[registry].new
block = new[new.index("// Set default registry") : new.index("// Load igenomes.config if required\n")]
replace_ops(path, {
    registry: regex(
        "nextflow.config",
        r"\n+// Load igenomes\.config if required\n",
        "\n\n" + block.replace("\\", "\\\\") + "// Load igenomes.config if required\n",
        r"\A(?=[\s\S]*^docker\.registry\s*=)[\s\S]*",
        "Hand-edited: pipelines end their profiles block with their own\n"
        "profiles, which this was anchored on. The registries and plugins go\n"
        "before the igenomes include, unless the pipeline sets them already.",
    ),
})
