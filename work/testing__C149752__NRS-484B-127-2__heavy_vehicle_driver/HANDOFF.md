# testing__C149752__NRS-484B-127-2__heavy_vehicle_driver

Status: partial construction and measurement draft. Nine exact draft cases and seven comparisons are proposed; none has a runtime delivery receipt or physical recording.

Exact law: NRS 484B.127(2) — The driver of any truck or combination of vehicles 80 inches or more in overall width, which is following a truck, or combination of vehicles 80 inches or more in overall width, shall, whenever conditions permit, leave a space of 500 feet so that an overtaking vehicle may enter and occupy such space without danger, but this shall not prevent a truck or combination of vehicles from overtaking and passing any vehicle or combination of vehicles. This subsection does not apply to any vehicle or combination of vehicles while moving on a highway on which there are two or more lanes available for traffic moving in the same direction.
Assigned branch(es): Qualifying truck following.
Cell: C149752 (one_way_road, overtake, truck); actor: heavy_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 1. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 19. Bounds are training coverage targets, not legal cutoffs.

## Original inventory actions, superseded by the checkpoint below

The actions recorded at the inventory stage are tracked in the 2026-11-23 checkpoint below. It gives the current implementation and exact remaining CPU work.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 19 exact law/actor ranges. These are unmeasured construction targets. 6 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-23 construction and source-bound audit checkpoint

`case-plan.json` now proposes the exact cases `gap_below_500ft`, `gap_at_500ft`, `gap_above_500ft`, `passing_completion`, `entering_vehicle`, `two_available_lanes`, `lead_below_80in`, `subject_below_80in`, and `conditions_constrained` under this assignment ID. Seven comparisons isolate measured gap, passing, entering, available lanes, each truck width, and surrounding conditions. The 500-foot case uses exactly 152.4 m as an authored target; original-frame measurement decides where a realized case falls. The 80-inch subject and lead boundaries are 2.032 m. No engineering epsilon is a legal cutoff. The exact legal judgment for “whenever conditions permit” and “without danger” remains unresolved.

`truck_following.py` implements source-gated, lazy Native adapter calls: it requires a public-highway map readback, connected straight route, measured lane availability from directional lane inventory, Native blueprint IDs/classes and width readback before spawning the two trucks. Passing and entering cases call separate pass-phase and entrant adapter operations. It also audits a byte-sealed, exact-case 900-frame original Native packet, all eight projected body vertices per vehicle, independently mesh-verified widths, 20 Hz frame/time continuity, full per-frame map lane inventory, distinct third-vehicle occupation of the finite gap, and ordered opposing/ahead/returned pass phases. The comparison audit rejects missing source seals, incomplete frames, fixed-condition drift and absent declared differences. These outputs are measurements, not a legal verdict or accepted delivery.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C149752__NRS-484B-127-2__heavy_vehicle_driver/tests -v` passed six tests; log `cpu-tests.log` SHA-256 `e77364b6fc56b578fddfbe4e41324b515819f64ab23ca905f50a611c5dfb2ef1`. Positive and negative CPU tests cover the construction adapter, source identity/hash, complete frames, mesh-width verification, lane count versus directional geometry, gap and entry measurement, pass ordering and comparison drift. `.venv-cpu/bin/python runtime.py preflight` passed in this session. `.venv-cpu/bin/python worker_check.py --assignment testing__C149752__NRS-484B-127-2__heavy_vehicle_driver --complete` passed after the draft plan was written.

The accepted recording `4d5906ccea56cb0afcb9af93a6a2d466e7a8b3fa5ec452442826e7b7b1022b97` remains reviewed at exported metadata level only. Its original video/trace are absent here, so the 840-frame metadata cannot establish widths, following interval, actual lane count, completed pass, gap-entry danger or branch coverage. The 19 source-hashed judgment-range targets in `judgment-probe-plan.json` remain unmeasured; six endpoint limits are retained.

Next CPU integration: bind the adapter to the pinned capture/restore API and resolve an actually compatible map for the one-way overtaking cell, especially a pass path with only one same-direction lane; then provide exact per-case runner/config/construction bundles, semantic proposals, diagnostic sources, offline and positive/negative compatibility receipts, saved-only postprocessing, independent delivery audits and comparison receipts. The passing case has a specific map/path risk and needs a reviewed source-gated fallback only if that risk is shown on a selected map. Keep these gaps as unfinished preparation, not a GPU dependency. The strict assignment gate is expected to fail while status is partial.

Final checks for this checkpoint: `check-complete.log` records exit 0 from the exact assignment `--complete` gate. `check-strict.log` records exit 1 from the exact assignment `--complete --require-delivery-ready` gate with `Preparation acceptance failed: partial/missing packages remain`. All nine returned files are UTF-8, below 2 MiB, and have no trailing whitespace or conflict marker lines. Status remains partial.
