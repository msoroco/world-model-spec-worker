Read AGENT_PROMPT.md first. Its completion and scheduling policy supersedes conflicting continuation guidance below.

# Start demo-test-delivery

Use a fresh clone of `worker/demo-test-delivery` after the reviewed cutover is merged. Run `scripts/run-worker.sh` from the repository root. The launcher starts the agent and a separate Git checkpoint timer; inspect `.runtime-work/worker-run.*/checkpoint.log` if publication fails.

The agent must read `AGENT_PROMPT.md`, `DELIVERY_CONTRACT.md`, `FULL_BRANCH_CONTRACT.md`, `batch.json`, its partitions, and `runtime/skills/worker-preparation/SKILL.md`. Continue the 43 assigned packages already in `work/`. Preserve selected case IDs and existing source work. A prior ready label is no longer proof after the runtime refresh; rerun the affected exact CPU checks before restoring it.

Create `.venv-cpu` with Python 3.11 and install `runtime/requirements-cpu.txt` if needed. Check `runtime.py preflight`, then scoped `worker_check.py --assignment ID --complete --require-delivery-ready` as each package is finished. Run the complete strict gate at the end. Generated files stay under ignored `.runtime-work/`; the returned `work/` contains code, plans, hashed logs, and receipts.

This worker performs CPU preparation only. CARLA execution, Native motion, camera pixels, physical acceptance and canonical recording membership remain for the local GPU operator. Do not claim them in the worker return.
