"""Check that Nextflow can compile a pipeline.

nf-core lint only notices a script that no longer compiles through its
container_configs test, so a migration that leaves a stale `include` is
found late and under a misleading name. `nextflow inspect` parses the
pipeline's scripts the way a run does and fails on a compile error, without
running a process; `nextflow config` does not parse them and passes.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from nf_migrate.migrations import MigrationError

ERROR_LINES_SHOWN = 5


@dataclass(frozen=True, slots=True)
class CompileCheck:
    passed: bool
    error: str = ""

    def render_markdown(self) -> str:
        quoted_error = [f"> {line}" for line in self.error.splitlines()]
        lines = [
            "> [!WARNING]",
            "> Nextflow could not compile the merged pipeline "
            "(`nextflow inspect`):",
            "> ```",
            *quoted_error,
            "> ```",
        ]
        return "\n".join(lines)


def run_compile_check(pipeline: Path) -> CompileCheck:
    """Inspect `pipeline` with Nextflow; a failure is a result, not a raise.

    Nextflow can also fail on a missing network resource, so the caller
    reports a failed check as a warning. A missing `nextflow` command is a
    usage error instead, because no check happened at all.
    """
    command = ["nextflow", "inspect", "-format", "json", str(pipeline)]
    environment = {**os.environ, "NXF_ANSI_LOG": "false"}
    # Nextflow writes .nextflow/ and work/ into its working directory.
    with tempfile.TemporaryDirectory() as working_directory:
        try:
            completed = subprocess.run(
                command,
                cwd=working_directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise MigrationError(
                "--compile-check needs the nextflow command"
            ) from None

    if completed.returncode == 0:
        return CompileCheck(passed=True)
    return CompileCheck(passed=False, error=_first_lines(completed))


def _first_lines(completed: subprocess.CompletedProcess[str]) -> str:
    output = completed.stderr.strip() or completed.stdout.strip()
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[:ERROR_LINES_SHOWN])
