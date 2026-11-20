import json
import subprocess

import pytest
from click.testing import CliRunner

from minternet import exe
from minternet.cli import main
from minternet.config import load_project
from minternet.hosts import loopback_names
from minternet.local import LocalTarget
from minternet.runner import Runner


@pytest.fixture
def cli():
    return CliRunner()


@pytest.fixture
def fake_subprocess(monkeypatch):
    """Record every subprocess call; read-only queries get canned answers."""
    calls: list[list[str]] = []
    vms = {"vms": [{"vm_name": "mini-alpha", "status": "running", "proxy_port": 8000, "proxy_share": "public"}]}

    def fake_run(cmd, capture_output=False, text=False, **kwargs):
        calls.append(cmd)
        stdout = json.dumps(vms) if cmd[-1] == "ls --json" else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_list(cli, project_root):
    result = cli.invoke(main, ["list"])
    assert result.exit_code == 0, result.output
    assert "http://alpha.test" in result.output
    assert "https://custom-vm.exe.xyz (private)" in result.output


def test_local_dry_run(cli, project_root, fake_subprocess):
    result = cli.invoke(main, ["deploy", "alpha", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "$ docker build -t mini/alpha" in result.output
    assert "--network mini" in result.output
    assert "-e PUBLIC_URL=http://alpha.test" in result.output
    assert "-p 80:80" in result.output  # the proxy
    # dry-run only runs read-only queries
    assert all(c[:2] in (["docker", "network"], ["docker", "inspect"]) for c in fake_subprocess)
    assert not (project_root / ".minternet").exists()


def test_exe_dry_run_existing_and_new_vm(cli, project_root, fake_subprocess):
    result = cli.invoke(main, ["deploy", "-t", "exe", "--dry-run"])
    assert result.exit_code == 0, result.output
    out = result.output
    # alpha exists: no create. beta-site is missing: create it.
    assert "new --name=mini-alpha" not in out
    assert "'new --name=custom-vm'" in out
    assert "rsync -az --delete" in out
    assert "docker build -t mini/alpha minternet/alpha" in out
    assert "-p 8000:80" in out
    assert "-p 8000:8080" in out
    assert "'share port mini-alpha 8000'" in out
    assert "'share set-public mini-alpha'" in out
    assert "'share set-private custom-vm'" in out
    assert "PUBLIC_URL=https://mini-alpha.exe.xyz" in out


def test_exe_status(cli, project_root, fake_subprocess, monkeypatch):
    monkeypatch.setattr(exe, "_probe", lambda url: "200")
    result = cli.invoke(main, ["status", "-t", "exe"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert any(line.startswith("alpha") and "running" in line and "200" in line for line in lines)
    assert any(line.startswith("beta-site") and "absent" in line for line in lines)


def test_remove_exe_requires_confirmation(cli, project_root, fake_subprocess):
    result = cli.invoke(main, ["remove", "alpha", "-t", "exe"], input="n\n")
    assert result.exit_code != 0
    assert not any("rm" in " ".join(c) for c in fake_subprocess)


def test_new_site_scaffold(cli, project_root):
    result = cli.invoke(main, ["new", "gamma", "--title", 'Gamma "G"', "--description", "Third <site>"])
    assert result.exit_code == 0, result.output
    site = load_project().site("gamma")
    assert site.title == 'Gamma "G"'
    assert (site.path / "app" / "server.py").exists()
    assert "Third &lt;site&gt;" in (site.path / "app" / "templates" / "index.html").read_text()
    for path in site.path.rglob("*.*"):
        assert "__NAME__" not in path.read_text() and "__TITLE__" not in path.read_text()

    again = cli.invoke(main, ["new", "gamma"])
    assert again.exit_code != 0
    assert "already exists" in again.output


def test_new_static_site(cli, project_root):
    result = cli.invoke(main, ["new", "delta", "--kind", "static"])
    assert result.exit_code == 0, result.output
    assert (project_root / "sites" / "delta" / "nginx.conf").exists()


def test_proxy_config_routes_every_site(project_root):
    conf = LocalTarget(load_project(), Runner(dry_run=True)).proxy_config()
    assert "server_name alpha.test;" in conf
    assert "http://alpha:80" in conf
    assert "server_name beta-site.test;" in conf
    assert "http://beta-site:8080" in conf
    assert "default_server" in conf


def test_loopback_names(tmp_path):
    hosts = tmp_path / "hosts"
    hosts.write_text("127.0.0.1 localhost a.test  # comment b.test\n::1 c.test\n10.0.0.1 d.test\n# 127.0.0.1 e.test\n")
    assert loopback_names(hosts) == {"localhost", "a.test", "c.test"}


def test_remove_requires_explicit_sites(cli, project_root, fake_subprocess):
    result = cli.invoke(main, ["remove", "-t", "exe", "-y"])
    assert result.exit_code != 0
    assert "or 'all'" in result.output
    assert fake_subprocess == []
