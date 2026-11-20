import os
from urllib.parse import urlsplit

from flask import Flask, render_template, jsonify

app = Flask(__name__)

PORT = int(os.getenv("PORT", "80"))
# Injected by the minternet CLI: this site's public base URL, e.g. https://x.exe.xyz
PUBLIC_URL = os.getenv("PUBLIC_URL", f"http://localhost:{PORT}").rstrip("/")
_parsed = urlsplit(PUBLIC_URL)
PUBLIC_SCHEME = _parsed.scheme
PUBLIC_HOST = _parsed.netloc

# Sample experiment data
EXPERIMENTS = [
    {
        "id": 1,
        "title": "Baking Soda Volcano",
        "category": "Chemistry",
        "difficulty": "Easy",
        "description": "Create a classic volcanic eruption using baking soda and vinegar.",
        "materials": ["Baking soda", "Vinegar", "Food coloring", "Container"]
    },
    {
        "id": 2,
        "title": "Crystal Growing",
        "category": "Chemistry",
        "difficulty": "Medium",
        "description": "Grow beautiful crystals from a supersaturated solution.",
        "materials": ["Sugar or salt", "Water", "String", "Pencil", "Jar"]
    },
    {
        "id": 3,
        "title": "Pendulum Waves",
        "category": "Physics",
        "difficulty": "Medium",
        "description": "Create mesmerizing wave patterns with a series of pendulums.",
        "materials": ["String", "Nuts or weights", "Wooden dowel", "Ruler"]
    },
    {
        "id": 4,
        "title": "Plant Maze",
        "category": "Biology",
        "difficulty": "Easy",
        "description": "Watch a plant navigate a maze to reach sunlight.",
        "materials": ["Bean seeds", "Cardboard box", "Cardboard pieces", "Soil", "Cup"]
    },
    {
        "id": 5,
        "title": "Static Electricity",
        "category": "Physics",
        "difficulty": "Easy",
        "description": "Explore static electricity with balloons and everyday objects.",
        "materials": ["Balloons", "Wool fabric", "Paper pieces", "Salt", "Pepper"]
    }
]


@app.route('/')
def index():
    return render_template(
        'index.html',
        public_host=PUBLIC_HOST,
        public_scheme=PUBLIC_SCHEME,
    )


@app.route('/healthz')
def healthz():
    return 'OK'


# API endpoint with relative URL (will work in replay)
@app.route('/api/experiments')
def get_experiments():
    return jsonify({
        "experiments": [
            {"id": e["id"], "title": e["title"], "category": e["category"], "difficulty": e["difficulty"]}
            for e in EXPERIMENTS
        ]
    })


# API endpoint for single experiment
@app.route('/api/experiment/<int:experiment_id>')
def get_experiment(experiment_id):
    experiment = next((e for e in EXPERIMENTS if e["id"] == experiment_id), None)
    if experiment:
        return jsonify(experiment)
    return jsonify({"error": "Experiment not found"}), 404


# API endpoint that returns data with absolute URLs (demonstrates replay issues)
@app.route('/api/featured')
def get_featured():
    base_url = PUBLIC_URL
    return jsonify({
        "featured": {
            "id": 1,
            "title": "Baking Soda Volcano",
            # This absolute URL will break in replay!
            "detailUrl": f"{base_url}/api/experiment/1",
            "imageUrl": f"{base_url}/static/volcano.svg"
        },
        "moreExperimentsUrl": f"{base_url}/api/experiments"
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
