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
  'Create an active Goal for this thread: complete the full-train-delivery work across all 253 assignments and finish with a passing strict delivery gate or a best-effort return identifying exact tested external blockers. Preserve truthful readiness statuses. If Goals are unavailable, continue the task and report that limitation.
Read AGENT_PROMPT.md, DELIVERY_CONTRACT.md, batch.json, the eight partitions, and work/_shared/RETURN-REPORT.md. Resume the existing work. The 624 case definitions are unverified drafts, not selected GPU jobs. The plural-branch checker repair is already pinned. First rerun runtime verification, decoder build, and CPU selftest; refresh work/_shared/runtime-proof.json against the current batch runtime manifest. Repair malformed case-plan lists, including the 31 drafts currently missing observations, sources, existing_evidence, or runtime_uncertainties.
Complete training__C329610__NRS-484B-400-2a__motor_vehicle_driver through all required CPU checks as the first full assignment, then complete the other assignments. For every selected case provide primary and three distinct fallbacks with measured triggers, exact offline and positive/negative compatibility proofs, saved processing and independent audits. Complete statutory coverage, controlled comparisons, semantic proposals, measurement contracts, the ordered GPU queue, and synthetic local integration proof. Rerun affected proofs and hashes. Do not run CARLA, access NERSC or campaign SQLite, or claim accepted recordings.
Continue fixing worker-owned failures; do not stop after another gap audit or at the first failing gate, and do not label missing constructions or proofs as external blockers. Continue independent assignments if one fails. Mark ready only after its CPU proofs pass. Run python3.11 worker_check.py --complete --require-delivery-ready at the end. If a frozen checker defect remains, record its exact input, command, and log while continuing unaffected work. Do not edit frozen inputs, runtime, or batch.json. Git checkpoints are published by the separate timer; do not commit or push from the agent.' || codex_status=$?

touch "$run_dir/codex-exited"
echo "Codex exited ($codex_status); waiting up to $interval seconds for the next scheduled Git checkpoint."
wait "$checkpoint_pid"
echo "Checkpoint log: $run_dir/checkpoint.log"
if [[ "$(cat "$run_dir/last-checkpoint-status" 2>/dev/null || true)" != published ]]; then
  echo 'Final scheduled Git checkpoint failed; inspect the log and local commits' >&2
  exit 1
fi
exit "$codex_status"
