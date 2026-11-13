# Held-out worker batch

This branch contains 51 CPU preparation assignments, frozen law/cell inputs, and a pinned runtime. Read [AGENT_PROMPT.md](AGENT_PROMPT.md), [START_HERE.md](START_HERE.md), `FULL_BRANCH_CONTRACT.md`, `DELIVERY_CONTRACT.md`, and `batch.json`. The worker prepares runnable CARLA constructions and saved-processing proofs; the local GPU workflow later checks native motion, camera pixels, and accepted recordings.

## Start the agent

```bash
git clone --branch worker/held-out-delivery --single-branch \
  https://github.com/msoroco/world-model-spec-worker.git scenario-worker-held
cd scenario-worker-held
scripts/run-worker.sh
```

The launcher defaults to GPT-6-sol with medium reasoning. For GPT-6.1-sol with low reasoning, use `WORKER_CODEX_MODEL=gpt-6.1-sol WORKER_CODEX_REASONING=low scripts/run-worker.sh`. It checks Git identity and a dry-run push before invoking Codex. A separate timer commits and pushes changed `work/` files about every 15 minutes; its log is in ignored `.runtime-work/worker-run.*/checkpoint.log`. The agent itself should not run Git.

## What counts as ready

A successful `scripts/run-worker.sh` exit shows that Codex and the final checkpoint ended; it does **not** establish GPU readiness. The worker must run exact offline and compatibility checks, saved-processing checks, assignment-scoped gates, and `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`. Inspect `work/` results and proof hashes before local GPU intake.

For each assignment, prove one primary selected case through saved processing first, then prove its three distinct fallbacks and comparison cases. Diagnostic fixtures must contain all four named camera streams. Required observation channels must be reproducible from retained raw sources; fixture-only derived `channels/` are insufficient. Keep generated diagnostic media under ignored `.runtime-work/`. After changing construction or finalization code, rerun the affected proofs and bind current hashes.

Continue independent CPU work after partial checkpoints. Record exact failures and resume commands for genuine blockers. The worker does not run CARLA or claim physical or legal acceptance.

## Resume after runtime repair

Resume the existing 51 assigned items from their latest pushed work. Preserve the exact assigned inventory; do not add candidate assignments. The launcher puts generated CPU files under ignored `.runtime-work/`; keep `runtime/` frozen. Finish and strictly check one assignment at a time before marking it ready. Some prior ready labels have stale fixture receipts; rerun and rebind their exact proofs or mark them partial with the concrete diagnosis.
