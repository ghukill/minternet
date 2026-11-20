"""Command execution with echo and dry-run support."""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable, Sequence

import click

# exe.dev VMs fail OpenSSH's host-key rotation check (UpdateHostKeys), which
# prints a warning on every connection; skip that check. Doesn't affect normal
# host key verification.
SSH_OPTS = ["-o", "UpdateHostKeys=no"]


class CommandError(click.ClickException):
    pass


class Runner:
    """Runs commands locally, printing them first.

    - ``run`` is for commands that change things; skipped under dry-run.
    - ``query`` is for read-only commands whose output drives decisions; these
      run even under dry-run so the printed plan reflects reality.
    """

    def __init__(self, dry_run: bool = False, echo: Callable[[str], None] = click.echo):
        self.dry_run = dry_run
        self.echo = echo

    @staticmethod
    def display(cmd: Sequence[str]) -> str:
        return shlex.join(cmd)

    def run(self, cmd: Sequence[str], *, check: bool = True) -> int:
        self.echo(f"$ {self.display(cmd)}")
        if self.dry_run:
            return 0
        result = subprocess.run(list(cmd))
        if check and result.returncode != 0:
            raise CommandError(f"Command failed (exit {result.returncode}): {self.display(cmd)}")
        return result.returncode

    def query(self, cmd: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(list(cmd), capture_output=True, text=True)
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise CommandError(f"Command failed: {self.display(cmd)}\n{detail}")
        return result


class Shell:
    """Where docker commands execute: this machine, or a VM over ssh."""

    def __init__(self, runner: Runner, host: str | None = None):
        self.runner = runner
        self.host = host

    def wrap(self, cmd: Sequence[str]) -> list[str]:
        if self.host is None:
            return list(cmd)
        return ["ssh", *SSH_OPTS, self.host, shlex.join(cmd)]

    def run(self, cmd: Sequence[str], *, check: bool = True) -> int:
        return self.runner.run(self.wrap(cmd), check=check)

    def query(self, cmd: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.runner.query(self.wrap(cmd), check=check)
