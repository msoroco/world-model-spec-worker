# NRS 484B.407, C129731: partial CPU checkpoint

The exact law concerns a turn to proceed in the opposite direction on a curve or on the approach to or near a crest of grade, where an approaching driver from either direction cannot see the turning vehicle within 500 feet. The assigned cell is `mountain_road` / `u_turn` / `other_vehicle` with a motor vehicle driver. The fixed 500 foot boundary is 152.4 meters. Do not infer an actual driver's sight line or a legal verdict from the pinned virtual-observer proxy.

`case-plan.json` proposes six exact cases: below, at and above the boundary at a curve, and the same three probes near a crest. The two comparison groups keep the U-turn site, controller, weather, traffic and capture contract fixed within each group. Both approach directions must be inventoried for every case. `inputs/testing__C129731__NRS-484B-407__motor_vehicle_driver/evidence.json` lists no accepted recordings, so no reuse is claimed. All six cases remain planned and unconstructed.

`visibility_measure.py` is a CPU-only measurement helper. It checks both approach inventories, source references and station validity, then preserves obstruction and clearance samples without filling unsampled intervals. It does not make a continuous visibility or legal claim. Its three tests pass in `cpu-tests.log` (hash in `result.json`).

## Next CPU work

1. Build the first curve case end to end. Construct actual curve/occluder geometry and both approach routes in `runner.py`, with synchronized raw source packets and four named cameras. Implement a U-turn controller and a saved finalizer using the pinned runtime's `st.sight_distance` proxy. Test map geometry and both direction lanes with CPU fakes. Match the common camera and duration contract for linked cases.
2. Run exact `runtime.py offline`, `runtime.py compatibility` positive/negative, and `runtime.py process-saved` for that primary case. Retain only textual sources, logs and hashes under this assignment; generated media belongs in `.runtime-work/`.
3. Extend the five other exact cases and three distinct fallback constructions per selected case, each with a measurable physical-risk trigger and invariant capture/comparison conditions. Complete semantic proposals, measurement contracts, independent delivery/comparison audits, saved-processing proofs and branch coverage/review. Rebind hashes after changes.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C129731__NRS-484B-407__motor_vehicle_driver --complete --require-delivery-ready`, then the batch strict gate after all assignments are ready.

## Environment limit

`.venv-cpu/bin/python runtime.py preflight` currently exits 1 at missing `numpy`. The pinned pip install failed because the package index could not be reached. `ffmpeg`, `ffprobe` and `lake` are absent from PATH. A working package index or local wheel mirror and those tools are required for exact runtime proofs; rerun the pinned install and preflight when available. This does not excuse the unfinished CPU construction and audit work. Physical realization remains unverified.
