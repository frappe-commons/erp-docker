#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPOSITORY_ROOT/.config/docker-compose.yml"

usage() {
  cat <<'EOF'
Usage:
  development/dev-env.sh \
    --apps-json PATH \
    --env-file PATH \
    [--site SITE] \
    COMMAND [BACKUP_URL]

Required inputs:
  --apps-json PATH  User-provided Bench app manifest inside this repository
  --env-file PATH   User-provided Compose environment file
  --site SITE       Restore target (default: localhost)

Commands:
  validate          Validate the inputs and Compose configuration
  up                Start the development environment and wait until healthy
  restore-latest    Start and restore from a source site or backup URL
  status            Show container status
  logs              Follow Frappe logs
  stop              Stop containers without deleting data
  help              Show this help

The script never creates, modifies, prints, or commits either input file.
EOF
}

apps_json=""
env_file=""
site_name=localhost
while [ "$#" -gt 0 ]; do
  case "$1" in
    --apps-json)
      [ "$#" -ge 2 ] || { echo "--apps-json requires a path" >&2; exit 64; }
      apps_json=$2
      shift 2
      ;;
    --env-file)
      [ "$#" -ge 2 ] || { echo "--env-file requires a path" >&2; exit 64; }
      env_file=$2
      shift 2
      ;;
    --site)
      [ "$#" -ge 2 ] || { echo "--site requires a name" >&2; exit 64; }
      site_name=$2
      shift 2
      ;;
    help | --help | -h)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

command=${1:-}
[ "$#" -eq 0 ] || shift

resolve_input() {
  local input_path=$1
  local input_dir
  local absolute_path

  input_dir=$(cd "$(dirname "$input_path")" 2>/dev/null && pwd -P) || return 1
  absolute_path="$input_dir/$(basename "$input_path")"
  [ -f "$absolute_path" ] || return 1
  printf '%s\n' "$absolute_path"
}

validate_inputs() {
  if [ -z "$apps_json" ] || [ -z "$env_file" ]; then
    echo "Both --apps-json and --env-file are required." >&2
    usage >&2
    exit 64
  fi

  apps_json=$(resolve_input "$apps_json") || {
    echo "App manifest not found: $apps_json" >&2
    exit 66
  }
  env_file=$(resolve_input "$env_file") || {
    echo "Environment file not found: $env_file" >&2
    exit 66
  }

  case "$apps_json" in
    "$REPOSITORY_ROOT"/*) ;;
    *)
      echo "The app manifest must be inside the repository so Docker can mount it." >&2
      exit 66
      ;;
  esac

  container_apps_json="/workspace/${apps_json#"$REPOSITORY_ROOT"/}"
  export APPS_JSON="$container_apps_json"
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required. Install and start Docker Desktop." >&2
    exit 69
  fi
  docker compose version >/dev/null
}

compose() {
  docker compose --env-file "$env_file" --file "$COMPOSE_FILE" "$@"
}

validate() {
  require_docker
  compose config --quiet
}

restore_latest() {
  local backup_source=${1:-${DEV_BACKUP_URL:-}}
  if ! grep -Eq '^FRAPPE_API_TOKEN=[^:]+:[^:]+$' "$env_file"; then
    echo "The environment file must define FRAPPE_API_TOKEN=key:secret." >&2
    exit 78
  fi

  compose up --detach --wait
  compose exec \
    --user frappe \
    --env HOME=/home/frappe \
    --workdir /workspace/development \
    frappe \
    sh -c \
    'cd -- frappe-bench; exec /workspace/development/restore-backup.sh "$1" "$2"' \
    sh \
    "$backup_source" \
    "$site_name"
}

case "$command" in
  validate)
    validate_inputs
    validate
    printf 'Configuration is valid.\n'
    ;;
  up)
    validate_inputs
    validate
    compose up --detach --wait
    ;;
  restore-latest)
    validate_inputs
    validate
    restore_latest "${1:-}"
    ;;
  status)
    validate_inputs
    require_docker
    compose ps
    ;;
  logs)
    validate_inputs
    require_docker
    compose logs --follow --tail=200 frappe
    ;;
  stop)
    validate_inputs
    require_docker
    compose stop
    ;;
  help | --help | -h)
    usage
    ;;
  "")
    usage >&2
    exit 64
    ;;
  *)
    echo "Unknown command: $command" >&2
    usage >&2
    exit 64
    ;;
esac
