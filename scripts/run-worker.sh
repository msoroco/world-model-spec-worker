#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
branch="$(python3.11 -c 'import json; print(json.load(open("batch.json"))["return_branch"])')"
if [[ "$(git branch --show-current)" != "$branch" ]]; then
  echo "Expected branch $branch" >&2
  exit 2
fi
command -v codex >/dev/null || { echo 'codex command not found' >&2; exit 2; }
git var GIT_AUTHOR_IDENT >/dev/null
git var GIT_COMMITTER_IDENT >/dev/null
GIT_TERMINAL_PROMPT=0 git push --dry-run origin "$branch" >/dev/null
interval="${WORKER_CHECKPOINT_INTERVAL_SECONDS:-900}"
if [[ ! "$interval" =~ ^[0-9]+$ ]] || (( 10#$interval < 1 )); then
  echo 'Invalid checkpoint interval' >&2
  exit 2
fi
mkdir -p .runtime-work/tmp
export TMPDIR="$repo_root/.runtime-work/tmp"
run_dir="$(mktemp -d .runtime-work/worker-run.XXXXXXXX)"
export SCENARIO_PIPELINE_OUTPUT_ROOT="$repo_root/$run_dir/adapter"
scripts/auto-checkpoint.sh "$interval" "$run_dir" &
checkpoint_pid=$!
codex_status=0
codex exec --approve-for-me -m "${WORKER_CODEX_MODEL:-gpt-6-sol}" \
  -c "model_reasoning_effort=${WORKER_CODEX_REASONING:-medium}" \
  'Read START_HERE.md and batch.json. Complete as much assigned CPU preparation as possible without asking questions or pausing for actionable work. Preserve frozen inputs and runtime. The independent timer commits and pushes work; do not run Git yourself. Report exact unresolved blockers and resume actions.' || codex_status=$?
touch "$run_dir/codex-exited"
wait "$checkpoint_pid"
echo "Checkpoint log: $run_dir/checkpoint.log"
if [[ "$(cat "$run_dir/last-checkpoint-status" 2>/dev/null || true)" != published ]]; then
  echo 'Final checkpoint failed; inspect the log and local commits' >&2
  exit 1
fi
exit "$codex_status"
