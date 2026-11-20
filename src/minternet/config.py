"""Project and site configuration.

Everything a deploy needs is derived from two kinds of file:

- ``minternet.toml`` at the repo root: project-wide naming and ports.
- ``sites/<name>/site.toml``: one per site. The directory name is the site name.

Nothing outside ``sites/`` needs editing to add a site.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Target = Literal["local", "exe"]
TARGETS: tuple[Target, ...] = ("local", "exe")

SITE_FILE = "site.toml"
PROJECT_FILE = "minternet.toml"
SITES_DIR = "sites"

# DNS-label safe, and usable as a docker container/network name.
NAME_RE = re.compile(r"^[a-z]([a-z0-9-]{0,40}[a-z0-9])?$")
# Names the CLI uses for its own infrastructure.
RESERVED_NAMES = {"proxy"}


class ConfigError(Exception):
    """Raised for invalid or missing configuration."""


@dataclass(frozen=True)
class Settings:
    prefix: str = "minternet"
    local_tld: str = "test"
    local_http_port: int = 80
    exe_domain: str = "exe.xyz"
    exe_vm_port: int = 8000

    @classmethod
    def from_dict(cls, data: dict) -> Settings:
        local = data.get("local", {})
        exe = data.get("exe", {})
        defaults = cls()
        return cls(
            prefix=str(data.get("prefix", defaults.prefix)),
            local_tld=str(local.get("tld", defaults.local_tld)),
            local_http_port=int(local.get("http_port", defaults.local_http_port)),
            exe_domain=str(exe.get("domain", defaults.exe_domain)),
            exe_vm_port=int(exe.get("vm_port", defaults.exe_vm_port)),
        )


@dataclass(frozen=True)
class Site:
    """A single site: one container locally, one VM on exe.dev."""

    name: str
    path: Path
    title: str
    description: str
    vm: str
    image: str
    port: int = 80
    public: bool = True
    listed: bool = True
    env: dict[str, str] = field(default_factory=dict)

    @property
    def container(self) -> str:
        """Container name, identical locally and on the VM."""
        return self.name

    def vm_host(self, settings: Settings) -> str:
        return f"{self.vm}.{settings.exe_domain}"

    def local_host(self, settings: Settings) -> str:
        return f"{self.name}.{settings.local_tld}"

    def url(self, settings: Settings, target: Target) -> str:
        if target == "local":
            port = settings.local_http_port
            suffix = "" if port == 80 else f":{port}"
            return f"http://{self.local_host(settings)}{suffix}"
        return f"https://{self.vm_host(settings)}"


def _site_env_key(name: str) -> str:
    return "SITE_URL_" + name.upper().replace("-", "_")


@dataclass(frozen=True)
class Project:
    root: Path
    settings: Settings
    sites: list[Site]

    @property
    def sites_dir(self) -> Path:
        return self.root / SITES_DIR

    def site(self, name: str) -> Site:
        for site in self.sites:
            if site.name == name:
                return site
        available = ", ".join(s.name for s in self.sites) or "(none)"
        raise ConfigError(f"Unknown site '{name}'. Available: {available}")

    def select(self, names: tuple[str, ...] | list[str]) -> list[Site]:
        """Resolve site names; no names (or 'all') means every site."""
        if not names or list(names) == ["all"]:
            return list(self.sites)
        return [self.site(n) for n in names]

    def runtime_env(self, site: Site, target: Target) -> dict[str, str]:
        """Environment injected into a site's container.

        - PUBLIC_URL: this site's own base URL (no trailing slash)
        - SITE_URL_<NAME>: base URL of every site, for cross-site links
        - MINTERNET_SITES: JSON list of all sites (used by the hub page)
        - MINTERNET_SITE / MINTERNET_TARGET: who and where am I
        Site-specific [env] values from site.toml are applied last.
        """
        env: dict[str, str] = {
            "MINTERNET_SITE": site.name,
            "MINTERNET_TARGET": target,
            "PUBLIC_URL": site.url(self.settings, target),
        }
        for other in self.sites:
            env[_site_env_key(other.name)] = other.url(self.settings, target)
        env["MINTERNET_SITES"] = json.dumps(
            [
                {
                    "name": s.name,
                    "title": s.title,
                    "description": s.description,
                    "url": s.url(self.settings, target),
                    "listed": s.listed,
                }
                for s in self.sites
            ],
            separators=(",", ":"),
        )
        env.update(site.env)
        return env


def load_site(path: Path, settings: Settings) -> Site:
    name = path.parent.name
    if not NAME_RE.match(name):
        raise ConfigError(
            f"Invalid site name '{name}': use lowercase letters, digits and dashes."
        )
    if name in RESERVED_NAMES:
        raise ConfigError(f"Site name '{name}' is reserved.")
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    if not (path.parent / "Dockerfile").exists():
        raise ConfigError(f"{path.parent} has no Dockerfile.")
    return Site(
        name=name,
        path=path.parent,
        title=str(data.get("title", name.title())),
        description=str(data.get("description", "")),
        vm=str(data.get("vm", f"{settings.prefix}-{name}")),
        image=f"{settings.prefix}/{name}",
        port=int(data.get("port", 80)),
        public=bool(data.get("public", True)),
        listed=bool(data.get("listed", True)),
        env={str(k): str(v) for k, v in data.get("env", {}).items()},
    )


def find_root(start: Path | None = None) -> Path:
    """Locate the project root: $MINTERNET_ROOT, or the nearest parent with minternet.toml."""
    env_root = os.getenv("MINTERNET_ROOT")
    if env_root:
        return Path(env_root).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / PROJECT_FILE).exists():
            return candidate
    raise ConfigError(
        f"Could not find {PROJECT_FILE} in {here} or any parent directory "
        "(or set MINTERNET_ROOT)."
    )


def load_project(root: Path | None = None) -> Project:
    root = root or find_root()
    project_file = root / PROJECT_FILE
    data = tomllib.loads(project_file.read_text()) if project_file.exists() else {}
    settings = Settings.from_dict(data)
    sites = [
        load_site(p, settings) for p in sorted((root / SITES_DIR).glob(f"*/{SITE_FILE}"))
    ]
    vms = [s.vm for s in sites]
    dupes = {v for v in vms if vms.count(v) > 1}
    if dupes:
        raise ConfigError(f"Duplicate VM names: {', '.join(sorted(dupes))}")
    return Project(root=root, settings=settings, sites=sites)
