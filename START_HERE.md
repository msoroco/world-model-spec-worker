# Start here

Read [AGENT_PROMPT.md](AGENT_PROMPT.md), [DELIVERY_CONTRACT.md](DELIVERY_CONTRACT.md), `batch.json`, and the eight `partitions/full-train-*.json` files. This checkout has no selected implementation yet. The lead agent is started manually and delegates eight disjoint partitions.

The worker is CPU-only. It prepares delivery cases and four candidate CARLA constructions per selected case. It does not run CARLA, access NERSC, edit SQLite or accept recordings. All result statuses become `ready`/`delivery_prepared` only after their CPU proofs pass; then run `python3.11 worker_check.py --complete --require-delivery-ready`.

Work autonomously without questions or clarification pauses. Preserve partial/blocked statuses and publish exact logs. The separate timer started by `scripts/run-worker.sh` commits and pushes changed `work/` files every 15 minutes while Codex runs and once at the next scheduled tick after it exits.

The agent does not run Git checkpoints. Inspect `.runtime-work/worker-run.*/checkpoint.log` for timer failures.
