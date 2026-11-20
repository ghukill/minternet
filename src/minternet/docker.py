"""Docker commands shared by the local and exe.dev targets.

Both targets build and run a site's container the same way; they differ only
in where the commands execute and how the container is reached.
"""

from __future__ import annotations

import time

import click

from .config import Site
from .runner import CommandError, Shell

LABEL_PROJECT = "minternet.project"
LABEL_SITE = "minternet.site"

_STATE_FORMAT = "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"


def build(shell: Shell, site: Site, context: str) -> None:
    shell.run(["docker", "build", "-t", site.image, context])


def replace_container(
    shell: Shell,
    site: Site,
    *,
    prefix: str,
    env: dict[str, str],
    network: str | None = None,
    publish: str | None = None,
) -> None:
    """Remove any existing container for the site and start a fresh one."""
    shell.run(["docker", "rm", "-f", site.container], check=False)
    cmd = [
        "docker", "run", "-d",
        "--name", site.container,
        "--restart", "unless-stopped",
        "--label", f"{LABEL_PROJECT}={prefix}",
        "--label", f"{LABEL_SITE}={site.name}",
    ]
    if network:
        cmd += ["--network", network]
    if publish:
        cmd += ["-p", publish]
    for key, value in env.items():
        cmd += ["-e", f"{key}={value}"]
    cmd.append(site.image)
    shell.run(cmd)


def container_state(shell: Shell, container: str) -> tuple[str, str] | None:
    """Return (status, health) for a container, or None if it doesn't exist."""
    result = shell.query(["docker", "inspect", "-f", _STATE_FORMAT, container], check=False)
    if result.returncode != 0:
        return None
    status, _, health = result.stdout.strip().partition(" ")
    return status, health


def wait_healthy(shell: Shell, site: Site, timeout: float = 90, interval: float = 2) -> None:
    """Block until the container's HEALTHCHECK passes (or it has none)."""
    if shell.runner.dry_run:
        return
    click.echo(f"Waiting for {site.container} to become healthy...")
    deadline = time.monotonic() + timeout
    state = None
    while time.monotonic() < deadline:
        state = container_state(shell, site.container)
        if state is None:
            raise CommandError(f"Container {site.container} disappeared.")
        status, health = state
        if status in {"exited", "dead"}:
            break
        if health in {"healthy", "none"}:
            click.echo(f"{site.container} is {'healthy' if health == 'healthy' else 'running'}.")
            return
        time.sleep(interval)
    logs = shell.query(["docker", "logs", "--tail", "30", site.container], check=False)
    raise CommandError(
        f"{site.container} did not become healthy (state: {state}).\n"
        f"Last log lines:\n{logs.stdout}{logs.stderr}"
    )
