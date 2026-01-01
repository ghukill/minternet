# Mini Internet for Web Archiving

A local "mini internet" for teaching web capture and replay systems (pywb, Browsertrix, WARC-based workflows).

## Quick Start

1. Add to `/etc/hosts`:

   ```
   127.0.0.1 recipes.test
   127.0.0.1 science.test
   127.0.0.1 blogs.test
   127.0.0.1 wowser.test
   ```

   Check if entries are configured:

   ```bash
   ./bin/hosts-check
   ```

2. Build and run:

   ```bash
   docker compose up --build

   # Or run in background
   docker compose up --build -d
   ```

3. Visit the sites (no port numbers needed):
   - http://recipes.test/
   - http://science.test/
   - http://blogs.test/
   - http://wowser.test/

## Sites

| Site | URL | Purpose |
|------|-----|---------|
| recipes.test | http://recipes.test/ | Static baseline - clean HTML, should replay perfectly |
| science.test | http://science.test/ | JS-heavy - demonstrates need for client-side rewriting |
| blogs.test | http://blogs.test/ | Crawler traps - calendar, search, infinite pagination |
| wowser.test | http://wowser.test/ | Pathological - SPA, History API, replay failures |

## Domain Configs

Each domain has a `domain.json` that stores deploy metadata (exe.dev VM name,
service port, and env overrides). These files are read by the CLI for deploys
and status checks.

## Testing Without /etc/hosts

If you can't modify `/etc/hosts`, use curl with Host headers:

```bash
curl -H "Host: recipes.test" http://127.0.0.1/
curl -H "Host: science.test" http://127.0.0.1/
curl -H "Host: blogs.test" http://127.0.0.1/
curl -H "Host: wowser.test" http://127.0.0.1/
```

## Health Checks

Each site exposes `/healthz`:

```bash
curl -H "Host: recipes.test" http://127.0.0.1/healthz
curl -H "Host: science.test" http://127.0.0.1/healthz
curl -H "Host: blogs.test" http://127.0.0.1/healthz
curl -H "Host: wowser.test" http://127.0.0.1/healthz
```

## Teaching Goals

| Site | Demonstrates |
|------|--------------|
| recipes.test | Server-side URL rewriting works - clean, predictable HTML |
| science.test | Need for client-side JS interception (wombat.js-style) |
| blogs.test | Crawler traps, URL explosion, infinite crawl depth |
| wowser.test | Replay failure modes, edge cases, broken patterns |

## Architecture

```
Browser → http://recipes.test/
              ↓
         /etc/hosts → 127.0.0.1
              ↓
         nginx proxy (port 80)
              ↓
         Routes by Host header:
           recipes.test → recipes container (nginx)
           science.test → science container (Flask)
           blogs.test   → blogs container (Flask)
           wowser.test  → wowser container (Flask)
```

- An nginx reverse proxy listens on port 80 and routes by hostname
- Each site runs in its own Docker container (not exposed to host directly)
- recipes.test: nginx serving static files
- science.test, blogs.test, wowser.test: Flask applications

## Stopping

```bash
docker compose down
```
