"""minternet: build, run and deploy a tiny internet of test websites."""

from __future__ import annotations

import functools

import click

from .config import TARGETS, ConfigError, Project, load_project
from .exe import ExeTarget
from .hosts import missing_hosts
from .local import LocalTarget
from .runner import Runner
from .scaffold import KINDS, create_site


def _project() -> Project:
    try:
        return load_project()
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc


def _target(name: str, dry_run: bool = False):
    project = _project()
    runner = Runner(dry_run=dry_run)
    cls = LocalTarget if name == "local" else ExeTarget
    return project, cls(project, runner)


def _select(project: Project, names: tuple[str, ...]):
    try:
        return project.select(names)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc


def target_option(func):
    return click.option(
        "--target", "-t",
        type=click.Choice(TARGETS),
        default="local",
        show_default=True,
        help="Where to act: local docker, or exe.dev VMs.",
    )(func)


def dry_run_option(func):
    return click.option("--dry-run", is_flag=True, help="Print commands that change things instead of running them.")(func)


def sites_argument(func):
    return click.argument("sites", nargs=-1)(func)


def _table(rows: list[dict[str, str]]) -> None:
    if not rows:
        click.echo("No sites.")
        return
    headers = list(rows[0].keys())
    widths = {h: max(len(h), *(len(str(r[h])) for r in rows)) for h in headers}
    click.echo("  ".join(h.ljust(widths[h]) for h in headers).rstrip())
    click.echo("  ".join("-" * widths[h] for h in headers))
    for row in rows:
        click.echo("  ".join(str(row[h]).ljust(widths[h]) for h in headers).rstrip())


def _handle_config_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConfigError as exc:
            raise click.ClickException(str(exc)) from exc

    return wrapper


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Build, run and deploy the minternet sites.

    Sites live in sites/<name>/ (a Dockerfile plus site.toml). Commands that
    take SITES act on every site when none are given.
    """


@main.command("list")
def list_sites() -> None:
    """List sites and their local and exe.dev URLs."""
    project = _project()
    s = project.settings
    _table(
        [
            {
                "site": site.name,
                "title": site.title,
                "local": site.url(s, "local"),
                "exe.dev": site.url(s, "exe") + ("" if site.public else " (private)"),
            }
            for site in project.sites
        ]
    )


@main.command()
@sites_argument
@target_option
@dry_run_option
def deploy(sites: tuple[str, ...], target: str, dry_run: bool) -> None:
    """Build and (re)start SITES.

    \b
    local: build images and run containers behind a proxy at http://<site>.test
    exe:   create the VM if missing, sync, build, run, and configure the
           exe.dev HTTPS proxy. Safe to re-run; existing VMs are updated in place.
    """
    project, t = _target(target, dry_run)
    t.deploy(_select(project, sites))


@main.command()
@sites_argument
@target_option
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@dry_run_option
def remove(sites: tuple[str, ...], target: str, yes: bool, dry_run: bool) -> None:
    """Stop SITES locally, or DELETE their exe.dev VMs.

    SITES is required here; pass 'all' to act on every site.
    """
    if not sites:
        raise click.UsageError("Name the site(s) to remove, or 'all'.")
    project, t = _target(target, dry_run)
    selected = _select(project, sites)
    names = ", ".join(s.name for s in selected)
    if not yes and not dry_run:
        if target == "local":
            click.confirm(f"Remove local container(s): {names}?", abort=True)
        else:
            vms = ", ".join(s.vm for s in selected)
            click.confirm(f"Permanently delete exe.dev VM(s): {vms}?", abort=True)
    t.remove(selected)


@main.command()
@sites_argument
@target_option
def status(sites: tuple[str, ...], target: str) -> None:
    """Show container/VM state and an HTTP health probe for SITES."""
    project, t = _target(target)
    _table(t.status(_select(project, sites)))


@main.command()
@click.argument("site")
@target_option
@click.option("--follow", "-f", is_flag=True, help="Follow log output.")
def logs(site: str, target: str, follow: bool) -> None:
    """Show a site's container logs."""
    project, t = _target(target)
    t.logs(_select(project, (site,))[0], follow)


@main.command(context_settings={"ignore_unknown_options": True})
@click.argument("site")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def ssh(site: str, command: tuple[str, ...]) -> None:
    """Open a shell on a site's exe.dev VM, or run COMMAND there."""
    project, t = _target("exe")
    t.ssh(_select(project, (site,))[0], command)


@main.command()
def hosts() -> None:
    """Check /etc/hosts for local site hostnames (never edits it)."""
    project = _project()
    missing = missing_hosts(project, project.sites)
    for site in project.sites:
        host = site.local_host(project.settings)
        mark = click.style("missing", fg="yellow") if host in missing else click.style("ok", fg="green")
        click.echo(f"  {host:<30} {mark}")
    if not missing:
        click.echo("\nAll site hostnames resolve to 127.0.0.1.")
        return
    click.echo("\nAdd these lines to /etc/hosts (e.g. `sudo nano /etc/hosts`):\n")
    for host in missing:
        click.echo(f"127.0.0.1 {host}")
    click.echo(
        "\nWithout /etc/hosts entries you can still use Host headers, e.g.\n"
        f"  curl -H 'Host: {missing[0]}' http://127.0.0.1/"
    )


@main.command()
@click.argument("name")
@click.option("--kind", "-k", type=click.Choice(KINDS), default="flask", show_default=True,
              help="Starting template.")
@click.option("--title", help="Human-readable title (default: from NAME).")
@click.option("--description", default="", help="One-line description, shown on the hub page.")
@_handle_config_errors
def new(name: str, kind: str, title: str | None, description: str) -> None:
    """Scaffold a new site in sites/NAME."""
    project = _project()
    dest = create_site(project, name, kind, title or name.replace("-", " ").title(), description)
    click.echo(f"Created {dest.relative_to(project.root)}/")
    click.echo("Next:")
    click.echo(f"  minternet deploy {name}            # run locally at http://{name}.{project.settings.local_tld}")
    click.echo(f"  minternet deploy {name} -t exe     # create VM and deploy to exe.dev")
