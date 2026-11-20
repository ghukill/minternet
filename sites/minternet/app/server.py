"""The Minternet hub: an index page linking to every listed site.

The site list comes from MINTERNET_SITES, which the minternet CLI injects at
deploy time, so new sites appear here without editing this app.
"""

import json
import os

from flask import Flask, render_template

app = Flask(__name__)

PORT = int(os.getenv("PORT", "80"))
SELF = os.getenv("MINTERNET_SITE", "minternet")


def listed_sites() -> list[dict]:
    try:
        sites = json.loads(os.getenv("MINTERNET_SITES", "[]"))
    except json.JSONDecodeError:
        return []
    return [s for s in sites if s.get("listed", True) and s.get("name") != SELF]


@app.route("/")
def index():
    return render_template("index.html", sites=listed_sites())


@app.route("/healthz")
def healthz():
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
