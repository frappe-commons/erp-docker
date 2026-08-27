#!/usr/bin/env bash
set -euo pipefail

bridge_port=${LMS_HOST_BRIDGE_PORT:-41235}
api_bridge_port=${LMS_HOST_API_BRIDGE_PORT:-41234}
api_port=${LMS_API_PORT:-1234}
runtime_dir=${XDG_RUNTIME_DIR:-/tmp}/srv-lms-bridge
pid_file="$runtime_dir/pid"
log_file="$runtime_dir/bridge.log"
lms_container_home=${LMS_CONTAINER_HOME:-/home/frappe/.host-lmstudio-client}
lms_internal_dir="$lms_container_home/.lmstudio/.internal"
lms_key_source=/opt/host-cli/lmstudio/lms-key-2
lms_server_config_source=/opt/host-cli/lmstudio/http-server-config.json
info_file="$lms_internal_dir/http-server.json"

if [ ! -r "$lms_key_source" ] || [ ! -r "$lms_server_config_source" ]; then
	printf 'LM Studio control files are not mounted in the container.\n' >&2
	exit 1
fi

mkdir -p "$runtime_dir" "$lms_internal_dir"
ln -sfn "$lms_key_source" "$lms_internal_dir/lms-key-2"
ln -sfn "$lms_server_config_source" "$lms_internal_dir/http-server-config.json"

bridge_running=false
if [ -r "$pid_file" ]; then
	bridge_pid=$(<"$pid_file")
	if kill -0 "$bridge_pid" 2>/dev/null; then
		bridge_running=true
	fi
fi

if [ "$bridge_running" = false ]; then
	nohup python3 /workspace/.devcontainer/lms-bridge.py container \
		--control-port "$bridge_port" \
		--api-bridge-port "$api_bridge_port" \
		--api-port "$api_port" >"$log_file" 2>&1 &
	bridge_pid=$!
	printf '%s\n' "$bridge_pid" >"$pid_file"
fi

bridge_ready=false
for _ in {1..40}; do
	if (exec 3<>"/dev/tcp/127.0.0.1/$bridge_port") 2>/dev/null; then
		exec 3>&-
		bridge_ready=true
		break
	fi
	sleep 0.05
done
if [ "$bridge_ready" = false ]; then
	printf 'LM Studio container bridge did not start; see %s.\n' "$log_file" >&2
	exit 1
fi

info_tmp=$(mktemp "$lms_internal_dir/.http-server.XXXXXX")
printf '{"host":"127.0.0.1","port":%s,"pid":%s}\n' \
	"$bridge_port" "$bridge_pid" >"$info_tmp"
mv -f "$info_tmp" "$info_file"

export HOME=$lms_container_home
export LMS_API_SERVER_INFO_PATH=$info_file
