#!/usr/bin/env bash
set -euo pipefail

setup_log=/tmp/frappe-bench-setup.log
setup_marker=/tmp/frappe-bench-setup-complete
setup_status=/tmp/frappe-bench-setup-status

while [ ! -f "$setup_log" ] && [ ! -f "$setup_status" ]; do
  sleep 0.2
done

if [ -f "$setup_status" ]; then
  test ! -f "$setup_log" || cat "$setup_log"
  exit "$(cat "$setup_status")"
fi

tail -n +1 --follow=name --retry "$setup_log" &
tail_pid=$!

stop_tail() {
  kill "$tail_pid" 2>/dev/null || true
  wait "$tail_pid" 2>/dev/null || true
}
trap stop_tail EXIT HUP INT TERM

while [ ! -f "$setup_status" ]; do
  sleep 0.5
done

exit "$(cat "$setup_status")"
