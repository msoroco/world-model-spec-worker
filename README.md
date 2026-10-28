# Standalone demo-test preparation trial v2
Read START_HERE.md to manually initiate the lead agent. There are 22 assignments across four partitions (6/6/5/5). No GPU or upstream repository is available to the worker. No trial is launched by this repository.

Checks before starting: `python3 worker_check.py`, `python3 -m unittest discover -s tests`, then each example `runner.py --check` and `python3 -m unittest discover -s examples/<name>/tests`.

The examples contain successful historical construction/case/result references with CPU checks; their native assumptions and endpoint restrictions must be adapted, not inherited. Historical provenance strings are not operational prerequisites. Target software and capture helper sources are supplied in runtime/.

Return branch: worker/demo-test-preparation-v2. All statuses are validated; ready is executable first-run readiness, not physical or statutory acceptance. The lead explicitly runs each returned --check and tests. No tests start a simulator.

Updates: inspect UPDATE.md and run `python3 update_status.py`; follow unseen numbered notices at safe checkpoints. Explicit resume releases pauses. Commit work before merging origin/main; do not force-push. Only the lead handles Git.
