import json

import pytest

from minternet.config import ConfigError, load_project
from tests.conftest import REPO_ROOT, write_site


def test_derived_names_and_urls(project_root):
    project = load_project()
    alpha = project.site("alpha")
    assert alpha.vm == "mini-alpha"
    assert alpha.image == "mini/alpha"
    assert alpha.container == "alpha"
    assert alpha.url(project.settings, "local") == "http://alpha.test"
    assert alpha.url(project.settings, "exe") == "https://mini-alpha.exe.xyz"


def test_site_overrides(project_root):
    beta = load_project().site("beta-site")
    assert beta.vm == "custom-vm"
    assert beta.public is False
    assert beta.port == 8080
    assert beta.title == "Beta-Site"


def test_non_default_local_port_appears_in_url(project_root):
    (project_root / "minternet.toml").write_text('prefix = "mini"\n[local]\nhttp_port = 8080\n')
    project = load_project()
    assert project.site("alpha").url(project.settings, "local") == "http://alpha.test:8080"


def test_runtime_env(project_root):
    project = load_project()
    env = project.runtime_env(project.site("beta-site"), "exe")
    assert env["PUBLIC_URL"] == "https://custom-vm.exe.xyz"
    assert env["SITE_URL_ALPHA"] == "https://mini-alpha.exe.xyz"
    assert env["SITE_URL_BETA_SITE"] == "https://custom-vm.exe.xyz"
    assert env["MINTERNET_SITE"] == "beta-site"
    assert env["MINTERNET_TARGET"] == "exe"
    assert env["FOO"] == "bar"
    sites = json.loads(env["MINTERNET_SITES"])
    assert [s["name"] for s in sites] == ["alpha", "beta-site"]
    assert sites[0]["description"] == "First"


def test_select(project_root):
    project = load_project()
    assert [s.name for s in project.select(())] == ["alpha", "beta-site"]
    assert [s.name for s in project.select(("all",))] == ["alpha", "beta-site"]
    assert [s.name for s in project.select(("beta-site",))] == ["beta-site"]
    with pytest.raises(ConfigError, match="Unknown site"):
        project.select(("nope",))


@pytest.mark.parametrize("name", ["Bad", "proxy", "-x", "a_b"])
def test_invalid_site_names(project_root, name):
    write_site(project_root, name)
    with pytest.raises(ConfigError):
        load_project()


def test_duplicate_vm_names_rejected(project_root):
    write_site(project_root, "gamma", 'vm = "custom-vm"\n')
    with pytest.raises(ConfigError, match="Duplicate VM"):
        load_project()


def test_missing_dockerfile_rejected(project_root):
    write_site(project_root, "gamma")
    (project_root / "sites" / "gamma" / "Dockerfile").unlink()
    with pytest.raises(ConfigError, match="Dockerfile"):
        load_project()


def test_repo_sites_load():
    """The real repo config is valid and keeps the existing exe.dev VM names."""
    project = load_project(REPO_ROOT)
    vms = {s.name: s.vm for s in project.sites}
    assert vms["minternet"] == "minternet"
    assert vms["blogs"] == "minternet-blogs"
    assert project.site("minternet").listed is False
