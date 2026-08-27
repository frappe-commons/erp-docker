# Development Workspace

This directory is mounted at `/workspace/development` inside the `frappe`
container. The one-command bootstrap creates the default Bench in
`development/frappe-bench`; generated Bench files remain ignored by Git.
The default setup installs only the Frappe framework. The local app manifest
belongs at `.config/apps.json`; see the complete guide for its format.

From the repository root, start or resume the environment:

```shell
docker compose -f .config/docker-compose.yml up --detach --wait
```

After setup, open a container terminal, change to the Bench directory, and run
`bench start`. Then open `http://localhost:8000`.

Common host commands:

```shell
# Follow Frappe logs
docker compose -f .config/docker-compose.yml logs --follow frappe

# Open a shell in this workspace
docker compose -f .config/docker-compose.yml exec --user frappe --env HOME=/home/frappe frappe bash

# Check service health
docker compose -f .config/docker-compose.yml ps
```

Host-installed user CLIs are bridged into the development container from the
host's NVM, Cargo, and `~/.local/bin` directories. Their launchers are rebuilt
whenever the container starts.

Codex, Headroom, and TokenSave integration is optional and disabled by default.
Enable it by adding the agent-tools override:

```shell
docker compose \
  -f .config/docker-compose.yml \
  -f .config/docker-compose.agent-tools.yml \
  up --detach --wait
```

The opt-in Codex wrapper keeps using the host's login and configuration while
translating host-only MCP paths. It starts a container-local Headroom proxy
using the host-installed version and enables TokenSave only when the current
Git repository already contains a readable `.tokensave/tokensave.db`.
TokenSave is never initialized implicitly.

Docker is the Codex isolation boundary in this environment, so the wrapper
defaults to `--sandbox danger-full-access` while retaining the configured
approval policy. Set `CODEX_CONTAINER_SANDBOX` in `.config/.env` to override
that mode. Codex and TokenSave state remain shared through `~/.codex` and
`~/.tokensave`; the rest of the host home is not mounted. Recreate the `frappe`
container after installing or upgrading a CLI.

Configuration belongs in the ignored `.config/.env` file. Read the
[complete development environment guide](../docs/05-development/01-development.md)
before changing credentials, updating images, or resetting persistent data.
No symlink or profile-selection step is required.
