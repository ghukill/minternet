"""Read-only /etc/hosts checks. The CLI never edits /etc/hosts."""

from __future__ import annotations

from pathlib import Path

from .config import Project, Site

HOSTS_FILE = Path("/etc/hosts")
LOOPBACK = {"127.0.0.1", "::1"}


def loopback_names(hosts_file: Path = HOSTS_FILE) -> set[str]:
    names: set[str] = set()
    try:
        text = hosts_file.read_text()
    except OSError:
        return names
    for line in text.splitlines():
        fields = line.split("#", 1)[0].split()
        if len(fields) >= 2 and fields[0] in LOOPBACK:
            names.update(fields[1:])
    return names


def missing_hosts(project: Project, sites: list[Site], hosts_file: Path = HOSTS_FILE) -> list[str]:
    present = loopback_names(hosts_file)
    wanted = [s.local_host(project.settings) for s in sites]
    return [h for h in wanted if h not in present]
