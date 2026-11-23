# testing__C227749__LVMC-11-30-050__pedestrian

Status: **partial**. No physical crossing or legal verdict has been established. Exact law: LVMC 11.30.050. Frozen accepted evidence inventory is empty; the witness is conditional and unverified.

## Coverage and construction checkpoint

`case-plan.json` now has five exact authored cases: `outside_right_angle`, `outside_shortest_endpoint`, `outside_neither`, `outside_endpoint_detour`, and `inside_crosswalk_oblique`, with three controlled comparisons. The two outside-crosswalk alternatives are disjunctive: either a right-angle route or the shortest route to a finite opposite curb. The outside detours probe neither, and the matching oblique route with an authored crosswalk polygon probes the exception. No statutory numeric tolerance or legal conclusion is assigned. The case source and Native map facts remain to be verified.

`cases/*/scene.json` has explicit finite starting/opposite curbs, complete route, authored crosswalk polygon, control context, and separate provenance notes. `crossing_geometry.py` computes route length, curb angle, nearest opposite-curb point and excess path length, checks polygon overlap, and measures original Native walker histories. `native_controller.py` lazily spawns the pedestrian with readback and requests waypoint motion without claiming the actor followed it. `delivery_audit.py` independently rejects missing original walker frames, non-20 Hz cadence, missing camera joins and missing four-camera source declarations. `comparison_audit.py` rejects undeclared changes between planned pair scenes. These audits are structural CPU code; they do not decode actual video or establish physical visibility.

## CPU proof

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C227749__LVMC-11-30-050__pedestrian/tests -v` passes 19 tests; retained log `cpu-tests.log` SHA256 0215763b5d21118448a314d83090bc659a943302afcfe8aa4d56d1af0361a3ad.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C227749__LVMC-11-30-050__pedestrian/prove_geometry.py` passes all five authored route targets; retained `geometry-proof.log` SHA256 586843cf048d190719b70cfdd5830694557a624877563396566afae931719393. This proves authored geometry only.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C227749__LVMC-11-30-050__pedestrian --complete` and the same command with `--require-delivery-ready` are rerun below. Strict readiness remains dependent on the unfinished package; do not promote status.

## Exact next CPU work

1. Bind curbs, marked and unmarked crosswalks, roadway extent, municipal jurisdiction/public use and governing devices to original map/site source packets. Replace authored planning geometry only after preserving exact case and comparison intentions. The cell is `plausible_ungrounded`; map suitability remains unverified.
2. Finish the 20 Hz, four-camera Native runner using the shared capture, original body vertices, frame map, sealed acquisition, failure preservation and world restore. Test fake CARLA creation and original-source joins. Include physical risk triggers and at most two tested engineering fallbacks where needed.
3. Add canonical semantic stage proposals, exact per-case construction/config/measurement bundles, source-hashed diagnostics, offline and positive/negative compatibility checks, saved-only finalization, full independent delivery audit and exact comparison proof receipts. Run exact assignment strict check until it passes.

Remaining GPU checks after CPU preparation: actual walker motion, source geometry and controls, full video visibility, realized path and physical completion. These do not excuse the CPU work above.
