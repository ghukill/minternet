import os

from flask import Flask, Response, redirect, render_template, request, make_response
import calendar
from datetime import datetime
import uuid

app = Flask(__name__)

PUBLIC_HOST = os.getenv("PUBLIC_HOST", "blogs.test")
PUBLIC_SCHEME = os.getenv("PUBLIC_SCHEME", "http")
SCIENCE_HOST = os.getenv("SCIENCE_HOST", "science.test")
SCIENCE_SCHEME = os.getenv("SCIENCE_SCHEME", "http")
PORT = int(os.getenv("PORT", "80"))

# Sample blog posts (ordered by date, newest first)
POSTS = [
    {
        "slug": "cross-domain-archiving-challenges",
        "title": "Cross-Domain Linking in Web Archives",
        "author": "charlie",
        "date": "2024-04-15",
        "excerpt": "How external resource links complicate web archive replay.",
        "content": """One of the trickiest aspects of web archiving is handling cross-domain resources.
        When a page on one domain embeds or links to content on another domain, archivists face decisions.

        Consider this embedded image from the science domain:
        <img src="http://science.test/static/images/pendulum.svg" alt="Pendulum Wave Experiment" style="max-width: 200px; display: block; margin: 1em 0;">

        For this image to display correctly in a replayed archive, the crawler must have:
        1. Followed the cross-domain link during capture
        2. Downloaded the SVG file from science.test
        3. Stored it in the WARC with proper metadata

        During replay, the archive playback system must rewrite the URL to serve the archived version
        instead of attempting to fetch from the live web.

        <strong>Common Cross-Domain Resources:</strong>
        <ul>
        <li>Images: <a href="http://science.test/static/images/volcano.svg">Volcano SVG</a></li>
        <li>Data: <a href="http://science.test/static/data/experiments.csv">Experiments CSV</a></li>
        <li>PDFs: <a href="http://science.test/static/documents/safety-guide.pdf">Safety Guide</a></li>
        </ul>

        Tools like Browsertrix and pywb handle this through URL rewriting, but edge cases
        still cause replay failures."""
    },
    {
        "slug": "science-resources-for-archivists",
        "title": "Science Resources for Web Archivists",
        "author": "alice",
        "date": "2024-04-10",
        "excerpt": "Exploring cross-domain scientific resources and how they challenge archiving.",
        "content": """When archiving websites, we often encounter pages that reference resources from other domains.
        This is especially common with scientific content that shares data and images across institutions.

        For example, the <a href="http://science.test">Science Experiments site</a> hosts various resources
        that other sites might embed or link to:

        <strong>Images:</strong> Scientific diagrams like the
        <a href="http://science.test/static/images/volcano.svg">volcano experiment diagram</a> and the
        <a href="http://science.test/static/images/crystal.svg">crystal growing illustration</a> are commonly
        embedded in educational materials.

        <strong>Data Files:</strong> Researchers often link to shared datasets. The
        <a href="http://science.test/static/data/experiments.csv">experiments catalog (CSV)</a> contains
        metadata about various experiments, while the
        <a href="http://science.test/static/data/observations.csv">observations log</a> tracks experimental results.

        <strong>Documents:</strong> Safety documentation like the
        <a href="http://science.test/static/documents/safety-guide.pdf">Laboratory Safety Guide (PDF)</a>
        is essential for any science education site.

        When archiving content that links to these cross-domain resources, crawlers must be configured
        to follow these external links and capture the referenced assets."""
    },
    {
        "slug": "getting-started-with-web-archiving",
        "title": "Getting Started with Web Archiving",
        "author": "alice",
        "date": "2024-03-15",
        "excerpt": "Learn the basics of preserving web content for future generations.",
        "content": """Web archiving is the process of collecting and preserving web content for future access.
        Whether you're a librarian, researcher, or just someone who wants to save a favorite website,
        understanding web archiving is increasingly important in our digital age.

        The most common format for web archives is WARC (Web ARChive), which stores both the content
        and metadata about how it was captured. Tools like Browsertrix, wget, and pywb make it possible
        for anyone to create and replay web archives."""
    },
    {
        "slug": "understanding-crawler-traps",
        "title": "Understanding Crawler Traps",
        "author": "bob",
        "date": "2024-02-28",
        "excerpt": "What are crawler traps and how do they affect web archiving?",
        "content": """A crawler trap is a set of URLs that can cause a web crawler to crawl indefinitely.
        Common examples include calendar widgets, search pages with pagination, and session IDs in URLs.

        For web archiving, crawler traps pose a significant challenge. Without proper handling,
        a crawler might spend days downloading an infinite calendar or millions of search result pages.

        This very website is designed to demonstrate several common crawler traps!"""
    },
    {
        "slug": "warc-file-format-explained",
        "title": "The WARC File Format Explained",
        "author": "alice",
        "date": "2024-01-10",
        "excerpt": "A deep dive into the standard format for web archives.",
        "content": """WARC (Web ARChive) is an ISO standard file format for storing web crawls.
        Each WARC file contains multiple records, each representing a single captured resource.

        A typical WARC record includes:
        - The original request
        - The response headers
        - The response body
        - Metadata about the capture (timestamp, software used, etc.)

        This format allows archives to faithfully replay websites as they appeared at capture time."""
    },
    {
        "slug": "javascript-and-replay-challenges",
        "title": "JavaScript and Web Archive Replay",
        "author": "charlie",
        "date": "2023-12-05",
        "excerpt": "Why modern JavaScript makes replay difficult.",
        "content": """Modern websites rely heavily on JavaScript for rendering content.
        This poses challenges for web archives because JavaScript often makes requests to external servers.

        When replaying an archive, these requests need to be intercepted and rewritten to fetch
        from the archive instead of the live web. Tools like wombat.js handle this rewriting,
        but it's not always perfect.

        Absolute URLs, dynamic API calls, and WebSocket connections can all cause replay failures."""
    },
    {
        "slug": "preserving-social-media",
        "title": "Challenges of Preserving Social Media",
        "author": "bob",
        "date": "2023-11-20",
        "excerpt": "Why archiving social platforms is particularly difficult.",
        "content": """Social media platforms present unique challenges for web archiving.
        Content is often personalized, login-gated, and generated through complex JavaScript applications.

        Additionally, the sheer volume of content being produced makes comprehensive archiving nearly impossible.
        Archivists must make difficult decisions about what to prioritize and how to authenticate."""
    }
]

