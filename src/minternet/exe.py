"""exe.dev target: one VM per site, one container per VM.

Deploys are idempotent: a missing VM is created, an existing one is updated in
place (rsync, rebuild, replace container, re-apply proxy settings).
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request

import click

from . import docker
from .config import Project, Site
from .runner import SSH_OPTS, CommandError, Runner, Shell

EXE_HOST = "exe.dev"
# Build context location on each VM, relative to the login user's home.
REMOTE_DIR = "minternet"
RSYNC_EXCLUDES = ["__pycache__", "*.pyc", ".venv", ".env*", ".DS_Store"]


class ExeTarget:
    name = "exe"

    def __init__(self, project: Project, runner: Runner):
        self.project = project
        self.runner = runner
        self.settings = project.settings

    def vm_shell(self, site: Site) -> Shell:
        return Shell(self.runner, site.vm_host(self.settings))

    # -- exe.dev API -------------------------------------------------------
    def _exe(self, *args: str, check: bool = True) -> int:
        # exe.dev's ssh CLI takes plain words; join without extra quoting.
        return self.runner.run(["ssh", *SSH_OPTS, EXE_HOST, " ".join(args)], check=check)

    def list_vms(self) -> dict[str, dict]:
        result = self.runner.query(["ssh", *SSH_OPTS, EXE_HOST, "ls --json"])
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Unexpected output from `ssh exe.dev ls --json`: {exc}") from exc
        return {vm["vm_name"]: vm for vm in data.get("vms", [])}

    # -- deploy ------------------------------------------------------------
    def deploy(self, sites: list[Site]) -> None:
        vms = self.list_vms()
        created = []
        for site in sites:
            click.secho(f"==> {site.name} -> {site.vm} (exe.dev)", bold=True)
            if site.vm not in vms:
                self._create_vm(site)
                created.append(site)
            self._deploy_site(site)
            click.echo(f"Done. {site.url(self.settings, 'exe')}")
        if created and len(sites) < len(self.project.sites):
            click.echo()
            click.secho(
                "New VM(s) created. Sites that link to other sites (e.g. the hub) learn "
                "about new ones only when redeployed: `minternet deploy -t exe`.",
                fg="yellow",
            )

    def _create_vm(self, site: Site) -> None:
        self._exe("new", f"--name={site.vm}")
        if self.runner.dry_run:
            return
        host = site.vm_host(self.settings)
        self._wait(lambda: _resolves(host), f"DNS for {host}")
        probe = ["ssh", *SSH_OPTS, "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                 "-o", "StrictHostKeyChecking=accept-new", host, "true"]
        self._wait(lambda: self.runner.query(probe, check=False).returncode == 0, f"ssh to {host}")

    def _deploy_site(self, site: Site) -> None:
        vm = self.vm_shell(site)
        host = site.vm_host(self.settings)
        remote_path = f"{REMOTE_DIR}/{site.name}"

        vm.run(["mkdir", "-p", remote_path])
        excludes = [arg for pattern in RSYNC_EXCLUDES for arg in ("--exclude", pattern)]
        self.runner.run(
            ["rsync", "-az", "--delete", *excludes, "-e", " ".join(["ssh", *SSH_OPTS]),
             f"{site.path}/", f"{host}:{remote_path}/"]
        )
        docker.build(vm, site, remote_path)
        docker.replace_container(
            vm,
            site,
            prefix=self.settings.prefix,
            env=self.project.runtime_env(site, "exe"),
            publish=f"{self.settings.exe_vm_port}:{site.port}",
        )
        docker.wait_healthy(vm, site)
        vm.run(["docker", "image", "prune", "-f"], check=False)

        self._exe("share", "port", site.vm, str(self.settings.exe_vm_port))
        self._exe("share", "set-public" if site.public else "set-private", site.vm)

    def remove(self, sites: list[Site]) -> None:
        for site in sites:
            self._exe("rm", site.vm)

    # -- inspect -----------------------------------------------------------
    def status(self, sites: list[Site]) -> list[dict[str, str]]:
        vms = self.list_vms()
        rows = []
        for site in sites:
            vm = vms.get(site.vm)
            if vm is None:
                rows.append({"site": site.name, "vm": site.vm, "vm_status": "absent",
                             "proxy": "-", "share": "-", "http": "-"})
                continue
            port = vm.get("proxy_port")
            port_ok = port == self.settings.exe_vm_port
            share = vm.get("proxy_share", "?")
            share_ok = (share == "public") == site.public
            rows.append(
                {
                    "site": site.name,
                    "vm": site.vm,
                    "vm_status": vm.get("status", "?"),
                    "proxy": f"{port}" + ("" if port_ok else f" (want {self.settings.exe_vm_port})"),
                    "share": share + ("" if share_ok else f" (want {'public' if site.public else 'private'})"),
                    "http": _probe(f"{site.url(self.settings, 'exe')}/healthz"),
                }
            )
        return rows

    def logs(self, site: Site, follow: bool) -> None:
        cmd = ["docker", "logs", "--tail", "100"]
        if follow:
            cmd.append("-f")
        self.vm_shell(site).run([*cmd, site.container], check=False)

    def ssh(self, site: Site, args: tuple[str, ...]) -> None:
        host = site.vm_host(self.settings)
        if args:
            self.vm_shell(site).run(list(args), check=False)
        else:
            self.runner.run(["ssh", *SSH_OPTS, host], check=False)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _wait(predicate, what: str, timeout: float = 300, interval: float = 5) -> None:
        click.echo(f"Waiting for {what}...")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(interval)
        raise CommandError(f"Timed out waiting for {what}.")


def _resolves(host: str) -> bool:
    try:
        socket.gethostbyname(host)
        return True
    except socket.gaierror:
        return False


def _probe(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return str(response.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except (urllib.error.URLError, OSError) as exc:
        return f"error: {getattr(exc, 'reason', exc)}"
