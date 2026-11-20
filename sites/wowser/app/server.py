import os
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import Flask, render_template, jsonify, make_response, request
from flask_sock import Sock
import random
import string
import base64

app = Flask(__name__)
sock = Sock(app)

PORT = int(os.getenv("PORT", "80"))
# Injected by the minternet CLI: this site's public base URL, e.g. https://x.exe.xyz
PUBLIC_URL = os.getenv("PUBLIC_URL", f"http://localhost:{PORT}").rstrip("/")
_parsed = urlsplit(PUBLIC_URL)
PUBLIC_SCHEME = _parsed.scheme
PUBLIC_HOST = _parsed.netloc
PUBLIC_WS_SCHEME = "wss" if PUBLIC_SCHEME == "https" else "ws"


def _public_base_url() -> str:
    return PUBLIC_URL


def _public_ws_url() -> str:
    return f"{PUBLIC_WS_SCHEME}://{PUBLIC_HOST}/ws/chat"

# Generate a random string
def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/healthz')
def healthz():
    return 'OK'


# SPA catch-all route - History API will handle client-side
@app.route('/app/<path:path>')
def spa_catchall(path):
    return render_template('spa.html', path=path)


# Base tag abuse demo
@app.route('/base-demo')
def base_demo():
    return render_template(
        'base_demo.html',
        public_base_url=_public_base_url(),
    )


# Randomized URLs - each response includes links to random new URLs
@app.route('/random')
@app.route('/random/<path:path>')
def random_page(path=None):
    # Generate random links that will be different each time
    random_links = [f'/random/{random_string()}' for _ in range(5)]
    return render_template('random.html', current_path=path, random_links=random_links)


# Inline base64 assets demo
@app.route('/inline-assets')
def inline_assets():
    return render_template('inline_assets.html')


# Large script demo
@app.route('/large-script')
def large_script():
    return render_template('large_script.html')


# CSP header issues demo
@app.route('/csp-demo')
def csp_demo():
    response = make_response(render_template('csp_demo.html'))
    # Deliberately restrictive CSP that will break things
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'"
    return response


# Meta refresh redirect loop
@app.route('/refresh-loop')
def refresh_loop():
    count = request.args.get('count', 0, type=int)
    return render_template('refresh_loop.html', count=count)


# WebSocket demo: the page connects live to /ws/chat (works live, not in replay)
@app.route('/websocket-demo')
def websocket_demo():
    return render_template(
        'websocket_demo.html',
        public_ws_url=_public_ws_url(),
    )


# Each WebSocket holds a gunicorn thread, so sessions are time-boxed.
WS_SESSION_SECONDS = int(os.getenv("WS_SESSION_SECONDS", "60"))
WS_TICK_SECONDS = float(os.getenv("WS_TICK_SECONDS", "2"))
WS_SCRIPT = [
    "User joined: alice",
    "alice: Hello everyone!",
    "User joined: bob",
    "bob: Is anyone archiving this conversation?",
    "alice: Good luck with that.",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


@sock.route('/ws/chat')
def ws_chat(ws):
    """Live feed: scripted chatter, then clock ticks; echoes anything the client sends."""
    ws.send(f"Server: connected at {_utc_now()}")
    script = iter(WS_SCRIPT)
    deadline = time.monotonic() + WS_SESSION_SECONDS
    while time.monotonic() < deadline:
        message = ws.receive(timeout=WS_TICK_SECONDS)
        if message is not None:
            ws.send(f"Server echo: {message}")
        else:
            ws.send(next(script, f"Server: tick {_utc_now()}"))
    ws.send(f"Server: {WS_SESSION_SECONDS}s demo session over, closing.")


# API that returns random data each time
@app.route('/api/random-data')
def random_data():
    return jsonify({
        'id': random_string(),
        'timestamp': random.randint(1000000000, 9999999999),
        'data': [random_string() for _ in range(3)],
        'next': f'/api/random-data?seed={random_string()}'
    })


# Shadow DOM demo
@app.route('/shadow-dom')
def shadow_dom():
    return render_template('shadow_dom.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
