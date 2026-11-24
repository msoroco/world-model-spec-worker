# testing__C150098__LVMC-11-52-130-A4__motor_vehicle_driver

Status: partial eleven-case hydrant construction and saved-source audit. No recording or physical acceptance is claimed.

Exact law: LVMC 11.52.130(A)(4) — No person shall stop, stand or park a vehicle except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device, in any of the following places: Within the following distances of any fire hydrant, whether or not the location is posted with a sign, whether or not the adjacent curb or roadway surface is painted red, and whether the location is on public or private property: (a) At a location where parallel parking is permitted, fifteen feet; (b) At a location where angle parking is permitted or no parking is permitted, twenty feet.
Assigned branch(es): Parallel parking permitted: fifteen feet.
Cell: C150098 (one_way_road, park, fire_hydrant); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## CPU construction and measurement

- `hydrant.py` defines 11 exact planned case suffixes: 15-foot below/at/above on both sides of the hydrant, stop/stand/park activity, and traffic-conflict/police/device-direction exception sources. The 15-foot engineering reference is 4.572 m; requested side gaps 4.422, 4.572 and 4.722 m are coverage targets, not accepted measurements or a legal distance convention.
- The constructor requires a source-identified physical hydrant (mapped object or spawned prop), actual readback of identity/geometry/presence, location-specific parallel-parking permission, one-way approach, curb/map/jurisdiction/vehicle/camera hashes, and source-bound exception directions. It creates the ego vehicle and route through a lazy adapter and destroys owned objects on failure. It does not substitute a mark, sign or data flag for a physical hydrant.
- `measure_original_history` computes the original body-edge longitudinal gap from continuous 20 Hz frames, with fixed hydrant/map/parking-authority joins, activity and exception source checks. It preserves the measured gap and leaves the legally controlling distance convention unresolved. `saved_audit.py` requires SHA256-sealed original site and history files and a complete 900-frame history by default; it rejects altered, short or site-mismatched inputs.
- `case-plan.json` now maps 11 cases to four comparisons: upstream and downstream boundary triples, stop/stand/park, and lawful exception source changes. The exported evidence inventory is empty. The 20-foot angle/no-parking alternative is a distinct parking-authority branch and remains for binding review; the selected C150098 branch is parallel parking permitted. Property status, signs and red paint are explicit context, not removal conditions.

## Next CPU actions

1. Bind the physical hydrant, parking authority, curb, municipality and one-way roadway to reviewed map/source bytes. Build exact per-case runner/configuration and four-camera 20 Hz acquisition with original body footage, then execute offline construction checks.
2. Add canonical semantic proposals, source-bound positive/negative compatibility, process-saved proof for each case, independent delivery and comparison audits, and risk-based fallbacks where the physical placement or visibility risk remains concrete.
3. Independently check whether 20-foot angle/no-parking alternatives are assigned to another compatible cell; do not treat this 15-foot construction as covering them.
4. Rerun the exact scoped strict gate after CPU completion. The current source-shaped tests do not establish physical placement, camera pixels or legal status.

## Proven checks and dependency boundary

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150098__LVMC-11-52-130-A4__motor_vehicle_driver/tests -v` passed 7 focused tests (`cpu-tests.log`, SHA256 `ace35bf5b0f25dfe9acc6a0849be172aa5a454cf104d3c3d148146ed8d8563ec`). Assignment static check passed (`static-check.log`, SHA256 `b58a6b3ec95a71efe450573b6f47324ee828532b70d3ee16310afe9850b36b13`). Exact `.venv-cpu/bin/python worker_check.py --assignment testing__C150098__LVMC-11-52-130-A4__motor_vehicle_driver --complete --require-delivery-ready` exited 1 in `strict-check.log`: partial/missing packages remain. These tests prove only software construction and source rejection branches. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
