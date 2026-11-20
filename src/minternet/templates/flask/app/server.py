"""__TITLE__ (minternet site: __NAME__)."""

import os

from flask import Flask, render_template

app = Flask(__name__)

PORT = int(os.getenv("PORT", "80"))
# Injected by the minternet CLI: this site's public base URL.
PUBLIC_URL = os.getenv("PUBLIC_URL", f"http://localhost:{PORT}").rstrip("/")


def site_url(name: str) -> str:
    """Base URL of another minternet site, for cross-site links."""
    key = "SITE_URL_" + name.upper().replace("-", "_")
    return os.getenv(key, f"http://{name}.test").rstrip("/")


@app.context_processor
def inject_urls():
    return {"public_url": PUBLIC_URL, "site_url": site_url}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
