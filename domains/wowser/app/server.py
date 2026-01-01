import os

from flask import Flask, render_template, jsonify, make_response, request
import random
import string
import base64

app = Flask(__name__)

PUBLIC_HOST = os.getenv("PUBLIC_HOST", "wowser.test")
PUBLIC_SCHEME = os.getenv("PUBLIC_SCHEME", "http")
PUBLIC_WS_SCHEME = os.getenv("PUBLIC_WS_SCHEME", "ws")
PORT = int(os.getenv("PORT", "80"))


def _public_base_url() -> str:
    return f"{PUBLIC_SCHEME}://{PUBLIC_HOST}"


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


# WebSocket attempt (will fail but shows the pattern)
@app.route('/websocket-demo')
def websocket_demo():
    return render_template(
        'websocket_demo.html',
        public_ws_url=_public_ws_url(),
    )


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