AUTHORS = {
    "alice": {"name": "Alice Chen", "bio": "Digital preservation specialist with 10 years of experience."},
    "bob": {"name": "Bob Martinez", "bio": "Web developer turned archivist. Loves breaking crawlers."},
    "charlie": {"name": "Charlie Kim", "bio": "Researcher focusing on JavaScript-heavy site preservation."}
}

# Generate search terms for trap
SEARCH_SUGGESTIONS = ["archive", "warc", "crawler", "javascript", "preservation", "web", "replay", "capture"]


def _replace_science_links(text: str) -> str:
    science_base = f"{SCIENCE_SCHEME}://{SCIENCE_HOST}"
    updated = text.replace("http://science.test", science_base)
    return updated.replace("science.test", SCIENCE_HOST)


def _decorate_post(post: dict) -> dict:
    updated = dict(post)
    if isinstance(updated.get("content"), str):
        updated["content"] = _replace_science_links(updated["content"])
    if isinstance(updated.get("excerpt"), str):
        updated["excerpt"] = _replace_science_links(updated["excerpt"])
    return updated


def _decorate_posts(posts: list[dict]) -> list[dict]:
    return [_decorate_post(post) for post in posts]


def _template_context(session_id: str | None, **kwargs: object) -> dict:
    return {
        "authors": AUTHORS,
        "session_id": session_id,
        "public_host": PUBLIC_HOST,
        "public_scheme": PUBLIC_SCHEME,
        **kwargs,
    }


def get_session_id():
    """Get or create a session ID (crawler trap!)"""
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    return session_id


@app.route('/')
def index():
    session_id = get_session_id()
    response = make_response(render_template('index.html',
        posts=_decorate_posts(POSTS[:3]),
        **_template_context(session_id)
    ))
    response.set_cookie('session_id', session_id)
    return response


