#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_FOLDER="${WORKSPACE_FOLDER:-/workspace/development}"
BENCH_NAME="${BENCH_NAME:-frappe-bench}"
SITE_NAME="${SITE_NAME:-development.localhost}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
DB_PASSWORD="${DB_PASSWORD:-123}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
PYENV_ROOT="${PYENV_ROOT:-/home/frappe/.pyenv}"

export PYENV_ROOT
export PATH="$PATH:/home/frappe/.local/bin:$PYENV_ROOT/bin:$PYENV_ROOT/shims"

if [ "$(id -u)" -eq 0 ]; then
  workspace_uid="$(stat -c '%u' "$WORKSPACE_FOLDER")"
  workspace_gid="$(stat -c '%g' "$WORKSPACE_FOLDER")"

  # On native Linux, match the host repository owner so generated files stay
  # editable. Docker Desktop virtualizes bind-mount ownership as root, so its
  # containers retain the image's portable frappe user (UID/GID 1000).
  if [ "$workspace_uid" -ne 0 ]; then
    identity_changed=false
    if [ "$workspace_gid" -ne "$(id -g frappe)" ]; then
      if getent group "$workspace_gid" >/dev/null 2>&1; then
        usermod --gid "$workspace_gid" frappe
      else
        groupmod --gid "$workspace_gid" frappe
      fi
      identity_changed=true
    fi
    if [ "$workspace_uid" -ne "$(id -u frappe)" ]; then
      usermod --non-unique --uid "$workspace_uid" frappe
      identity_changed=true
    fi
    if [ "$identity_changed" = true ]; then
      chown -R frappe:"$(id -g frappe)" /home/frappe
    fi
  fi
  exec setpriv \
    --reuid="$(id -u frappe)" \
    --regid="$(id -g frappe)" \
    --init-groups \
    env HOME=/home/frappe LOGNAME=frappe USER=frappe bash "$0"
fi

export NVM_DIR="${NVM_DIR:-/home/frappe/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  nvm use default >/dev/null
fi

bash /workspace/.devcontainer/setup-host-cli.sh

cd "$WORKSPACE_FOLDER"

installer_args=(
  --bench-name "$BENCH_NAME"
  --site-name "$SITE_NAME"
  --frappe-branch "$FRAPPE_BRANCH"
  --db-root-password "$DB_PASSWORD"
  --admin-password "$ADMIN_PASSWORD"
)

if [ -n "${APPS_JSON:-}" ]; then
  installer_args+=(--apps-json "$APPS_JSON")
fi

python installer.py "${installer_args[@]}"

cd "$BENCH_NAME"
echo "Bench setup complete. Run 'cd $WORKSPACE_FOLDER/$BENCH_NAME && bench start' to start it."
exec sleep infinity
