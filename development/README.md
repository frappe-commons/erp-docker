# Development Workspace

This directory is mounted at `/workspace/development` inside the `frappe`
container. The one-command bootstrap creates the default Bench in
`development/frappe-bench`; generated Bench files remain ignored by Git.
The default setup installs only the Frappe framework and creates `localhost`.
The local app manifest belongs at `.config/apps.json`. Optionally configure
`.config/sites.json` to run several database-isolated client sites from the
same Bench; see the complete guide for both formats.

From the repository root, start or resume the environment:

```shell
docker compose -f .config/docker-compose.yml up --detach --wait
```

After setup, open a container terminal, change to the Bench directory, and run
`bench start`. Then open `http://localhost:8000` for the legacy site or a
configured hostname such as `http://client.localhost:8000`.

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

Codex, OpenCode, Headroom, and TokenSave integration is optional and disabled
by default. Enable it for one machine by adding these values to the ignored
`.config/.env`:

```dotenv
ENABLE_HOST_AGENT_TOOLS=1
HOST_AGENT_UV_SOURCE=/absolute/path/to/home/.local/share/uv
HOST_AGENT_UV_TARGET=/absolute/path/to/home/.local/share/uv
HOST_LMS_CLI_SOURCE=/absolute/path/to/home/.lmstudio/bin/lms
HOST_LMS_KEY_SOURCE=/absolute/path/to/home/.lmstudio/.internal/lms-key-2
HOST_LMS_SERVER_CONFIG_SOURCE=/absolute/path/to/home/.lmstudio/.internal/http-server-config.json
CODEX_CONTAINER_SANDBOX=danger-full-access
```

Then include the agent-tools override when using Compose directly:

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

OpenCode works the same way under `ENABLE_HOST_AGENT_TOOLS`. The host
`~/.config/opencode`, `~/.local/share/opencode`, `~/.cache/opencode`, and
`~/.local/state/opencode` directories are mounted, so credentials, providers,
plugins, and sessions are shared with the host. Its wrapper reuses the same
container-local Headroom proxy and TokenSave detection and disables OpenCode's
self-update, because the shared binary is the host's read-only installation.
Set `HOST_OPENCODE_*_HOME` in `.config/.env` when the host uses nonstandard XDG
paths.

When the three `HOST_LMS_*_SOURCE` paths are set, the same opt-in also exposes
the host `lms` CLI in the container. A host-side bridge is started when the Dev
Container opens and accepts traffic only from this Compose project's `frappe`
container; LM Studio remains bound to host loopback and is not exposed to the
LAN. Start LM Studio's service before opening or rebuilding the container.

Docker is the Codex and OpenCode isolation boundary in this environment, so
the Codex wrapper defaults to `--sandbox danger-full-access` while retaining
the configured approval policy. Set `CODEX_CONTAINER_SANDBOX` in `.config/.env`
to override that mode. Codex, OpenCode, and TokenSave state remain shared
through `~/.codex`, the OpenCode directories above, and `~/.tokensave`; the
rest of the host home is not mounted. Recreate the `frappe` container after
installing or upgrading a CLI.

Configuration belongs in the ignored `.config/.env` file. Read the
[complete development environment guide](../docs/05-development/01-development.md)
before changing credentials, updating images, or resetting persistent data.
No symlink or profile-selection step is required.
