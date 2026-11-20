#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if [[ $# -ne 2 || ! "$1" =~ ^[0-9]+$ ]] || (( 10#$1 < 1 )); then
  echo 'Usage: auto-checkpoint.sh INTERVAL_SECONDS RUN_DIRECTORY' >&2
  exit 2
fi
interval="$1"
run_dir="$2"
log="$run_dir/checkpoint.log"
while sleep "$interval"; do
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if scripts/checkpoint.sh "$timestamp" >> "$log" 2>&1; then
    printf 'published\n' > "$run_dir/last-checkpoint-status"
  else
    printf 'failed\n' > "$run_dir/last-checkpoint-status"
  fi
  if [[ -e "$run_dir/codex-exited" ]]; then
    exit 0
  fi
done
