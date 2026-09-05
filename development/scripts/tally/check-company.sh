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
artifact_dir="${TALLY_ARTIFACT_DIR:-$project_root/test-artifacts/tally/$stamp-company}"
mkdir -p "$artifact_dir"
request="$artifact_dir/request.xml"
response="$artifact_dir/response.xml"
cat > "$request" <<'XML'
<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>ReadonlyCompanies</ID></HEADER>
  <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES><TDL><TDLMESSAGE>
    <COLLECTION NAME="ReadonlyCompanies">
      <TYPE>Company</TYPE>
      <FETCH>Name,GUID,StartingFrom,BooksFrom,EndingAt</FETCH>
    </COLLECTION>
  </TDLMESSAGE></TDL></DESC></BODY>
</ENVELOPE>
XML
printf 'curl --fail --silent --show-error --header Content-Type:\ text/xml\;charset=utf-8 --data-binary @%q %q/\n' "$request" "$base_url" > "$artifact_dir/command.txt"
curl --fail --silent --show-error --max-time 30 \
    --header 'Content-Type: text/xml; charset=utf-8' --data-binary "@$request" "$base_url/" > "$response"
xmllint --noout "$response"
count="$(xmllint --xpath 'count(/*[local-name()="ENVELOPE"]/*[local-name()="BODY"]/*[local-name()="DATA"]/*[local-name()="COLLECTION"]/*)' "$response")"
[[ "$count" != "0" ]] || { echo "Tally is reachable but exposes no open company" >&2; exit 1; }
xmllint --xpath '/*[local-name()="ENVELOPE"]/*[local-name()="BODY"]/*[local-name()="DATA"]/*[local-name()="COLLECTION"]/*/@NAME' "$response" 2>/dev/null || true
echo
echo "Loaded-company check OK ($count company record(s)); artifacts: $artifact_dir"
