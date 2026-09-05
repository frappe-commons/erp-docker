#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_FOLDER="${WORKSPACE_FOLDER:-/workspace/development}"
BENCH_NAME=frappe-bench
SITE_NAME=localhost
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
DB_PASSWORD="${DB_PASSWORD:-123}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-1212}"
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

setup_log=/tmp/frappe-bench-setup.log
setup_marker=/tmp/frappe-bench-setup-complete
setup_status=/tmp/frappe-bench-setup-status
rm -f "$setup_log" "$setup_marker" "$setup_status"
exec > >(tee -a "$setup_log") 2>&1

record_setup_failure() {
  status=$?
  if [ "$status" -ne 0 ]; then
    printf '%s\n' "$status" > "$setup_status"
  fi
}
trap record_setup_failure EXIT

export NVM_DIR="${NVM_DIR:-/home/frappe/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  nvm use default >/dev/null
fi

bash /workspace/.devcontainer/setup-host-cli.sh

cd "$WORKSPACE_FOLDER"

backup_source=${BACKUP_URL:-${SOURCE_SITE_URL:-}}
installer_args=(
  --frappe-branch "$FRAPPE_BRANCH"
  --db-root-password "$DB_PASSWORD"
  --admin-password "$ADMIN_PASSWORD"
)

if [ -n "${APPS_JSON:-}" ]; then
  installer_args+=(--apps-json "$APPS_JSON")
fi
if [ -n "${SITES_JSON:-}" ]; then
  installer_args+=(--sites-json "$SITES_JSON")
fi
if [ -n "${SITES_JSON:-}" ] && [ -n "$backup_source" ]; then
  echo "Ignoring the global backup source in multi-site mode." >&2
  echo "Restore each site explicitly with restore-backup.sh." >&2
  backup_source=""
fi
if [ -n "$backup_source" ]; then
  installer_args+=(--skip-app-install)
fi

python installer.py "${installer_args[@]}"

cd "$BENCH_NAME"

if [ -n "$backup_source" ]; then
  backup_digest=$(printf '%s' "$backup_source" | sha256sum | awk '{print $1}')
  backup_marker="$WORKSPACE_FOLDER/$BENCH_NAME/sites/$SITE_NAME/.development-backup-restore"
  restored_digest=""
  if [ -f "$backup_marker" ]; then
    restored_digest=$(sed -n '1p' "$backup_marker")
  fi

  if [ "$restored_digest" != "$backup_digest" ]; then
    /workspace/development/restore-backup.sh "$backup_source" "$SITE_NAME"
    bench --site "$SITE_NAME" set-admin-password "$ADMIN_PASSWORD"
    printf '%s\n' "$backup_digest" > "$backup_marker"
  else
    echo "Configured backup is already restored; skipping."
  fi
fi

echo "Bench setup complete. Run 'cd $WORKSPACE_FOLDER/$BENCH_NAME && bench start' to start it."
touch "$setup_marker"
printf '0\n' > "$setup_status"
trap - EXIT
exec sleep infinity
