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

Configuration belongs in the ignored `.devcontainer/.env` file. Read the
[complete development environment guide](../docs/05-development/01-development.md)
before changing credentials, updating images, or resetting persistent data.
