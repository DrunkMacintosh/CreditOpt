#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 API_URL PROJECT_ID REGION WORKER_JOB [--execute-worker]" >&2
  exit 64
}

[[ $# -eq 4 || $# -eq 5 ]] || usage

api_url="${1%/}"
project_id="$2"
region="$3"
worker_job="$4"
execute_worker="${5:-}"

if [[ -n "$execute_worker" && "$execute_worker" != "--execute-worker" ]]; then
  usage
fi

for command_name in curl gcloud python3; do
  command -v "$command_name" >/dev/null || {
    echo "required command is unavailable: $command_name" >&2
    exit 69
  }
done

identity_token="$(gcloud auth print-identity-token --audiences="$api_url")"
[[ -n "$identity_token" ]] || {
  echo "gcloud returned an empty identity token" >&2
  exit 77
}

check_endpoint() {
  local path="$1"
  local expected_status="$2"
  local response

  response="$(curl --silent --show-error --fail --max-time 15 --config - "$api_url$path" <<EOF
header = "Authorization: Bearer $identity_token"
EOF
)"
  RESPONSE="$response" EXPECTED_STATUS="$expected_status" python3 -c '
import json
import os

payload = json.loads(os.environ["RESPONSE"])
if payload.get("status") != os.environ["EXPECTED_STATUS"]:
    raise SystemExit(f"unexpected health response: {payload!r}")
'
}

check_endpoint "/api/v1/health" "ok"
check_endpoint "/api/v1/ready" "configuration-valid"
unset identity_token

gcloud run jobs describe "$worker_job" \
  --project="$project_id" \
  --region="$region" \
  --format=json >/dev/null

if [[ "$execute_worker" == "--execute-worker" ]]; then
  gcloud run jobs execute "$worker_job" \
    --project="$project_id" \
    --region="$region" \
    --wait
fi

echo "Cloud smoke checks passed for API health and worker Job visibility."
