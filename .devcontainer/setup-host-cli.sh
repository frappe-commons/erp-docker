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
if [ "${#nvm_bins[@]}" -gt 0 ]; then
  # NVM normally puts one selected version on PATH. Pick the newest mounted
  # version so stale installations cannot shadow newly installed global CLIs.
  mapfile -t nvm_bins < <(printf '%s\n' "${nvm_bins[@]}" | sort -Vr)
  source_dirs+=("${nvm_bins[0]}")
fi
source_dirs+=("$host_cli_root/cargo/bin" "$host_cli_root/local/bin")

for source_dir in "${source_dirs[@]}"; do
  [ -d "$source_dir" ] || continue
  for executable in "$source_dir"/*; do
    [ -x "$executable" ] || continue
    name=${executable##*/}
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

# TokenSave uses ~/.tokensave directly. Keep its writable host state available
# while leaving the rest of the host home unmounted.
if [ ! -e /home/frappe/.tokensave ]; then
  ln -s "$host_cli_root/state/tokensave" /home/frappe/.tokensave
fi

shell_hook='export PATH="${HOST_CLI_PATH:-/home/frappe/.host-cli/bin}:$PATH"'
if ! grep -Fqx "$shell_hook" /home/frappe/.bashrc; then
  printf '\n%s\n' "$shell_hook" >>/home/frappe/.bashrc
fi
