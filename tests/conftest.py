from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_site(root: Path, name: str, toml: str = "") -> Path:
    site = root / "sites" / name
    site.mkdir(parents=True)
    (site / "Dockerfile").write_text("FROM scratch\n")
    (site / "site.toml").write_text(toml)
    return site


@pytest.fixture
def project_root(tmp_path, monkeypatch) -> Path:
    """A minimal project with two sites; MINTERNET_ROOT points at it."""
    (tmp_path / "minternet.toml").write_text('prefix = "mini"\n')
    write_site(tmp_path, "alpha", 'title = "Alpha"\ndescription = "First"\n')
    write_site(tmp_path, "beta-site", 'vm = "custom-vm"\npublic = false\nport = 8080\n[env]\nFOO = "bar"\n')
    monkeypatch.setenv("MINTERNET_ROOT", str(tmp_path))
    return tmp_path
