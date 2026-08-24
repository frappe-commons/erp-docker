---
title: Local Development
---

# Local Development with Docker Compose

This repository includes a complete local Frappe development environment for
macOS, Windows, and Linux. Docker and Docker Compose are the only runtime
dependencies on the host; VS Code is optional.

> This environment is for local development only. It uses convenient default
> credentials and is not suitable for production or an internet-facing host.

## Quick start

Install these prerequisites:

- [Git](https://git-scm.com/downloads)
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose v2](https://docs.docker.com/compose/), invoked as
  `docker compose`

Docker Desktop includes Compose v2 on macOS and Windows. Linux users should
install Docker Engine with the Compose plugin and ensure their user can access
the Docker daemon. Allocate at least 4 GB of memory to Docker.

Clone the repository and enter it:

```shell
git clone https://github.com/bhickta/erp-docker.git frappe_docker
cd frappe_docker
```

From the repository root, create and start the environment with the same
command on every supported host:

```shell
docker compose -f .config/docker-compose.yml up --detach --wait
```

The first run pulls container images and clones the Frappe framework, so it can
take several minutes. The command returns when Bench setup finishes.

Open a container terminal and start Bench manually:

```shell
cd /workspace/development/frappe-bench
bench start
```

Open `http://localhost:8000` and sign in with:

- User: `Administrator`
- Password: `admin`

Running the command again is safe. The bootstrap reuses an existing Bench and
site instead of recreating them.

## What the command creates

The development Compose project starts these services:

| Service       | Purpose                                           |
| ------------- | ------------------------------------------------- |
| `frappe`      | Bench CLI, Frappe web server, workers, and assets |
| `mariadb`     | Site database                                     |
| `redis-cache` | Frappe cache                                      |
| `redis-queue` | Queue and Socket.IO Redis service                 |

The `frappe` service runs `.devcontainer/start-development.sh`, which:

1. Aligns file ownership with the repository owner on native Linux.
2. Creates `development/frappe-bench` when no Bench exists.
3. Configures MariaDB, Redis, and developer mode.
4. Creates the `development.localhost` site when missing, or selects the
   existing site.
5. Keeps the container ready for a developer to run `bench start` manually.

By default, the Bench contains only the Frappe framework on `version-16`.
An optional apps JSON file can add ERPNext or other apps during the first run.

## Configure the environment

### Defaults

| Setting                | Default                 |
| ---------------------- | ----------------------- |
| Compose project        | `frappe_development`    |
| Bench directory        | `frappe-bench`          |
| Site                   | `development.localhost` |
| Frappe branch          | `version-16`            |
| Additional apps        | None                    |
| Administrator password | `admin`                 |
| MariaDB root password  | `123`                   |
| HTTP port              | `8000`                  |
| Socket.IO port         | `9000`                  |

### Use a `.env` file

Create an ignored `.config/.env` file before the first run to change the
defaults without using shell-specific environment syntax. Compose loads this
file because it lives beside `.config/docker-compose.yml`:

```dotenv
COMPOSE_PROJECT_NAME=my-frappe-development
BENCH_NAME=frappe-bench
SITE_NAME=my-site.localhost
FRAPPE_BRANCH=version-16
ADMIN_PASSWORD=change-me
DB_PASSWORD=change-me-too
HTTP_PORT=8010
SOCKETIO_PORT=9010
```

No symlink or profile-selection command is required. Put the provided files
directly at `.config/.env` and `.config/apps.json`.

| Variable               | When it is used                                     |
| ---------------------- | --------------------------------------------------- |
| `COMPOSE_PROJECT_NAME` | Names and isolates the Compose project and volumes  |
| `BENCH_NAME`           | Selects or creates `development/<BENCH_NAME>`       |
| `SITE_NAME`            | Selects an existing site or creates a new site      |
| `FRAPPE_BRANCH`        | Applies only when a new Bench is created            |
| `APPS_JSON`            | Optional app-list path used for a new Bench          |
| `BACKUP_URL`           | Optional database backup restored once during setup  |
| `ADMIN_PASSWORD`       | Applies only when a new site is created             |
| `DB_PASSWORD`          | Initializes MariaDB and authenticates site creation |
| `FRAPPE_API_TOKEN`     | Optional token used for authenticated backup downloads |
| `SOURCE_SITE_URL`      | Optional source origin used to discover the latest backup |
| `HTTP_PORT`            | Publishes the Frappe web server on the host         |
| `SOCKETIO_PORT`        | Publishes the Socket.IO service on the host         |

Keep the same `COMPOSE_PROJECT_NAME` and `DB_PASSWORD` after the first run.
Changing the project name selects a different set of containers and volumes;
changing the password does not update an existing MariaDB account.

Preview the resolved configuration without starting or changing containers:

```shell
docker compose -f .config/docker-compose.yml config
```

## Everyday commands

Run these commands from the repository root.

### Start or resume the environment

```shell
docker compose -f .config/docker-compose.yml up --detach --wait
```

Compose recreates a service when its configuration changed and leaves healthy,
unchanged services running.

### Check service status

```shell
docker compose -f .config/docker-compose.yml ps
```

### Follow logs

All services:

```shell
docker compose -f .config/docker-compose.yml logs --follow --tail=200
```

Only the Frappe bootstrap and development server:

```shell
docker compose -f .config/docker-compose.yml logs --follow --tail=200 frappe
```

Press `Ctrl+C` to stop following logs; the containers continue running.

### Open a development shell

```shell
docker compose -f .config/docker-compose.yml exec --user frappe --env HOME=/home/frappe frappe bash
```

The repository is mounted at `/workspace`, and the development workspace is
`/workspace/development`. The explicit user and home directory keep files
owned by the development user; omitting them opens a root shell because the
container initially starts as root to align native Linux file ownership.

### Run Bench commands from the host

Use Compose's `--workdir` option so Bench runs from the correct directory. For
the default Bench and site:

```shell
docker compose -f .config/docker-compose.yml exec --user frappe --env HOME=/home/frappe --workdir /workspace/development/frappe-bench frappe bench --site development.localhost migrate
```

Other useful examples:

```shell
docker compose -f .config/docker-compose.yml exec --user frappe --env HOME=/home/frappe --workdir /workspace/development/frappe-bench frappe bench --site development.localhost console
docker compose -f .config/docker-compose.yml exec --user frappe --env HOME=/home/frappe --workdir /workspace/development/frappe-bench frappe bench --site development.localhost backup --with-files
docker compose -f .config/docker-compose.yml exec --user frappe --env HOME=/home/frappe --workdir /workspace/development/frappe-bench frappe bench list-sites
```

Replace the Bench path and site name when `BENCH_NAME` or `SITE_NAME` is
overridden.

### Stop without deleting data

```shell
docker compose -f .config/docker-compose.yml stop
```

Run the quick-start command again to resume.

### Remove replaceable containers

```shell
docker compose -f .config/docker-compose.yml down
```

This removes the containers and Compose network but preserves the Bench files
and named volumes. The next `up --detach --wait` recreates the containers.

## Files and persistence

| Data                 | Location or storage                                              | Persists after `down` |
| -------------------- | ---------------------------------------------------------------- | --------------------- |
| Repository files     | Host repository, mounted at `/workspace`                         | Yes                   |
| Bench, apps, sites   | `development/<BENCH_NAME>`                                       | Yes                   |
| MariaDB data         | Compose-managed `mariadb-data` named volume                      | Yes                   |
| Redis state          | Replaceable container storage                                    | No                    |

Do not delete only the Bench directory or only the MariaDB volume. A site needs
both its files and its database.

## Work with apps

The default quick start creates a framework-only Frappe Bench and does not
require an `apps.json` file.

To include ERPNext in a brand-new environment, update `.config/apps.json`:

```json
[
  {
    "url": "https://github.com/frappe/erpnext.git",
    "branch": "version-16"
  }
]
```

Then add its container path to `.config/.env` before the first start:

```dotenv
APPS_JSON=/workspace/.config/apps.json
```

The real manifest is ignored by Git. `.config/apps.example.json` is a neutral
tracked sample containing `[]`. The real file must use the format accepted by
`bench init --apps_path`.

`APPS_JSON` applies only when the Bench is first created. Changing the variable
or file later does not alter an existing Bench automatically.

## Restore a development backup

Provide either the source-site origin or a specific database-backup URL. With
an origin, the script discovers the newest downloadable database backup. The
restore replaces the selected local site's database, runs migrations, and
verifies the installed apps:

```shell
docker compose -f .config/docker-compose.yml exec --user frappe --env HOME=/home/frappe --workdir /workspace/development/frappe-bench frappe /workspace/development/restore-backup.sh https://source.example.com
```

Authenticated downloads use `FRAPPE_API_TOKEN` from the ignored
`.config/.env` file. Set `SOURCE_SITE_URL` to discover and restore its latest
backup automatically, or set `BACKUP_URL` to select a specific backup.
`BACKUP_URL` takes precedence. The script records a digest to avoid restoring
again on every container restart, and resets the local Administrator password
to `ADMIN_PASSWORD` afterward. It validates the archive before replacing the
database and removes temporary files afterward.

For an existing Bench, open a development shell and use Bench directly:

```shell
cd frappe-bench
bench get-app --branch version-16 https://github.com/example/my_app.git
bench --site development.localhost install-app my_app
```

Use matching branches for Frappe and its apps. For SSH Git URLs, Compose mounts
the host SSH `config` and `known_hosts` files read-only and forwards the host
agent socket. Authentication remains in the agent; private key files are not
mounted. Ensure the required key is visible in `ssh-add -l` before starting.

## Use VS Code Dev Containers

VS Code is optional and uses the same Compose project:

1. Install the
   [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).
2. Open the repository folder in VS Code.
3. Run **Dev Containers: Reopen in Container** from the Command Palette.

The Compose file declares the project name `frappe_development`, so VS Code and
host Compose commands use the same containers regardless of the checkout
directory. Override `COMPOSE_PROJECT_NAME` in `.config/.env` when you
need multiple isolated development environments.

VS Code attaches to the `frappe` service and opens `/workspace/development`.
The checked-in configuration preserves the Compose bootstrap command. Copy
`development/vscode-example` to `development/.vscode` if you want the example
launch and task configurations.

The Dev Container configuration uses `shutdownAction: none`, so rebuilding,
reopening, or closing the VS Code window does not stop the Compose project.
Stop it explicitly with the command in [Stop without deleting data](#stop-without-deleting-data)
when it is no longer needed.

See [Debugging](02-debugging.md) for debugger setup.

## Update the environment

After pulling repository changes, update images and reconcile the services:

```shell
docker compose -f .config/docker-compose.yml pull
docker compose -f .config/docker-compose.yml up --detach --wait
```

The bootstrap preserves existing Bench and site state. It does not switch the
branch of an existing Bench, install newly added apps, run migrations, or reset
passwords automatically. Perform those upgrades explicitly with Bench after
reviewing the relevant Frappe upgrade instructions and taking a backup.

## Troubleshooting

### The startup command exits before Frappe is healthy

Inspect status and the Frappe logs:

```shell
docker compose -f .config/docker-compose.yml ps
docker compose -f .config/docker-compose.yml logs --tail=300 frappe
```

The first installation can be slow while apps and dependencies download. The
Frappe health check allows up to 30 minutes for initial setup.

### A host port is already allocated

Set unused ports in `.config/.env`, then run the quick-start command
again:

```dotenv
HTTP_PORT=8010
SOCKETIO_PORT=9010
```

Open the configured HTTP port, such as `http://localhost:8010`.

### Docker reports a permission error on Linux

Confirm the Docker daemon is running and follow Docker's
[Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/)
to grant your user access. Log out and back in after changing group membership.

### MariaDB rejects the configured password

Use the `DB_PASSWORD` that initialized the existing volume. Updating `.env`
does not change MariaDB credentials already stored in the volume.

### The bootstrap says the Bench directory is invalid

The selected `development/<BENCH_NAME>` exists but does not contain both
`apps/` and `sites/`. Inspect or move that directory instead of deleting it;
it may contain work that should be recovered.

### Containers need access to another local service

See [Connecting to local services](03-local-services-connection.md).

## Reset the environment

Use `down` without `--volumes` for normal container recreation. A full reset is
destructive and should be rare.

To reset everything:

1. Stop the environment.

   ```shell
   docker compose -f .config/docker-compose.yml stop
   ```

2. Move `development/<BENCH_NAME>` outside the repository as a recoverable
   backup. Do not move it while the services are running.
3. Remove the containers and all Compose-managed volumes.

   ```shell
   docker compose -f .config/docker-compose.yml down --volumes
   ```

4. Run the quick-start command to create a new environment.

`down --volumes` permanently removes MariaDB data for the selected Compose
project. Confirm the active `COMPOSE_PROJECT_NAME` before running it. Keep any
Bench backup outside `development/<BENCH_NAME>`, because that directory must be
absent for a clean bootstrap.

## Security and host-specific features

The default passwords are intentionally convenient for local use. Published
ports may be reachable from other machines depending on Docker and firewall
configuration. Use strong credentials on shared networks and never use this
stack as a production deployment.

GPU access and other private host files are not mounted by the portable
baseline. SSH routing uses read-only host configuration and authentication is
forwarded through the agent socket; raw SSH private keys remain on the host.
Keep backup API tokens in the ignored `.config/.env` file, never in an
app manifest or committed configuration.

## Further reading

- [Choosing a deployment or development method](../01-getting-started/01-choosing-a-deployment-method.md)
- [Debugging](02-debugging.md)
- [Connecting to local services](03-local-services-connection.md)
- [macOS company development setup](04-macos-development.md)
- Installer options from inside the `frappe` container:

  ```shell
  cd /workspace/development
  python installer.py --help
  ```
