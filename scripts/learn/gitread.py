"""Read files straight from git objects, and a Workspace on top of that."""

import subprocess
from pathlib import Path

import yaml

from nf_migrate.operations import Workspace
from nf_migrate.variables import manifest_variables, template_variables


class GitReader:
    """`git cat-file --batch` kept open, with a cache."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.process = subprocess.Popen(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        self.cache: dict[tuple[str, str], str | None] = {}

    def read(self, ref: str, path: str) -> str | None:
        key = (ref, path)
        if key in self.cache:
            return self.cache[key]
        self.process.stdin.write(f"{ref}:{path}\n".encode())
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode()
        parts = header.split()
        if len(parts) != 3:
            self.cache[key] = None
            return None
        _, kind, size = parts
        data = self.process.stdout.read(int(size))
        self.process.stdout.read(1)
        if kind != "blob":
            content = None
        else:
            content = data.decode("utf-8", errors="surrogateescape")
        self.cache[key] = content
        return content

    def close(self) -> None:
        self.process.stdin.close()
        self.process.wait()


class GitWorkspace(Workspace):
    def __init__(
        self, reader: GitReader, ref: str, variables: dict[str, str]
    ) -> None:
        super().__init__(reader.repo, variables)
        self.reader = reader
        self.ref = ref

    def _read_from_disk(self, path: str) -> str | None:
        return self.reader.read(self.ref, path)


def variables_at(reader: GitReader, ref: str) -> dict[str, str]:
    variables: dict[str, str] = {}
    nextflow_config = reader.read(ref, "nextflow.config")
    if nextflow_config:
        variables = manifest_variables(nextflow_config)
    nf_core_yml = reader.read(ref, ".nf-core.yml")
    if nf_core_yml:
        try:
            variables.update(template_variables(nf_core_yml))
        except (yaml.YAMLError, AttributeError):
            pass
    return variables
