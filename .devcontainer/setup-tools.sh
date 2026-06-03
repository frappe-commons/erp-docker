#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="${HOME:-/home/frappe}"
CODEX_VERSION="${CODEX_VERSION:-0.133.0}"
TOKENSAVE_VERSION="${TOKENSAVE_VERSION:-6.1.2}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/workspace}"
WORKSPACE_FOLDER="${WORKSPACE_FOLDER:-/workspace/development}"

export HOME="$HOME_DIR"
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

if ! command -v npm >/dev/null 2>&1 && [ -s "$HOME/.nvm/nvm.sh" ]; then
	# shellcheck disable=SC1091
	. "$HOME/.nvm/nvm.sh"
	nvm use default >/dev/null 2>&1 || nvm use node >/dev/null 2>&1 || true
fi

mkdir -p "$HOME/.local/bin" "$HOME/.codex" "$HOME/.tokensave" "$HOME/.gemini/antigravity" "$HOME/.cargo" "$HOME/.rustup"
for user_dir in "$HOME/.local" "$HOME/.codex" "$HOME/.tokensave" "$HOME/.gemini" "$HOME/.cargo" "$HOME/.rustup"; do
	if [ "$(stat -c '%u:%g' "$user_dir")" != "$(id -u):$(id -g)" ]; then
		sudo chown -R "$(id -u):$(id -g)" "$user_dir"
	fi
done

if [ -f "$HOME/.codex-host-auth.json" ]; then
	cp "$HOME/.codex-host-auth.json" "$HOME/.codex/auth.json"
	chmod 600 "$HOME/.codex/auth.json"
fi

if ! command -v codex >/dev/null 2>&1 || ! codex --version 2>/dev/null | grep -q "codex-cli ${CODEX_VERSION}"; then
	npm install -g "@openai/codex@${CODEX_VERSION}"
fi

if ! command -v cargo >/dev/null 2>&1; then
	curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal
fi

# shellcheck disable=SC1091
. "$HOME/.cargo/env"

if ! command -v tokensave >/dev/null 2>&1 || ! tokensave --version 2>/dev/null | grep -q "tokensave ${TOKENSAVE_VERSION}"; then
	cargo install tokensave --version "$TOKENSAVE_VERSION"
fi

rm -f "$HOME/.local/bin/tokensave"
ln -s "$HOME/.cargo/bin/tokensave" "$HOME/.local/bin/tokensave"

tokensave install --agent codex
tokensave install --agent antigravity

for project_dir in "$WORKSPACE_ROOT" "$WORKSPACE_FOLDER"; do
	if [ ! -d "$project_dir" ]; then
		continue
	fi

	if [ -f "$project_dir/.tokensave/tokensave.db" ]; then
		(cd "$project_dir" && tokensave sync)
	else
		(cd "$project_dir" && tokensave init)
	fi
done
