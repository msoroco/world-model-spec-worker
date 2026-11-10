# Full-train worker continuation

This branch carries the refreshed CPU runtime and the existing 253 full-train assignments. Read [AGENT_PROMPT.md](AGENT_PROMPT.md), [START_HERE.md](START_HERE.md), [MIGRATION.md](MIGRATION.md), and `batch.json`. Historical drafts and receipts are starting material; rerun runtime-dependent proofs against the current pinned runtime before declaring readiness. CARLA execution and recording acceptance happen later in the local pipeline.

## Which branch to run

`worker/full-train-runtime-refresh` is a **staging branch**. Its `batch.json` names `worker/full-train-delivery` as the return branch, and `scripts/run-worker.sh` enforces that name. Cloning this staging branch and running the launcher directly will stop at the branch check.

After the existing full-train worker has stopped and all work to retain is pushed, promote the staging branch to `worker/full-train-delivery` only if the delivery tip is an ancestor. Do not force-push or discard unpushed work:

```bash
git clone --branch worker/full-train-runtime-refresh --single-branch \
  https://github.com/msoroco/world-model-spec-worker.git scenario-worker-full-train-refresh
cd scenario-worker-full-train-refresh
git fetch origin worker/full-train-delivery:refs/remotes/origin/worker/full-train-delivery
git merge-base --is-ancestor origin/worker/full-train-delivery HEAD || {
  echo 'Branches diverged: reconcile the delivery work before promotion' >&2
  exit 1
}
git push origin HEAD:worker/full-train-delivery
```

If the ancestry check fails, reconcile on a separate branch and recheck the retained work before updating the delivery branch. Once the delivery branch contains the refreshed runtime, start the agent from a fresh checkout:

```bash
git clone --branch worker/full-train-delivery --single-branch \
  https://github.com/msoroco/world-model-spec-worker.git scenario-worker-full-train
cd scenario-worker-full-train
scripts/run-worker.sh
```

The launcher defaults to GPT-6-sol with medium reasoning. To use GPT-6.1-sol with low reasoning, run `WORKER_CODEX_MODEL=gpt-6.1-sol WORKER_CODEX_REASONING=low scripts/run-worker.sh`.

## Progress and completion

The launcher checks Git identity and a dry-run push, then starts a separate timer that commits and pushes changed `work/` files about every 15 minutes. Check `.runtime-work/worker-run.*/checkpoint.log` for publication errors. A successful launcher exit means the Codex process and final checkpoint finished; **it does not mean any assignment is ready**. Readiness requires current assignment proofs and a passing `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` gate.

An isolated test of the refreshed runtime completed one selected case's synthetic speed, conversion, rendering, and saved-processing checks, but did not complete its assignment. The test found a useful order of work: make one primary case pass the full saved-processing path, including all four source views and channels derived from retained raw sources, before running its fallback sweep. After changing construction or finalization code, regenerate every affected fallback, comparison, and receipt; older green logs do not prove the current code. Keep generated diagnostic media under ignored `.runtime-work/`.

Continue CPU work after partial checkpoints. If a genuine blocker or execution limit stops work, preserve the exact failure, affected cases, and next commands in `work/`; do not call a partial checkpoint delivery ready. No CARLA run or physical acceptance is claimed by the CPU gate.
