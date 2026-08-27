#!/usr/bin/env bash
set -euo pipefail

host_cli_root=/opt/host-cli
host_cli_bin=${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}
host_loader="$host_cli_root/lib/ld-linux-x86-64.so.2"

mkdir -p "$host_cli_bin"
find "$host_cli_bin" -mindepth 1 -maxdepth 1 -delete

# Preserve the host's normal precedence. Every executable gets a stable path,
# including NVM packages whose version directory changes after an upgrade.
shopt -s nullglob
nvm_bins=("$host_cli_root"/nvm/versions/node/*/bin)
source_dirs=()
codex_host_executable=
headroom_host_executable=
lms_host_executable=
host_agent_tools_enabled=false
case ${ENABLE_HOST_AGENT_TOOLS:-0} in
  1 | true | yes | on) host_agent_tools_enabled=true ;;
esac
if [ "${#nvm_bins[@]}" -gt 0 ]; then
  # NVM normally puts one selected version on PATH. Pick the newest mounted
  # version so stale installations cannot shadow newly installed global CLIs.
  mapfile -t nvm_bins < <(printf '%s\n' "${nvm_bins[@]}" | sort -Vr)
  source_dirs+=("${nvm_bins[0]}")
fi
source_dirs+=("$host_cli_root/cargo/bin" "$host_cli_root/local/bin" "$host_cli_root/lmstudio")

for source_dir in "${source_dirs[@]}"; do
  [ -d "$source_dir" ] || continue
  for executable in "$source_dir"/*; do
    [ -x "$executable" ] || continue
    name=${executable##*/}
		if [ "$name" = codex ]; then
			if [ "$host_agent_tools_enabled" = true ]; then
				[ -n "$codex_host_executable" ] || codex_host_executable=$executable
			fi
			continue
		fi
		if [ "$name" = headroom ]; then
			if [ "$host_agent_tools_enabled" = true ]; then
				[ -n "$headroom_host_executable" ] || headroom_host_executable=$executable
			fi
			continue
		fi
		if [ "$name" = lms ]; then
			if [ "$host_agent_tools_enabled" = true ]; then
				[ -n "$lms_host_executable" ] || lms_host_executable=$executable
			fi
			continue
		fi
		if [ "$host_agent_tools_enabled" = false ] && [ "$name" = tokensave ]; then
			continue
		fi
    [ -e "$host_cli_bin/$name" ] && continue

    if [ -x "$host_loader" ] && file -Lb "$executable" | grep -q '^ELF '; then
      printf '#!/usr/bin/env bash\nexec %q --library-path %q %q "$@"\n' \
        "$host_loader" "$host_cli_root/lib" "$executable" >"$host_cli_bin/$name"
      chmod 0755 "$host_cli_bin/$name"
    else
      ln -s "$executable" "$host_cli_bin/$name"
    fi
  done
done

