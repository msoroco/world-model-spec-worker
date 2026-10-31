# Start here

Read [AGENT_PROMPT.md](AGENT_PROMPT.md), [DELIVERY_CONTRACT.md](DELIVERY_CONTRACT.md), `batch.json`, and the eight `partitions/full-train-*.json` files. This checkout has no selected implementation yet. The lead agent is started manually and delegates eight disjoint partitions.

The worker is CPU-only. It prepares delivery cases and four candidate CARLA constructions per selected case. It does not run CARLA, access NERSC, edit SQLite or accept recordings. All result statuses become `ready`/`delivery_prepared` only after their CPU proofs pass; then run `python3.11 worker_check.py --complete --require-delivery-ready`.

Work autonomously without questions or clarification pauses. Commit and attempt to push the best-effort return at the end even when the strict gate fails; preserve partial/blocked statuses and publish exact logs.

The lead also publishes progress checkpoints with `scripts/checkpoint.sh`; read the cadence and ownership rules in `AGENT_PROMPT.md`.
