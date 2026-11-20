"""Smoke tests for the site apps' URL handling (no docker needed)."""

import importlib.util
import sys

import pytest

from tests.conftest import REPO_ROOT

flask = pytest.importorskip("flask")


def load_app(site: str, monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    path = REPO_ROOT / "sites" / site / "app" / "server.py"
    spec = importlib.util.spec_from_file_location(f"site_{site}", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module.app.test_client()


def test_blogs_resolves_cross_site_refs(monkeypatch):
    client = load_app(
        "blogs",
        monkeypatch,
        PUBLIC_URL="https://mini-blogs.exe.xyz",
        SITE_URL_SCIENCE="https://mini-science.exe.xyz",
    )
    body = client.get("/post/cross-domain-archiving-challenges").get_data(as_text=True)
    assert 'src="https://mini-science.exe.xyz/static/images/pendulum.svg"' in body
    assert "SVG file from mini-science.exe.xyz" in body
    assert "{site:" not in body and "{host:" not in body
    sitemap = client.get("/sitemap.xml").get_data(as_text=True)
    assert "<loc>https://mini-blogs.exe.xyz/</loc>" in sitemap


def test_wowser_ws_scheme_follows_public_url(monkeypatch):
    client = load_app("wowser", monkeypatch, PUBLIC_URL="https://mini-wowser.exe.xyz")
    body = client.get("/websocket-demo").get_data(as_text=True)
    assert "wss://mini-wowser.exe.xyz/ws/chat" in body



def test_wowser_ws_chat_streams_and_echoes(monkeypatch):
    """Connect a real WebSocket client to /ws/chat on a live local server."""
    import threading

    simple_websocket = pytest.importorskip("simple_websocket")
    from werkzeug.serving import make_server

    client = load_app(
        "wowser", monkeypatch, WS_SESSION_SECONDS="2", WS_TICK_SECONDS="0.1"
    )
    server = make_server("127.0.0.1", 0, client.application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ws = simple_websocket.Client.connect(f"ws://127.0.0.1:{server.port}/ws/chat")
        try:
            assert ws.receive(timeout=5).startswith("Server: connected at")
            ws.send("ping")
            received = [ws.receive(timeout=5) for _ in range(4)]
            assert "Server echo: ping" in received
            assert "User joined: alice" in received
        finally:
            ws.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)

def test_science_absolute_api_urls(monkeypatch):
    client = load_app("science", monkeypatch, PUBLIC_URL="http://science.test:8080")
    data = client.get("/api/featured").get_json()
    assert data["moreExperimentsUrl"] == "http://science.test:8080/api/experiments"


def test_hub_lists_sites_except_itself(monkeypatch):
    sites = (
        '[{"name":"minternet","url":"http://minternet.test","listed":false},'
        '{"name":"alpha","url":"http://alpha.test","description":"A","listed":true},'
        '{"name":"hidden","url":"http://hidden.test","listed":false}]'
    )
    client = load_app("minternet", monkeypatch, MINTERNET_SITES=sites, MINTERNET_SITE="minternet")
    body = client.get("/").get_data(as_text=True)
    assert 'href="http://alpha.test"' in body
    assert "hidden" not in body
    assert 'href="http://minternet.test"' not in body
