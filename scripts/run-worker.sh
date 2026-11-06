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
  'Create an active Goal for this thread: complete CPU delivery preparation for all 253 full-train assignments and finish with a passing strict delivery gate. If a genuinely external blocker remains, identify its exact tested cause, continue independent assignments, and return truthful partial status. If Goals are unavailable, continue the task and report that limitation.
Read AGENT_PROMPT.md, DELIVERY_CONTRACT.md, batch.json, the eight partitions, and work/_shared/RETURN-REPORT.md. Resume the existing work without restarting proven steps. The current return has 253 blocked assignments, no selected delivery cases or dispatchable GPU queue rows, and a pending statutory branch matrix. Existing offline and synthetic v1 prototypes are implementation seeds; promote only cases with the exact pinned delivery proofs.
Finish training__C329610__NRS-484B-400-2a__motor_vehicle_driver as the first complete CPU delivery package before starting another draft assignment, unless a precise tested capability blocker prevents it. For each selected case supply primary plus three distinct law-preserving fallbacks with source-based measurable triggers, exact offline and positive/negative portable compatibility proofs, saved processing and Core/Lean/video fixtures, independent delivery audit, controlled comparison, canonical commands, and a queue row. Actual CARLA behavior, original pixels, physical trigger observations, and accepted recordings are later GPU checks. Do not demand those real observations before CPU delivery readiness; test the trigger logic and saved path on synthetic CPU fixtures and state physical limitations honestly.
Complete the statutory branch review and every remaining assignment. Continue repairing worker-owned failures rather than stopping at another audit or the first failing gate. Mark a package ready only when all required CPU proofs pass. Run the ordinary tests and python3.11 worker_check.py --complete --require-delivery-ready without a special PYTHONPATH, repair affected work and rerun proofs until the gate passes. If a frozen checker defect appears, record its exact reproducer and continue unaffected work. Do not run CARLA, access NERSC or campaign SQLite, edit frozen inputs/runtime/batch.json, or claim accepted recordings. The separate timer publishes Git checkpoints; do not commit or push from the agent.' || codex_status=$?

touch "$run_dir/codex-exited"
echo "Codex exited ($codex_status); waiting up to $interval seconds for the next scheduled Git checkpoint."
wait "$checkpoint_pid"
echo "Checkpoint log: $run_dir/checkpoint.log"
if [[ "$(cat "$run_dir/last-checkpoint-status" 2>/dev/null || true)" != published ]]; then
  echo 'Final scheduled Git checkpoint failed; inspect the log and local commits' >&2
  exit 1
fi
exit "$codex_status"
