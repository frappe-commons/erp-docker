#!/usr/bin/env bash
set -euo pipefail

headroom_container_bin=${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}
headroom_executable="$headroom_container_bin/headroom"
headroom_proxy_url=http://127.0.0.1:8787
headroom_proxy_log=/tmp/headroom-proxy.log
headroom_proxy_pid_file=/tmp/headroom-proxy.pid

if [ ! -x "$headroom_executable" ]; then
  printf 'Headroom is not available at %s\n' "$headroom_executable" >&2
  exit 1
fi

if curl --fail --silent --show-error --connect-timeout 1 \
  "$headroom_proxy_url/livez" >/dev/null 2>&1; then
  exit 0
fi

headroom_proxy_pid=
if [ -r "$headroom_proxy_pid_file" ]; then
  read -r headroom_proxy_pid <"$headroom_proxy_pid_file" || true
  case $headroom_proxy_pid in
    '' | *[!0-9]*) headroom_proxy_pid= ;;
  esac
fi

if [ -z "$headroom_proxy_pid" ] || ! kill -0 "$headroom_proxy_pid" 2>/dev/null; then
  nohup "$headroom_executable" proxy \
    --host 127.0.0.1 \
    --port 8787 \
    --mode cache \
    --backend openai \
    --no-telemetry \
    >"$headroom_proxy_log" 2>&1 &
  headroom_proxy_pid=$!
  printf '%s\n' "$headroom_proxy_pid" >"$headroom_proxy_pid_file"
fi

# The first launch may import/load compression models from the mounted uv
# environment, which is noticeably slower than subsequent warm starts.
for headroom_probe_attempt in {1..300}; do
  if curl --fail --silent --show-error --connect-timeout 1 \
    "$headroom_proxy_url/livez" >/dev/null 2>&1; then
    exit 0
  fi
  sleep 0.2
done

printf 'Headroom proxy failed to start; see %s\n' "$headroom_proxy_log" >&2
exit 1
