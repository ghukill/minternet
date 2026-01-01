from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import os


@dataclass(frozen=True)
class HooksConfig:
    pre_build: str | None = None


@dataclass(frozen=True)
class DomainConfig:
    name: str
    domain: str
    service_port: int
    image: str
    container_port: int
    public: bool
    env: dict[str, str]
    local_env: dict[str, str]
    hooks: HooksConfig
    path: Path


def _repo_root() -> Path:
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


def load_domain_config(path: Path) -> DomainConfig:
    data = json.loads(path.read_text())
    hooks_data = data.get("hooks", {})
    return DomainConfig(
        name=data["name"],
        domain=data["domain"],
        service_port=int(data["service_port"]),
        image=data["image"],
        container_port=int(data["container_port"]),
        public=bool(data.get("public", True)),
        env=dict(data.get("env", {})),
        local_env=dict(data.get("local_env", {})),
        hooks=HooksConfig(
            pre_build=hooks_data.get("pre_build"),
        ),
        path=path,
    )


def load_all_domains(root: Path | None = None) -> list[DomainConfig]:
    base = root or _repo_root()
    domain_dir = base / "domains"
    configs: list[DomainConfig] = []
    for cfg_path in sorted(domain_dir.glob("*/domain.json")):
        configs.append(load_domain_config(cfg_path))
    return configs


def domain_map(domains: list[DomainConfig]) -> dict[str, DomainConfig]:
    return {domain.name: domain for domain in domains}
