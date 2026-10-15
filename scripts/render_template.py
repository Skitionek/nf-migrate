"""Render a pipeline's nf-core template with the installed nf-core/tools.

Run it under the tools release to render, for example:

    uvx --from nf-core==4.0.3 python scripts/render_template.py \
        path/to/.nf-core.yml path/to/output

This mirrors `PipelineSync.make_template_pipeline` in nf-core/tools: it
renders from the pipeline's `.nf-core.yml` template settings, so the output
matches what that release would commit to the TEMPLATE branch.
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import nf_core
import nf_core.pipelines.create.create
import yaml


class PrettierDumper(yaml.SafeDumper):
    """Indent list items under their key, as prettier formats YAML."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


# nf-core/tools 4.0.x parses `nextflow inspect` stdout as JSON, but
# Nextflow 26 wraps it in [PIPELINE]/[WORKDIR]/[SUCCESS] status lines. The
# shim keeps only the JSON block for `inspect` and passes other calls on.
NEXTFLOW_INSPECT_SHIM = """#!/usr/bin/env bash
if [ "$1" = "inspect" ]; then
    "$REAL_NEXTFLOW" "$@" | sed -n '/^{/,/^}/p'
    exit "${PIPESTATUS[0]}"
fi
exec "$REAL_NEXTFLOW" "$@"
"""


def install_nextflow_shim(shim_dir: Path) -> None:
    real_nextflow = shutil.which("nextflow")
    if real_nextflow is None:
        return
    shim = shim_dir / "nextflow"
    shim.write_text(NEXTFLOW_INSPECT_SHIM)
    shim.chmod(0o755)
    os.environ["REAL_NEXTFLOW"] = real_nextflow
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{os.environ['PATH']}"


def render(nf_core_yml: Path, output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    # nf-core formats the result with prettier through `prek run`, which
    # works on the git repo of the current directory. Sync runs inside the
    # pipeline repo, so the template's own .prettierignore applies there.
    # The RO-Crate step also reads git history, so seed one empty commit.
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=master", str(output)],
        check=True,
    )
    os.chdir(output)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=nf-migrate",
            "-c",
            "user.email=nf-migrate@localhost",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "render",
        ],
        check=True,
    )

    config = yaml.safe_load(nf_core_yml.read_text())
    config["template"]["force"] = True
    config["template"]["outdir"] = "."
    (output / ".nf-core.yml").write_text(yaml.safe_dump(config))

    logging.getLogger("nf_core.pipelines.create").setLevel(logging.ERROR)
    pipeline_create = nf_core.pipelines.create.create.PipelineCreate(
        outdir=str(output),
        from_config_file=True,
        no_git=True,
        force=True,
        default_branch="master",
    )
    pipeline_create.init_pipeline()

    # Same post-processing as sync: record the version, reset force.
    config["template"]["force"] = False
    config["nf_core_version"] = nf_core.__version__
    (output / ".nf-core.yml").write_text(
        yaml.dump(config, Dumper=PrettierDumper, sort_keys=False)
    )


if __name__ == "__main__":
    # nf-core caches `nextflow config` output under $NXF_HOME/nf-core, keyed
    # only by file hashes, and the cache format differs between releases.
    # A per-run NXF_HOME stops one release reading another release's cache.
    # Nextflow's own downloads (framework jars, plugins) are shared through
    # symlinks so a per-run home does not re-download them.
    real_nxf_home = Path(os.environ.get("NXF_HOME", Path.home() / ".nextflow"))
    with tempfile.TemporaryDirectory() as nxf_home:
        for shared in ("framework", "plugins", "capsule"):
            if (real_nxf_home / shared).is_dir():
                (Path(nxf_home) / shared).symlink_to(real_nxf_home / shared)
        os.environ["NXF_HOME"] = nxf_home
        shim_dir = Path(nxf_home) / "bin"
        shim_dir.mkdir()
        install_nextflow_shim(shim_dir)
        render(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
