# Portable scenario preparation

This clean v6 Git batch carries four current-split demo-test partitions, 22 frozen law/cell assignments, a pinned portable runtime, accepted training implementation references, case measurement examples, and the worker gate. Read [START_HERE.md](START_HERE.md). The operator starts the agent manually.

Implementation belongs in `work/<assignment-id>/`. Inputs and baseline runtime are frozen. Portable repairs use `work/_shared/runtime-overlay/` and `overlay.py`. Generated diagnostic media belong in ignored `.runtime-work/`. The worker prepares and tests cases without CARLA, NERSC or campaign SQLite. Local GPU execution and physical acceptance happen later.
