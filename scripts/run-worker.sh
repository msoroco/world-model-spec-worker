#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
branch=worker/full-train-delivery

if [[ "$(git branch --show-current)" != "$branch" ]]; then
  echo "expected branch $branch" >&2
  exit 2
fi
command -v codex >/dev/null || { echo 'codex command not found' >&2; exit 2; }
git var GIT_AUTHOR_IDENT >/dev/null || { echo 'Git author identity is missing' >&2; exit 2; }
git var GIT_COMMITTER_IDENT >/dev/null || { echo 'Git committer identity is missing' >&2; exit 2; }
git remote get-url --push origin >/dev/null || { echo 'Git origin push remote is missing' >&2; exit 2; }
GIT_TERMINAL_PROMPT=0 git push --dry-run origin "$branch" >/dev/null || {
  echo 'Git push preflight failed; resolve authentication or branch divergence before starting Codex' >&2
  exit 2
}

interval="${WORKER_CHECKPOINT_INTERVAL_SECONDS:-900}"
if [[ ! "$interval" =~ ^[0-9]+$ ]] || (( 10#$interval < 1 )); then
  echo 'WORKER_CHECKPOINT_INTERVAL_SECONDS must be a positive integer' >&2
  exit 2
fi
model="${WORKER_CODEX_MODEL:-gpt-6-sol}"
effort="${WORKER_CODEX_REASONING:-medium}"

mkdir -p .runtime-work
run_dir="$(mktemp -d .runtime-work/worker-run.XXXXXXXX)"
trap 'touch "$run_dir/codex-exited"' EXIT
scripts/auto-checkpoint.sh "$interval" "$run_dir" &
checkpoint_pid=$!

codex_status=0
codex exec --approve-for-me -m "$model" -c "model_reasoning_effort=$effort" \
  'Create an active Goal for this thread: complete the full-train-delivery work in AGENT_PROMPT.md and finish with either a passing strict delivery gate or a best-effort return identifying every unresolved blocker. Preserve frozen inputs and truthful readiness statuses. Then read AGENT_PROMPT.md and complete the work assigned in batch.json. Do not edit batch.json. Git checkpoints are published by the separate timer; do not commit or push from the agent. If Goals are unavailable, continue the task and report that limitation.' || codex_status=$?

touch "$run_dir/codex-exited"
echo "Codex exited ($codex_status); waiting up to $interval seconds for the next scheduled Git checkpoint."
wait "$checkpoint_pid"
echo "Checkpoint log: $run_dir/checkpoint.log"
if [[ "$(cat "$run_dir/last-checkpoint-status" 2>/dev/null || true)" != published ]]; then
  echo 'Final scheduled Git checkpoint failed; inspect the log and local commits' >&2
  exit 1
fi
exit "$codex_status"
