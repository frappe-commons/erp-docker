#!/usr/bin/env bash
set -euo pipefail

repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
environment_file="$repository_root/.config/.env"

read_setting() {
	local name=$1
	[ -r "$environment_file" ] || return 0
	sed -n "s/^${name}=//p" "$environment_file" | tail -n 1
}

agent_tools_enabled=$(read_setting ENABLE_HOST_AGENT_TOOLS)
compose_project=$(read_setting COMPOSE_PROJECT_NAME)
compose_project=${compose_project:-$(basename "$repository_root")}
unit_project=${compose_project//[^a-zA-Z0-9_.-]/-}
unit_name="devcontainer-lms-${unit_project}"

case $agent_tools_enabled in
	1 | true | yes | on) ;;
	*)
		systemctl --user stop "$unit_name.service" >/dev/null 2>&1 || true
		exit 0
		;;
esac

lms_cli=$(read_setting HOST_LMS_CLI_SOURCE)
lms_cli=${lms_cli:-$HOME/.lmstudio/bin/lms}
if [ ! -x "$lms_cli" ]; then
	printf 'LM Studio bridge skipped: %s is not executable.\n' "$lms_cli" >&2
	exit 0
fi

lmstudio_home=$(cd "$(dirname "$lms_cli")/.." && pwd)
server_info="$lmstudio_home/.internal/http-server.json"
if [ ! -r "$server_info" ]; then
	printf 'LM Studio bridge skipped: start the LM Studio service first.\n' >&2
	exit 0
fi

bridge_port=$(read_setting HOST_LMS_BRIDGE_PORT)
bridge_port=${bridge_port:-41235}
api_bridge_port=$(read_setting HOST_LMS_API_BRIDGE_PORT)
api_bridge_port=${api_bridge_port:-41234}
api_port=$(read_setting HOST_LMS_API_PORT)
api_port=${api_port:-1234}
docker_cli=$(command -v docker)
python_cli=$(command -v python3)

systemctl --user stop "$unit_name.service" >/dev/null 2>&1 || true
systemctl --user reset-failed "$unit_name.service" >/dev/null 2>&1 || true
systemd-run --user --quiet --collect \
	--unit "$unit_name" \
	--property Restart=on-failure \
	--property RestartSec=2 \
	-- "$python_cli" "$repository_root/.devcontainer/lms-bridge.py" host \
	--control-port "$bridge_port" \
	--api-bridge-port "$api_bridge_port" \
	--api-port "$api_port" \
	--project "$compose_project" \
	--docker "$docker_cli" \
	--info "$server_info"
