from __future__ import annotations

import os
import shlex
import socket
import subprocess
import time
from pathlib import Path

import click

from .config import DomainConfig, domain_map, load_all_domains


@click.group()
def main() -> None:
    """Minternet CLI."""


@main.command("list")
def list_domains() -> None:
    """List available domains and deploy metadata."""
    domains = load_all_domains()
    if not domains:
        click.echo("No domains found.")
        return
    rows = [
        ("name", "domain", "service_port", "image"),
        *[
            (
                domain.name,
                domain.domain,
                str(domain.service_port),
                domain.image,
            )
            for domain in domains
        ],
    ]
    col_widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for idx, row in enumerate(rows):
        line = "  ".join(text.ljust(col_widths[i]) for i, text in enumerate(row))
        click.echo(line)
        if idx == 0:
            click.echo("  ".join("-" * width for width in col_widths))


def _resolve_domain(name: str):
    """Resolve a domain config by short name, raising on unknown entries."""
    domains = load_all_domains()
    domains_by_name = domain_map(domains)
    domain = domains_by_name.get(name)
    if not domain:
        available = ", ".join(sorted(domains_by_name.keys()))
        message = f"Unknown domain '{name}'."
        if available:
            message += f" Available: {available}"
        raise click.ClickException(message)
    return domain


def _run(cmd: list[str], dry_run: bool) -> None:
    """Run a command locally, printing it first and honoring dry-run."""
    # Simple display: quote args with spaces, leave others as-is
    display = " ".join(f"'{a}'" if " " in a else a for a in cmd)
    click.echo(f"$ {display}")
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def _ssh(host: str, command: str | list[str], dry_run: bool) -> None:
    """Run a command on the target host via ssh."""
    if isinstance(command, list):
        command = shlex.join(command)
    cmd = [
        "ssh",
        host,
        command,
    ]
    _run(cmd, dry_run)


def _rsync(source: str, destination: str, dry_run: bool) -> None:
    """Sync files to the VM, skipping common local artifacts."""
    cmd = [
        "rsync",
        "-az",
        "-e",
        "ssh",
        "--exclude",
        "__pycache__",
        "--exclude",
        ".venv",
        source,
        destination,
    ]
    _run(cmd, dry_run)


def _vm_host(vm_name: str) -> str:
    return f"{vm_name}.exe.xyz"


def _wait_for_dns(hostname: str, timeout: int = 300, interval: int = 10) -> None:
    """Wait for DNS to resolve a hostname."""
    click.echo(f"Waiting for DNS ({hostname})...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            socket.gethostbyname(hostname)
            click.echo("DNS ready.")
            return
        except socket.gaierror:
            time.sleep(interval)
    raise click.ClickException(f"Timed out waiting for DNS: {hostname}")


def _repo_root() -> Path:
    """Find the repository root (directory containing domains/)."""
    candidates: list[Path] = []
    env_root = os.getenv("MINTERNET_ROOT")
    if env_root:
        candidates.append(Path(env_root))
    candidates.append(Path.cwd())
    candidates.append(Path(__file__).resolve().parents[2])
    for candidate in candidates:
        if (candidate / "domains").exists():
            return candidate
    return candidates[-1]


def _compose_file() -> Path:
    """Return path to docker-compose.yml."""
    return _repo_root() / "domains" / "docker-compose.yml"


def _write_env_file(domain: DomainConfig) -> None:
    """Write local_env to .env.local in domain directory."""
    env_path = domain.path.parent / ".env.local"
    lines = [f"{k}={v}" for k, v in domain.local_env.items()]
    env_path.write_text("\n".join(lines) + "\n" if lines else "")


def _run_hooks(domain: DomainConfig, hook_name: str, strategy: str, dry_run: bool) -> None:
    """Execute hooks, passing MINTERNET_STRATEGY env var."""
    hook_cmd = getattr(domain.hooks, hook_name, None)
    if not hook_cmd:
        return
    click.echo(f"Running {hook_name} hook for {domain.name}...")
    if dry_run:
        click.echo(f"  Would run: {hook_cmd}")
        return
    env = os.environ.copy()
    env["MINTERNET_STRATEGY"] = strategy
    subprocess.run(
        ["sh", "-c", hook_cmd],
        cwd=domain.path.parent,
        env=env,
        check=True,
    )


def _ensure_proxy_running(dry_run: bool) -> None:
    """Start proxy service if not running."""
    compose_file = _compose_file()
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "-q", "proxy"],
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        click.echo("Starting proxy service...")
        cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d", "--no-deps", "proxy"]
        _run(cmd, dry_run)


