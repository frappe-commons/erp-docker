---
title: macOS Company Development Setup
---

# macOS Company Development Environments

This guide uses the shared `main` branch for any company or site. The developer
provides two ignored local files:

1. An apps JSON file containing the exact app repositories and branches.
2. An environment file containing site settings and local credentials.

The repository supplies one orchestration script. It does not create, modify,
print, or commit either input.

## Install the Mac prerequisites

Install:

- [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
- [Git for macOS](https://git-scm.com/download/mac)

In Docker Desktop, allocate at least 6 GB memory, 4 CPUs, and 20 GB free disk
space. Native Apple Silicon images are used where available; do not force
`linux/amd64` unless a required private image lacks ARM64 support.

Verify the tools in Terminal:

```shell
git --version
docker version
docker compose version
```

If the app manifest uses SSH Git URLs, start the host SSH agent, load the
required key, and verify the Git host is already trusted:

```shell
ssh-add -l
ssh -T git@github.com
```

Compose forwards the agent and mounts host `config` and `known_hosts` files
read-only. It never mounts the underlying private key files.

## Clone the shared repository

```shell
git clone https://github.com/bhickta/erp-docker.git frappe_docker
cd frappe_docker
```

Only `main` is required. Company-specific branches are not part of the setup.

## Company developer handoff

A developer receives two files from the company administrator through a secure
channel. Save them at the fixed paths used by the Dev Container:

```text
.config/apps.json
.config/.env
```

The files are intentionally excluded from Git. Tracked `.example` files show
their neutral formats without company repositories or credentials.

## Provide the app manifest

Store the provided manifest at `.config/apps.json`:

```json
[
  {
    "url": "https://github.com/frappe/erpnext.git",
    "branch": "version-16"
  }
]
```

The manifest must contain every app installed in the source backup. Use the
exact repository and a branch compatible with the Frappe version. A restored
database cannot migrate successfully when an installed app is absent from the
Bench.

## Provide the environment file

Store the provided environment at `.config/.env`:

```dotenv
COMPOSE_PROJECT_NAME=example_company_development
FRAPPE_BRANCH=version-16
ADMIN_PASSWORD=admin
DB_PASSWORD=change-this-local-password
HTTP_PORT=8000
SOCKETIO_PORT=9000
FRAPPE_API_TOKEN=key:secret
SOURCE_SITE_URL=https://source.example.com
APPS_JSON=/workspace/.config/apps.json
```

`FRAPPE_API_TOKEN` is needed only for authenticated backup downloads. Never put
it in the app manifest, documentation, a command, or a commit.

## Validate the inputs

Run from the repository root:

```shell
development/dev-env.sh \
  --apps-json .config/apps.json \
  --env-file .config/.env \
  validate
```

Validation confirms that both files exist, the app manifest is inside the
mounted repository, Docker is available, and the merged Compose configuration
is valid. It does not print the resolved configuration or credentials.

## Start the environment

```shell
development/dev-env.sh \
  --apps-json .config/apps.json \
  --env-file .config/.env \
  up
```

The command initializes a new Bench and site when missing, then waits until
setup completes. VS Code users can instead choose **Dev Containers: Reopen in
Container** directly. Start Bench manually from the container terminal.

## Restore the latest backup

Pass the source-site origin to discover its newest downloadable database
backup automatically, or pass a specific database-backup URL:

```shell
development/dev-env.sh \
  --apps-json .config/apps.json \
  --env-file .config/.env \
  restore-latest https://source.example.com
```

The command starts the environment when necessary, authenticates using the
provided environment file, validates the download, replaces the default local
site's database, runs migrations, and lists the installed apps. Restoring is
destructive to the selected local database.

For a short-lived shell session, the URL can be supplied without adding it to
a file:

```shell
DEV_BACKUP_URL=LATEST_BACKUP_URL development/dev-env.sh \
  --apps-json .config/apps.json \
  --env-file .config/.env \
  restore-latest
```

## Everyday commands

Reuse the same inputs with another command:

```shell
# Status
development/dev-env.sh --apps-json .config/apps.json --env-file .config/.env status

# Follow Frappe logs
development/dev-env.sh --apps-json .config/apps.json --env-file .config/.env logs

# Stop without deleting Bench files or database volumes
development/dev-env.sh --apps-json .config/apps.json --env-file .config/.env stop
```

Replace the two ignored files to switch environments; no symlink is involved.

## Mac troubleshooting

- If a host port is occupied, change it in the provided environment file.
- If Docker becomes slow, increase Docker Desktop memory before changing image
  architecture.
- If migration reports a missing app, correct the provided apps JSON using the
  installed-app set from the source backup, recreate a clean Bench, and restore
  again.
- If an image has no ARM64 build, set `DOCKER_DEFAULT_PLATFORM=linux/amd64` only
  for that session; emulation is slower.

For resets, persistence, VS Code attachment, and general troubleshooting, see
the [complete development guide](01-development.md).