@app.route('/healthz')
def healthz():
    return 'OK'


@app.route('/posts/<slug>')
def post_redirect(slug):
    return redirect(f'/post/{slug}', code=301)


@app.route('/sitemap.xml')
def sitemap():
    base = f'{PUBLIC_SCHEME}://{PUBLIC_HOST}'
    urls = [f'{base}/']
    urls += [f'{base}/post/{p["slug"]}' for p in POSTS]
    urls += [f'{base}/author/{a}' for a in AUTHORS]

    xml_entries = '\n'.join(
        f'  <url><loc>{url}</loc></url>' for url in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{xml_entries}\n'
        '</urlset>\n'
    )
    return Response(xml, mimetype='application/xml')


@app.route('/post/<slug>')
def post(slug):
    session_id = get_session_id()
    post = next((p for p in POSTS if p['slug'] == slug), None)
    if not post:
        return render_template('404.html', **_template_context(session_id)), 404

    response = make_response(render_template('post.html',
        post=_decorate_post(post),
        author=AUTHORS.get(post['author']),
        **_template_context(session_id)
    ))
    response.set_cookie('session_id', session_id)
    return response


@app.route('/author/<name>')
def author(name):
    session_id = get_session_id()
    author_info = AUTHORS.get(name)
    if not author_info:
        return render_template('404.html', **_template_context(session_id)), 404

    author_posts = _decorate_posts([p for p in POSTS if p['author'] == name])

    response = make_response(render_template('author.html',
        author_name=name,
        author=author_info,
        posts=author_posts,
        **_template_context(session_id)
    ))
    response.set_cookie('session_id', session_id)
    return response


# CRAWLER TRAP: Infinite calendar navigation
@app.route('/calendar')
def calendar_view():
    session_id = get_session_id()
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    # Normalize month (allows going before 1 or after 12)
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1

    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    # Posts in this month
    month_str = f"{year}-{month:02d}"
    month_posts = _decorate_posts([p for p in POSTS if p['date'].startswith(month_str)])

    response = make_response(render_template('calendar.html',
        year=year,
        month=month,
        month_name=month_name,
        calendar=cal,
        posts=month_posts,
        **_template_context(session_id)
    ))
    response.set_cookie('session_id', session_id)
    return response


# CRAWLER TRAP: Infinite search pagination
@app.route('/search')
def search():
    session_id = get_session_id()
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    # "Search" results - always return something to keep crawler going
    if query:
        results = _decorate_posts([
            p for p in POSTS
            if query.lower() in p['title'].lower() or query.lower() in p['content'].lower()
        ])
    else:
        results = []

    # Simulate more pages (infinite pagination trap!)
    has_next = page < 1000  # Could go forever, but let's cap it
    has_prev = page > 1

    response = make_response(render_template('search.html',
        query=query,
        page=page,
        results=results,
        has_next=has_next,
        has_prev=has_prev,
        suggestions=SEARCH_SUGGESTIONS,
        **_template_context(session_id)
    ))
    response.set_cookie('session_id', session_id)
    return response


# CRAWLER TRAP: Date-based archives
@app.route('/archive/<int:year>/<int:month>')
def archive(year, month):
    session_id = get_session_id()
    month_str = f"{year}-{month:02d}"
    month_posts = _decorate_posts([p for p in POSTS if p['date'].startswith(month_str)])
    month_name = calendar.month_name[month] if 1 <= month <= 12 else "Unknown"

    response = make_response(render_template('archive.html',
        year=year,
        month=month,
        month_name=month_name,
        posts=month_posts,
        **_template_context(session_id)
    ))
    response.set_cookie('session_id', session_id)
    return response


# Session-tracked page (URL changes with session)
@app.route('/track')
def tracked_page():
    session_id = get_session_id()
    tracking_id = request.args.get('tid', session_id)

    response = make_response(render_template('tracked.html',
        tracking_id=tracking_id,
        **_template_context(session_id)
    ))
    response.set_cookie('session_id', session_id)
    return response


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
