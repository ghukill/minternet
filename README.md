# minternet

A tiny internet of purpose-built websites for teaching and testing web capture
and replay (pywb, Browsertrix, WARC/WACZ workflows). Every site runs locally at
`http://<site>.test` and on [exe.dev](https://exe.dev) at
`https://<vm>.exe.xyz`, from the same Dockerfile and the same CLI.

## Sites

| Site | Purpose |
|------|---------|
| `minternet` | Hub page linking to every other site (generated from config) |
| `recipes` | Static baseline: clean HTML that should replay perfectly |
| `science` | JS-heavy: content via `fetch()`, absolute URLs in JSON, cross-site assets |
| `blogs` | Crawler traps: infinite calendar, search pagination, session IDs, cross-site embeds |
| `wowser` | Pathological: SPA/History API, `<base>` abuse, CSP, refresh loops, WebSockets |

`uv run minternet list` shows every site with its local and exe.dev URLs.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker (for local runs)
- An exe.dev account with your SSH key registered (for `-t exe`), plus `rsync`

## Quick start (local)

```bash
uv run minternet deploy          # build + run every site behind a local proxy on :80
uv run minternet hosts           # check /etc/hosts; prints any lines you need to add
uv run minternet status          # container health + HTTP probe per site
open http://minternet.test
```

The CLI never edits `/etc/hosts`. Without entries you can still use Host headers:
`curl -H 'Host: blogs.test' http://127.0.0.1/`.

## Deploying to exe.dev

```bash
uv run minternet deploy -t exe            # every site
uv run minternet deploy blogs -t exe      # one site
uv run minternet status -t exe            # VM state, proxy port, public/private, HTTP probe
```

`deploy` is idempotent: it creates any missing VM, then rsyncs the site, rebuilds
the image on the VM, replaces the container, waits for its healthcheck, and
(re)applies the exe.dev proxy port and public/private setting. Re-running it is
how you push updates.

## Commands

| Command | |
|---|---|
| `deploy [SITES] [-t local\|exe]` | Build and (re)start sites (all by default) |
| `status [SITES] [-t local\|exe]` | Show state and probe `/healthz` |
| `logs SITE [-t local\|exe] [-f]` | Container logs |
| `remove SITES\|all [-t local\|exe]` | Stop local containers, or **delete** exe.dev VMs (asks first) |
| `ssh SITE [COMMAND...]` | Shell into a site's VM, or run a command there |
| `new NAME [-k flask\|static]` | Scaffold a new site |
| `hosts` | Check `/etc/hosts` for local hostnames |
| `list` | Sites and their URLs |

`--target` defaults to `local`. `deploy` and `remove` accept `--dry-run`, which
prints commands that would change things (read-only lookups still run).

## Adding a site

```bash
uv run minternet new museum --description "Image-heavy galleries"   # Flask
uv run minternet new zine --kind static                             # nginx, static files
uv run minternet deploy museum                                      # try it locally
uv run minternet deploy -t exe                                      # ship it (and refresh the hub)
```

A site is just a directory under `sites/`, so nothing else in the repo needs to change.
The hub and any cross-site links pick up a new site when they are redeployed, which
is why the last step above deploys everything.

### Site contract

```
sites/<name>/
├── site.toml     # title, description, optional overrides
├── Dockerfile    # must serve HTTP on port 80 (or `port` from site.toml)
└── ...           # anything else the Dockerfile needs
```

- The directory name is the site name: lowercase letters, digits and dashes.
- Serve `GET /healthz` and declare a Docker `HEALTHCHECK`; deploys wait for it.
- Don't hardcode hostnames. The CLI injects:

  | Variable | Example (exe.dev) |
  |---|---|
  | `PUBLIC_URL` | `https://minternet-blogs.exe.xyz` |
  | `SITE_URL_<NAME>` (one per site) | `SITE_URL_SCIENCE=https://minternet-science.exe.xyz` |
  | `MINTERNET_SITES` | JSON list of `{name, title, description, url, listed}` |
  | `MINTERNET_SITE`, `MINTERNET_TARGET` | `blogs`, `exe` |
  | anything in `site.toml` `[env]` | |

`site.toml` options (all optional):

```toml
title = "Museum"
description = "Image-heavy galleries"
vm = "my-museum"     # exe.dev VM name; default "<prefix>-<name>"
port = 80            # port the container listens on
public = true        # exe.dev proxy public, or limited to logged-in users
listed = true        # include on the hub page

[env]
SOME_FLAG = "1"
```

## Configuration and naming

`minternet.toml` holds the project-wide settings:

| Setting | Default | Effect |
|---|---|---|
| `prefix` | `minternet` | VM `<prefix>-<site>`, image `<prefix>/<site>`, local docker network `<prefix>` |
| `local.tld` | `test` | Local hostnames `<site>.<tld>` |
| `local.http_port` | `80` | Host port for the local proxy (non-80 ports show up in URLs) |
| `exe.domain` | `exe.xyz` | Public hostnames `<vm>.<domain>` |
| `exe.vm_port` | `8000` | Port the container is published on inside each VM; the exe.dev proxy points here |

## How it works

```
local:   browser → http://blogs.test → nginx proxy (:80, routes by Host) → container "blogs"
exe.dev: browser → https://minternet-blogs.exe.xyz → exe.dev HTTPS proxy → VM :8000 → container "blogs"
```

Both targets run the same `docker build` and `docker run` steps. Locally they run
on your machine, with containers on a shared Docker network behind a generated nginx
proxy (`.minternet/proxy/default.conf`). On exe.dev they run over ssh on the site's
own VM.

## Development

```bash
uv run pytest
```

Tests cover config derivation, generated commands (via `--dry-run` with a fake
subprocess), scaffolding, and the sites' URL handling. They don't need Docker or
network access.
