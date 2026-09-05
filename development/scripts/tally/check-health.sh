#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
base_url="${TALLY_BASE_URL:-}"
if [[ -z "$base_url" && -f "$project_root/.env.local" ]]; then
    base_url="$(sed -n 's/^TALLY_BASE_URL=//p' "$project_root/.env.local" | tail -1)"
fi
base_url="${base_url%/}"
[[ -n "$base_url" ]] || { echo "TALLY_BASE_URL is not set" >&2; exit 2; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
artifact_dir="${TALLY_ARTIFACT_DIR:-$project_root/test-artifacts/tally/$stamp-health}"
mkdir -p "$artifact_dir"
printf 'curl --fail --silent --show-error %q/\n' "$base_url" > "$artifact_dir/command.txt"
curl --fail --silent --show-error --max-time 10 "$base_url/" | tee "$artifact_dir/response.txt"
tr -d '\r' < "$artifact_dir/response.txt" | grep -Eq '^(<RESPONSE>)?TallyPrime Server is Running(</RESPONSE>)?$' || {
    echo "Unexpected Tally health response" >&2
    exit 1
}
echo
echo "Tally health OK; artifacts: $artifact_dir"