# uv tool entry points use an absolute host-Python shebang. Run Headroom with
# that interpreter through the mounted host loader so it remains usable when
# the container image has an older glibc than the host.
if [ -n "$headroom_host_executable" ]; then
  headroom_host_interpreter=$(head -n 1 "$headroom_host_executable")
  headroom_host_interpreter=${headroom_host_interpreter#\#!}
  if [ -x "$headroom_host_interpreter" ]; then
    headroom_wrapper=$(mktemp "$host_cli_bin/.headroom.XXXXXX")
    if [ -x "$host_loader" ] && file -Lb "$headroom_host_interpreter" | grep -q '^ELF '; then
      printf '#!/usr/bin/env bash\nexec %q --library-path %q %q %q "$@"\n' \
        "$host_loader" "$host_cli_root/lib" "$headroom_host_interpreter" \
        "$headroom_host_executable" >"$headroom_wrapper"
    else
      printf '#!/usr/bin/env bash\nexec %q %q "$@"\n' \
        "$headroom_host_interpreter" "$headroom_host_executable" >"$headroom_wrapper"
    fi
    chmod 0755 "$headroom_wrapper"
    mv -f "$headroom_wrapper" "$host_cli_bin/headroom"
  fi
fi

# LM Studio's control and OpenAI-compatible servers listen on host loopback.
# Wrap the mounted CLI with container-local forwards and isolated client state.
if [ -n "$lms_host_executable" ]; then
	lms_wrapper=$(mktemp "$host_cli_bin/.lms.XXXXXX")
	{
		printf '#!/usr/bin/env bash\nset -euo pipefail\n'
		printf 'lms_host_command=('
		# The bundled Bun executable relies on argv[0], so it must be invoked
		# directly rather than through the mounted dynamic loader.
		printf '%q ' "$lms_host_executable"
		printf ')\n'
		cat <<'LMS_WRAPPER'

source /workspace/.devcontainer/ensure-lms-bridge.sh
exec "${lms_host_command[@]}" "$@"
LMS_WRAPPER
	} >"$lms_wrapper"
	chmod 0755 "$lms_wrapper"
	mv -f "$lms_wrapper" "$host_cli_bin/lms"
fi

# The shared Codex config points its OpenAI provider and Headroom MCP server at
# localhost:8787. Run an equivalent proxy in the container so those settings,
# compression, and retrieval behavior stay consistent with the host.
if [ -x "$host_cli_bin/headroom" ]; then
  bash /workspace/.devcontainer/ensure-headroom.sh
fi

# The host Codex config is mounted for shared authentication and preferences,
# but its absolute MCP executable paths are not valid in the container. Wrap
# Codex with container-only overrides instead of modifying the host config.
if [ -n "$codex_host_executable" ]; then
  codex_wrapper=$(mktemp "$host_cli_bin/.codex.XXXXXX")
  {
    printf '#!/usr/bin/env bash\nset -euo pipefail\n'
    printf 'codex_host_command=('
    if [ -x "$host_loader" ] && file -Lb "$codex_host_executable" | grep -q '^ELF '; then
      printf '%q ' "$host_loader" --library-path "$host_cli_root/lib" "$codex_host_executable"
    else
      printf '%q ' "$codex_host_executable"
    fi
    printf ')\n'
    cat <<'CODEX_WRAPPER'

codex_container_bin=${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}
codex_container_sandbox=${CODEX_CONTAINER_SANDBOX:-danger-full-access}
export PATH="$PATH:$codex_container_bin"

if command -v headroom >/dev/null 2>&1; then
  bash /workspace/.devcontainer/ensure-headroom.sh
fi

codex_working_dir=$PWD
codex_arguments=("$@")
for ((codex_argument_index = 0; codex_argument_index < ${#codex_arguments[@]}; codex_argument_index++)); do
  case ${codex_arguments[$codex_argument_index]} in
    -C | --cd)
      if ((codex_argument_index + 1 < ${#codex_arguments[@]})); then
        codex_working_dir=${codex_arguments[$((codex_argument_index + 1))]}
      fi
      ;;
    --cd=*)
      codex_working_dir=${codex_arguments[$codex_argument_index]#--cd=}
      ;;
  esac
done

codex_tokensave_enabled=false
if codex_repository_root=$(git -C "$codex_working_dir" rev-parse --show-toplevel 2>/dev/null) &&
  [ -r "$codex_repository_root/.tokensave/tokensave.db" ] &&
  command -v tokensave >/dev/null 2>&1; then
  codex_tokensave_enabled=true
fi

codex_headroom_enabled=false
if command -v headroom >/dev/null 2>&1 &&
  curl --fail --silent --show-error --connect-timeout 1 \
    http://127.0.0.1:8787/livez >/dev/null 2>&1; then
  codex_headroom_enabled=true
fi

exec "${codex_host_command[@]}" \
  --sandbox "$codex_container_sandbox" \
  -c 'mcp_servers.headroom.command="headroom"' \
  -c 'mcp_servers.headroom.args=["mcp","serve","--proxy-url","http://127.0.0.1:8787"]' \
  -c "mcp_servers.headroom.enabled=$codex_headroom_enabled" \
  -c 'mcp_servers.tokensave.command="tokensave"' \
  -c 'mcp_servers.tokensave.args=["serve"]' \
  -c "mcp_servers.tokensave.enabled=$codex_tokensave_enabled" \
  "$@"
CODEX_WRAPPER
  } >"$codex_wrapper"
  chmod 0755 "$codex_wrapper"
  mv -f "$codex_wrapper" "$host_cli_bin/codex"
fi

# TokenSave uses ~/.tokensave directly. Keep its writable host state available
# while leaving the rest of the host home unmounted.
if [ ! -e /home/frappe/.tokensave ]; then
  ln -s "$host_cli_root/state/tokensave" /home/frappe/.tokensave
fi

legacy_shell_hook='export PATH="${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}:$PATH"'
bashrc_tmp=$(mktemp)
awk -v line="$legacy_shell_hook" '$0 != line' /home/frappe/.bashrc >"$bashrc_tmp"
mv "$bashrc_tmp" /home/frappe/.bashrc

# Keep the image's Python, Node, Yarn, and Bench toolchain ahead of host CLIs.
# Commands absent from the image (for example codex and tokensave) still fall
# through to the bridged directory.
shell_hook='export PATH="$PATH:${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}"'
if ! grep -Fqx "$shell_hook" /home/frappe/.bashrc; then
  printf '\n%s\n' "$shell_hook" >>/home/frappe/.bashrc
fi
