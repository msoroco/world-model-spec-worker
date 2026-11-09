#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
branch="$(python3.11 -c 'import json; print(json.load(open("batch.json"))["return_branch"])')"
if [[ "$(git branch --show-current)" != "$branch" ]]; then echo "expected branch $branch" >&2; exit 2; fi
command -v codex >/dev/null || { echo 'codex command not found' >&2; exit 2; }
git var GIT_AUTHOR_IDENT >/dev/null
git var GIT_COMMITTER_IDENT >/dev/null
GIT_TERMINAL_PROMPT=0 git push --dry-run origin "$branch" >/dev/null
interval="${WORKER_CHECKPOINT_INTERVAL_SECONDS:-900}"
if [[ ! "$interval" =~ ^[0-9]+$ ]] || (( 10#$interval < 1 )); then echo 'invalid checkpoint interval' >&2; exit 2; fi
model="${WORKER_CODEX_MODEL:-gpt-6-sol}"
effort="${WORKER_CODEX_REASONING:-medium}"
mkdir -p .runtime-work
run_dir="$(mktemp -d .runtime-work/worker-run.XXXXXXXX)"
trap 'touch "$run_dir/codex-exited"' EXIT
scripts/auto-checkpoint.sh "$interval" "$run_dir" &
checkpoint_pid=$!
codex_status=0
codex exec --approve-for-me -m "$model" -c "model_reasoning_effort=$effort"   'Create an active Goal for this thread: complete the CPU preparation in AGENT_PROMPT.md and batch.json, or return a truthful best-effort checkpoint with exact blockers. Read AGENT_PROMPT.md and START_HERE.md. Work autonomously, preserve existing progress, and do not edit frozen inputs, runtime or batch.json. The independent timer handles Git commits and pushes; do not run Git yourself. If Goals are unavailable, continue the task.' || codex_status=$?
touch "$run_dir/codex-exited"
wait "$checkpoint_pid"
echo "Checkpoint log: $run_dir/checkpoint.log"
if [[ "$(cat "$run_dir/last-checkpoint-status" 2>/dev/null || true)" != published ]]; then
  echo 'Final scheduled Git checkpoint failed; inspect the log and local commits' >&2; exit 1
fi
exit "$codex_status"
