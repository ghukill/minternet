"""Create a new site from a bundled template."""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from .config import NAME_RE, RESERVED_NAMES, SITE_FILE, ConfigError, Project

TEMPLATES_DIR = Path(__file__).parent / "templates"
KINDS = sorted(p.name for p in TEMPLATES_DIR.iterdir() if p.is_dir()) if TEMPLATES_DIR.exists() else []


def create_site(project: Project, name: str, kind: str, title: str, description: str) -> Path:
    if not NAME_RE.match(name):
        raise ConfigError(f"Invalid site name '{name}': use lowercase letters, digits and dashes.")
    if name in RESERVED_NAMES:
        raise ConfigError(f"Site name '{name}' is reserved.")
    template = TEMPLATES_DIR / kind
    if not template.is_dir():
        raise ConfigError(f"Unknown kind '{kind}'. Available: {', '.join(KINDS)}")
    dest = project.sites_dir / name
    if dest.exists():
        raise ConfigError(f"{dest} already exists.")

    shutil.copytree(template, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for path in dest.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text()
        if path.name == SITE_FILE:
            # JSON string literals are valid TOML basic strings.
            text = text.replace('"__TITLE__"', json.dumps(title))
            text = text.replace('"__DESCRIPTION__"', json.dumps(description))
        elif path.suffix in {".html", ".htm"}:
            text = text.replace("__TITLE__", html.escape(title))
            text = text.replace("__DESCRIPTION__", html.escape(description))
        else:
            text = text.replace("__TITLE__", title).replace("__DESCRIPTION__", description)
        path.write_text(text.replace("__NAME__", name))
    return dest