def _deploy_local(domain: DomainConfig, dry_run: bool) -> None:
    """Deploy a domain using local Docker Compose."""
    if domain.name == "proxy":
        raise click.ClickException(
            "Proxy is infrastructure, not a deployable domain. "
            "It will be started automatically."
        )

    compose_file = _compose_file()

    click.echo(f"Deploying {domain.name} locally")

    # Run pre-build hook
    _run_hooks(domain, "pre_build", "local", dry_run)

    # Write environment file
    click.echo(f"Writing .env.local for {domain.name}")
    if not dry_run:
        _write_env_file(domain)

    # Ensure proxy is running
    _ensure_proxy_running(dry_run)

    # Build and start the service
    cmd = [
        "docker", "compose",
        "-f", str(compose_file),
        "up", "-d", "--build",
        domain.name,
    ]
    _run(cmd, dry_run)

    # Build URL from local_env config
    scheme = domain.local_env.get("PUBLIC_SCHEME", "http")
    host = domain.local_env.get("PUBLIC_HOST", f"{domain.name}.test")
    click.echo(f"Done. {scheme}://{host}")


def _get_running_domains(compose_file: Path) -> set[str]:
    """Get the set of running domain containers (excluding proxy)."""
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "ps", "--format", "{{.Service}}"],
        capture_output=True,
        text=True,
    )
    services = set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()
    services.discard("proxy")
    return services


def _delete_local(domain: DomainConfig, dry_run: bool) -> None:
    """Stop and remove a domain container locally."""
    compose_file = _compose_file()
    click.echo(f"Stopping {domain.name} locally")
    cmd = [
        "docker", "compose",
        "-f", str(compose_file),
        "rm", "-sf",
        domain.name,
    ]
    _run(cmd, dry_run)

    # Check if any domains are still running; if not, stop proxy too
    if not dry_run:
        running = _get_running_domains(compose_file)
        running.discard(domain.name)  # Exclude the one we just stopped
        if not running:
            click.echo("No domains running, stopping proxy...")
            proxy_cmd = [
                "docker", "compose",
                "-f", str(compose_file),
                "rm", "-sf",
                "proxy",
            ]
            _run(proxy_cmd, dry_run)


def _deploy_one(domain: DomainConfig, skip_create: bool, dry_run: bool) -> None:
    """Deploy a single domain to exe.dev."""
    vm_host = _vm_host(domain.domain)
    remote_dir = f"~/minternet/{domain.name}"

    click.echo(f"Deploying {domain.name} -> {domain.domain}")

    # Run pre-build hook locally before rsync
    _run_hooks(domain, "pre_build", "exe.dev", dry_run)

    if not skip_create:
        _ssh("exe.dev", ["new", f"--name={domain.domain}"], dry_run)
        if not dry_run:
            _wait_for_dns(vm_host)

    _ssh(vm_host, f"mkdir -p {remote_dir}", dry_run)

    _rsync(f"{domain.path.parent}/", f"{vm_host}:minternet/{domain.name}/", dry_run)

    _ssh(vm_host, f"cd {remote_dir} && docker build -t {domain.image} .", dry_run)

    env_flags = " ".join(f"-e {k}={shlex.quote(v)}" for k, v in domain.env.items())
    run_cmd = (
        f"docker rm -f {domain.name} 2>/dev/null || true && "
        f"docker run -d --name {domain.name} --restart unless-stopped "
        f"-p {domain.service_port}:80 {env_flags} {domain.image}"
    )
    _ssh(vm_host, run_cmd, dry_run)

    _ssh("exe.dev", ["share", "port", domain.domain, str(domain.service_port)], dry_run)
    if domain.public:
        _ssh("exe.dev", ["share", "set-public", domain.domain], dry_run)

    # Build URL from env config
    scheme = domain.env.get("PUBLIC_SCHEME", "https")
    host = domain.env.get("PUBLIC_HOST", f"{domain.domain}.exe.xyz")
    click.echo(f"Done. {scheme}://{host}")


