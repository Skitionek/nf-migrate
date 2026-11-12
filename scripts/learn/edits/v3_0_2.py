from editops import find, load, migration_path, replace_ops

path = migration_path("3.0.2")
operations = load(path).operations
ref = find(
    operations,
    ".github/workflows/template_version_comment.yml",
    new_contains="ref: ${{ github.event.pull_request.head.sha }}",
)
reason = (
    "Hand-edited: 3.0.2 made the checkout of template_version_comment.yml take\n"
    "`ref: ${{ github.event.pull_request.head.sha }}`. That workflow runs on\n"
    "pull_request_target, with the base repository's secrets and a write\n"
    "token even for fork PRs, so the fork's .nf-core.yml (whose\n"
    "nf_core_version goes into `pip install`) would be read in a privileged\n"
    "job. It is left out: the workflow keeps checking out the base branch."
)
replace_ops(path, {ref: "".join(f"    # {line}\n" for line in reason.splitlines())})
