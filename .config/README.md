# Development configuration

The Dev Container uses two local configuration files:

```text
.config/.env
.config/apps.json
```

Both files are ignored by Git. Place the provided files at those exact paths,
open the repository in a Dev Container, and wait for Bench setup to finish.
Bench does not start automatically; run it from the container terminal:

```sh
cd "/workspace/development/$BENCH_NAME"
bench start
```

Neutral samples are provided as `.config/.env.example` and
`.config/apps.example.json`. The real files keep the same base names without
`.example` and remain ignored.

When `.config/.env` defines `SOURCE_SITE_URL` and
`FRAPPE_API_TOKEN`, restore the newest downloadable database backup before
starting Bench:

```sh
cd "/workspace/development/$BENCH_NAME"
/workspace/development/restore-backup.sh
```

To restore a specific backup automatically during initial setup, define:

```dotenv
ADMIN_PASSWORD=1212
BACKUP_URL=https://source.example.com/backups/database.sql.gz
```

The URL is restored once. Its digest is recorded locally so container restarts
do not overwrite later database changes. Changing `BACKUP_URL` triggers one
new restore. After restoration, the local Administrator password is set to
`ADMIN_PASSWORD`.
