# Development Workspace

This directory is mounted at `/workspace/development` inside the `frappe`
container. The one-command bootstrap creates the default Bench in
`development/frappe-bench`; generated Bench files remain ignored by Git.
The default setup installs only the Frappe framework. Optional app manifests
belong in the repository's ignored `.apps-json/` directory; see the complete
guide for the expected format.

From the repository root, start or resume the environment:

```shell
docker compose -f .devcontainer/docker-compose.yml up --detach --wait
```

Then open `http://localhost:8000` and sign in as `Administrator` with password
`admin`.

Common host commands:

```shell
# Follow Frappe logs
docker compose -f .devcontainer/docker-compose.yml logs --follow frappe

# Open a shell in this workspace
docker compose -f .devcontainer/docker-compose.yml exec --user frappe --env HOME=/home/frappe frappe bash

# Check service health
docker compose -f .devcontainer/docker-compose.yml ps
```

Host-installed user CLIs are bridged into the development container from the
host's NVM, Cargo, and `~/.local/bin` directories. Their launchers are rebuilt
whenever the container starts, so commands such as `codex` and `tokensave`
work in an interactive container shell. Codex and TokenSave keep using their
host state in `~/.codex` and `~/.tokensave`; the rest of the host home is not
mounted. Recreate the `frappe` container after installing or upgrading a CLI.

Configuration belongs in the ignored `.devcontainer/.env` file. Read the
[complete development environment guide](../docs/05-development/01-development.md)
before changing credentials, updating images, or resetting persistent data.
If configuration is stored in a named profile such as `.devcontainer/srv.env`,
select it from the repository root with
`ln -s srv.env .devcontainer/.env` before opening the Dev Container.
