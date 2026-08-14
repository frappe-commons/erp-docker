# Development Workspace

This directory is mounted at `/workspace/development` inside the `frappe`
container. The one-command bootstrap creates the default Bench in
`development/frappe-bench`; generated Bench files remain ignored by Git.

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
docker compose -f .devcontainer/docker-compose.yml exec frappe bash

# Check service health
docker compose -f .devcontainer/docker-compose.yml ps
```

Configuration belongs in the ignored `.env` file at the repository root. Read
the [complete development environment guide](../docs/05-development/01-development.md)
before changing credentials, updating images, or resetting persistent data.
