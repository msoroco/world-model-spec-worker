# Supplemental import validation path proposal

The current assignment exists at `work/testing__C394554__NRS-484B-280-1c__motor_vehicle_driver/assignment.json`, as required for an additional branch binding. The frozen `portable.validate_imports(repo, aid)` instead reads `inputs/<aid>/assignment.json`. The original `inputs/` tree has no supplemental assignment, so any truthful attempt to mark this package ready reaches `FileNotFoundError` before the remaining ready checks run. The direct reproduction is in `portable-import-nov27c.log`.

Minimal runtime change for the runtime maintainer:

1. In `worker_exchange/portable.py`, accept an optional assignment source path in `validate_imports`, and read that path when provided. Keep the existing `inputs/<aid>/assignment.json` fallback for ordinary callers.
2. In `worker_exchange/preparation.py`, pass the already resolved `assignment_path(repo, aid, item)` to `validate_imports`.

This uses the same source identity that `preparation.check` already uses for the supplemental plan and result hash. It does not relax import allowlisting or require an input-tree copy. After a pinned runtime refresh, rerun the assignment's CPU tests and exact `worker_check.py --assignment testing__C394554__NRS-484B-280-1c__motor_vehicle_driver --complete --require-delivery-ready` before changing its status.
