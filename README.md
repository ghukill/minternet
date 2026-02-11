# minternet-exe-dev

A tiny internet on exe.dev VMs for testing web archiving.

## CLI

List available domains and deploy metadata:

```bash
uv run minternet list
```

### Deploy

First deploy (creates a new exe.dev VM, builds, and starts the container):

```bash
uv run minternet deploy -d blogs -s exe.dev
```

Update a running VM (rsync code, rebuild image, restart container — no VM teardown):

```bash
uv run minternet deploy -d blogs -s exe.dev --skip-create
```

Deploy all domains at once:

```bash
uv run minternet deploy -d all -s exe.dev          # first time
uv run minternet deploy -d all -s exe.dev --skip-create  # update
```

### Other commands

```bash
uv run minternet status <domain>          # container health on the VM
uv run minternet logs <domain>            # tail docker logs
uv run minternet ssh <domain>             # interactive shell on the VM
uv run minternet ssh <domain> -- <cmd>    # run a one-off command
uv run minternet delete -d <domain> -s exe.dev  # destroy the VM
```

All commands support `--dry-run` to preview what would execute.
