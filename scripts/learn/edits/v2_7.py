from editops import find, load, migration_path, regex, replace_ops

path = migration_path("2.7")
operations = load(path).operations
arm = find(operations, "nextflow.config", new_contains="    arm {\n")
replace_ops(path, {
    arm: regex(
        "nextflow.config",
        r"^    singularity \{\n",
        "    arm {\n"
        "        docker.runOptions = '-u $(id -u):$(id -g) --platform=linux/amd64'\n"
        "    }\n"
        "    singularity {\n",
        r"^[ \t]*arm \{[\s\S]*?^    singularity \{\n",
        "Hand-edited: pipelines add their own lines to the docker profile this\n"
        "was anchored on; the arm profile goes before singularity either way.",
    ),
})
