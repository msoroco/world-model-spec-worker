# Full-train worker

This branch contains the 253 existing full-train assignments and the refreshed CPU runtime. Continue the authored work under `work/`; preserve prior plans and failures, and rerun runtime-dependent proofs before marking an assignment ready. Start with [AGENT_PROMPT.md](AGENT_PROMPT.md) and [START_HERE.md](START_HERE.md).

## Start the agent

```bash
git clone --branch worker/full-train-delivery --single-branch \
  https://github.com/msoroco/world-model-spec-worker.git scenario-worker-full-train
cd scenario-worker-full-train
scripts/run-worker.sh
```

The launcher defaults to GPT-6-sol with medium reasoning. To use GPT-6.1-sol with low reasoning, run `WORKER_CODEX_MODEL=gpt-6.1-sol WORKER_CODEX_REASONING=low scripts/run-worker.sh`.

## Progress and completion

A separate timer commits and pushes changed `work/` files about every 15 minutes; see `.runtime-work/worker-run.*/checkpoint.log` for publication failures. A successful launcher exit means Codex and its final checkpoint ended. **Delivery readiness requires** current case proofs and `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` to pass.

Prove a primary case through saved processing before its fallback sweep. The four named source-camera videos and observation channels derived from retained raw inputs must survive that path. Regenerate affected fallback and comparison proofs after changing construction or finalization code. Keep generated diagnostic media under ignored `.runtime-work/`. The CPU gate does not claim CARLA execution or physical acceptance.

## Resume after runtime repair

The numbered law-field migration preserves all 253 assignments and prior work. Each assignment input now has one canonical `law` object with unchanged text. Old input-bound proofs remain historical; rerun affected checks before readiness. The launcher puts generated CPU files under ignored `.runtime-work/`; keep `runtime/` frozen. Finish and strictly check one assignment at a time; do not wait for the whole batch before recording an individually verified ready result.
