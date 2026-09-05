#!/bin/sh
set -eu

if [ "$#" -gt 2 ]; then
  echo "Usage: restore-backup.sh [SOURCE_SITE_URL_OR_BACKUP_URL] [SITE]" >&2
  exit 64
fi

db_root_password=${DB_ROOT_PASSWORD:-${DB_PASSWORD:-}}
: "${db_root_password:?Set DB_ROOT_PASSWORD or DB_PASSWORD}"

backup_source=${1:-${SOURCE_SITE_URL:-}}
bench_dir=${BENCH_DIR:-$PWD}
site=${2:-}

if [ -z "$backup_source" ]; then
  echo "Provide a source site URL, backup URL, or SOURCE_SITE_URL" >&2
  exit 64
fi

if [ ! -f "$bench_dir/sites/common_site_config.json" ]; then
  echo "BENCH_DIR is not a Frappe bench: $bench_dir" >&2
  exit 66
fi

if [ -z "$site" ]; then
  site=$(python -c 'import json,sys; print(json.load(open(sys.argv[1])).get("default_site", ""))' "$bench_dir/sites/common_site_config.json")
fi

if [ -z "$site" ] || [ ! -f "$bench_dir/sites/$site/site_config.json" ]; then
  echo "Could not resolve a valid target site" >&2
  exit 66
fi

restore_tmp=$(mktemp -d /tmp/frappe-restore.XXXXXX)
trap 'rm -rf "$restore_tmp"' EXIT HUP INT TERM
archive=$restore_tmp/database.sql.gz
sql_file=$restore_tmp/database.sql

case "$backup_source" in
  http://* | https://*) ;;
  *)
    echo "Source must be an HTTP(S) URL: $backup_source" >&2
    exit 64
    ;;
esac

case "$backup_source" in
  *.sql.gz | *.sql.gz\?*)
    backup_url=$backup_source
    ;;
  *)
    if [ -z "${FRAPPE_API_TOKEN:-}" ]; then
      echo "FRAPPE_API_TOKEN is required to discover backups" >&2
      exit 78
    fi

    source_origin=$(printf '%s\n' "$backup_source" | sed -n 's#^\(https\{0,1\}://[^/]*\).*$#\1#p')
    if [ -z "$source_origin" ]; then
      echo "Could not resolve source origin: $backup_source" >&2
      exit 64
    fi

    backups_page=$restore_tmp/backups.json
    curl --fail --location --show-error --silent --retry 5 --retry-all-errors \
      -H "Authorization: token $FRAPPE_API_TOKEN" \
      --output "$backups_page" \
      "$source_origin/api/method/frappe.desk.desk_page.getpage?name=backups"

    backup_path=$(python -c '
import json, re, sys
with open(sys.argv[1], encoding="utf-8") as source:
    response = json.load(source)
scripts = "\n".join(doc.get("script", "") for doc in response.get("docs", []))
paths = sorted(set(re.findall(r"href=\"(/backups/[^\"?]*\.sql\.gz)\"", scripts)), reverse=True)
print(paths[0] if paths else "")
' "$backups_page")
    if [ -z "$backup_path" ]; then
      echo "No downloadable database backup found for $source_origin" >&2
      exit 69
    fi
    backup_url="$source_origin$backup_path"
    echo "Using latest database backup from $source_origin"
    ;;
esac

if [ -n "${FRAPPE_API_TOKEN:-}" ]; then
  curl --fail --location --show-error --silent --retry 5 --retry-all-errors \
    -H "Authorization: token $FRAPPE_API_TOKEN" --output "$archive" "$backup_url"
else
  curl --fail --location --show-error --silent --retry 5 --retry-all-errors \
    --output "$archive" "$backup_url"
fi

restore_input=$archive
if ! gzip -t "$archive" 2>/dev/null; then
  set +e
  gzip -cd "$archive" > "$sql_file"
  gzip_status=$?
  set -e
  if [ "$gzip_status" -ne 0 ] && ! grep -q '^-- Dump completed on ' "$sql_file"; then
    echo "Backup is truncated or invalid" >&2
    exit 65
  fi
  if ! sed -n '1,20p' "$sql_file" | grep -q 'MySQL dump' || ! tail -n 20 "$sql_file" | grep -q '^-- Dump completed on '; then
    echo "Extracted SQL lacks a complete MySQL dump header/footer" >&2
    exit 65
  fi
  restore_input=$sql_file
fi

cd "$bench_dir"
bench --site "$site" restore "$restore_input" --force --mariadb-root-password "$db_root_password"
bench --site "$site" migrate
bench --site "$site" set-admin-password "${ADMIN_PASSWORD:-1212}"
bench --site "$site" list-apps