def _expand_domains(names: tuple[str, ...]) -> list[str]:
    """Expand 'all' to all domain names, otherwise return as-is."""
    if len(names) == 1 and names[0].lower() == "all":
        return [d.name for d in load_all_domains()]
    return list(names)


@main.command("deploy")
@click.option("--domain", "-d", "domains", multiple=True, required=True, help="Domain(s) to deploy, or 'all'.")
@click.option("--strategy", "-s", required=True, type=click.Choice(["local", "exe.dev"]), help="Deployment strategy.")
@click.option("--skip-create", is_flag=True, help="Skip VM creation (exe.dev only).")
@click.option("--dry-run", is_flag=True, help="Print commands without running.")
def deploy(domains: tuple[str, ...], strategy: str, skip_create: bool, dry_run: bool) -> None:
    """Deploy domain(s) using the specified strategy."""
    for name in _expand_domains(domains):
        domain = _resolve_domain(name)
        if strategy == "local":
            _deploy_local(domain, dry_run)
        else:
            _deploy_one(domain, skip_create, dry_run)


@main.command("delete")
@click.option("--domain", "-d", "domains", multiple=True, required=True, help="Domain(s) to delete, or 'all'.")
@click.option("--strategy", "-s", required=True, type=click.Choice(["local", "exe.dev"]), help="Deployment strategy.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("--dry-run", is_flag=True, help="Print commands without running.")
def delete(domains: tuple[str, ...], strategy: str, yes: bool, dry_run: bool) -> None:
    """Delete domain(s) using the specified strategy."""
    resolved = [_resolve_domain(name) for name in _expand_domains(domains)]
    if not yes:
        names = ", ".join(d.name for d in resolved)
        if strategy == "local":
            click.confirm(f"Stop container(s) {names}?", abort=True)
        else:
            click.confirm(f"Delete VM(s) {names}? This cannot be undone.", abort=True)
    for domain in resolved:
        if strategy == "local":
            _delete_local(domain, dry_run)
        else:
            _ssh("exe.dev", ["rm", domain.domain], dry_run)


@main.command("status")
@click.argument("name")
@click.option("--dry-run", is_flag=True, help="Print commands without running.")
def status_domain(name: str, dry_run: bool) -> None:
    """Show exe.dev status for a domain."""
    domain = _resolve_domain(name)
    vm_host = _vm_host(domain.domain)
    click.echo(f"Status {domain.name} -> {domain.domain}")
    _ssh(vm_host, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", dry_run)
    _ssh(vm_host, f"curl -sf http://localhost:{domain.service_port}/healthz", dry_run)


@main.command("logs")
@click.argument("name")
@click.option("--dry-run", is_flag=True, help="Print commands without running.")
def logs_domain(name: str, dry_run: bool) -> None:
    """Tail logs for a domain."""
    domain = _resolve_domain(name)
    vm_host = _vm_host(domain.domain)
    click.echo(f"Logs {domain.name} -> {domain.domain}")
    _ssh(vm_host, f"docker logs -f {domain.name}", dry_run)


@main.command("ssh")
@click.argument("name")
@click.argument("args", nargs=-1)
@click.option("--dry-run", is_flag=True, help="Print commands without running.")
def ssh_domain(name: str, args: tuple[str, ...], dry_run: bool) -> None:
    """Open an SSH session or run a command on a domain VM."""
    domain = _resolve_domain(name)
    vm_host = _vm_host(domain.domain)
    if args:
        _ssh(vm_host, list(args), dry_run)
        return
    # Interactive SSH session (no command)
    _run(["ssh", vm_host], dry_run)
