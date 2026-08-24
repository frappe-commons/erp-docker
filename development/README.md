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
whenever the container starts, so commands such as `codex` and `tokensave`
work in an interactive container shell. Codex and TokenSave keep using their
host state in `~/.codex` and `~/.tokensave`; the rest of the host home is not
mounted. Recreate the `frappe` container after installing or upgrading a CLI.

Configuration belongs in the ignored `.config/.env` file. Read the
[complete development environment guide](../docs/05-development/01-development.md)
before changing credentials, updating images, or resetting persistent data.
No symlink or profile-selection step is required.
