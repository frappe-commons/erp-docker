# Development configuration

The Dev Container uses two local configuration files:

```text
.config/.env
.config/apps.json
```

Both files are ignored by Git. Place the provided files at those exact paths,
open the repository in a Dev Container, and wait for Bench setup to finish.
The Rebuild and Reopen progress view streams the detailed setup log.
The Bench directory is always `frappe-bench` and its site is always `localhost`.
Each app keeps Bench's `upstream` remote and also gets an `origin` remote that
fetches all branches, so standard `git switch <branch>` workflows work.
Before creating Bench, setup checks that every configured app repository and
branch/tag is accessible non-interactively through the forwarded host SSH agent
and mounted host SSH configuration. Fixing host Git/SSH access and rebuilding
is therefore required before any installation work begins.
Bench does not start automatically; run it from the container terminal:

```sh
cd /workspace/development/frappe-bench
bench start
```

Neutral samples are provided as `.config/.env.example` and
`.config/apps.example.json`. The real files keep the same base names without
`.example` and remain ignored.

When `.config/.env` defines `SOURCE_SITE_URL` and
`FRAPPE_API_TOKEN`, restore the newest downloadable database backup before
starting Bench:

```sh
cd /workspace/development/frappe-bench
/workspace/development/restore-backup.sh
```

To discover and restore the latest backup automatically during initial setup,
define the source site and API token:

```dotenv
SOURCE_SITE_URL=https://source.example.com
FRAPPE_API_TOKEN=key:secret
```

To restore a specific backup instead, define:

```dotenv
ADMIN_PASSWORD=1212
BACKUP_URL=https://source.example.com/backups/database.sql.gz
```

`BACKUP_URL` takes precedence over `SOURCE_SITE_URL`. The selected source is
restored once and its digest is recorded locally so container restarts do not
overwrite later database changes. Changing the configured source triggers one
new restore. When a backup is configured, setup creates only the base site
before restoring, so custom apps are initialized from the backup rather than
against an empty database. After restoration, the local Administrator password
is set to `ADMIN_PASSWORD`.
