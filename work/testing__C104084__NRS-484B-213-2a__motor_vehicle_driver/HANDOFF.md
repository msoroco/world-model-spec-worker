# testing__C104084__NRS-484B-213-2a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.213(2)(a); with 484B.213(3) — A vehicle must not be driven to the left side of the highway at any time: When approaching the crest of a grade or upon a curve in the highway where the driver’s view is obstructed within such distance as to create a hazard in the event another vehicle might approach from the opposite direction. Subsection 2 does not apply upon a one-way highway.
Assigned branch(es): Approaching a crest; obstructed-view condition; one-way exception absent by setup..
Cell: C104084 (hill_crest, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The exact law has separate crest and curve alternatives. This assignment's frozen
`hill_crest` layout supports the crest alternative; the curve alternative needs a
compatible cell binding in the batch-level branch allocation. Subsection 3's
one-way exception is represented as an explicit original lane-allocation case,
not inferred from the absence of an oncoming actor. No numeric hazard-distance
threshold exists in the supplied law, so the judgment remains unlabelled.

`case-plan.json` now lists four exact crest cases: `right_crest_obstructed`,
`left_crest_obstructed`, `left_crest_clear`, and `left_one_way_obstructed`, each
prefixed by this assignment ID. The three comparisons separately vary actual
left-side body motion, sampled crest-ray obstruction, and original one-way lane
allocation. The frozen evidence inventory has zero accepted recordings, so all
four remain planned captures rather than reuse claims. Each case now records its
physical risk: no source-bounded Native map crest or lane-direction packet has
yet been selected. No fallback is claimed without a tested alternate construction.

`crest_geometry.py` requires original waypoint source references, a same-road
opposing lane with opposite direction, aligned stations, and an actual sampled
grade intersecting the declared 1.4 m virtual-observer proxy ray. Its CPU tests
exercise both approach directions, reject a flat grade, and reject wrong lane
orientation or missing provenance. `comparison_audit.py` requires source-bound
packets and rejects missing sources, confounded fixed conditions and missing
planned differences. Its tests cover all three comparisons. These checks are
preparation code and synthetic unit evidence; they are not physical completion,
actual Native raycasts, delivered pixels, or a legal hazard conclusion.

Proof: `.venv-cpu/bin/python -m unittest discover -s work/testing__C104084__NRS-484B-213-2a__motor_vehicle_driver/tests -v` passed six tests in `cpu-tests.log` (hash in `result.json`). `.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete` passed static checks in `assignment-check.log`. The exact strict command with `--require-delivery-ready` failed because this assignment is still partial; see `strict-gate.log`. CPU preflight passed with the pinned environment.

Next worker-owned work: bind a real Native hill-crest map and highway context to
these geometry checks; implement the four exact capture constructions, controller,
measurement/finalization code, source-bound diagnostics and positive/negative
compatibility proofs; author semantic proposals, saved-only processing and
independent delivery audits; then rerun the exact strict gate. The batch lead
owns any shared curve cell binding. Actual CARLA motion, visibility and video
quality remain later physical checks after CPU preparation.

### Native map binding follow-up

`native_map.py` now follows the original CARLA map's connected ego waypoints,
retrieves each adjacent lane waypoint, checks opposing headings, rejects route
termination/branching and road/lane changes, retains original map/road/lane
source references and elevation samples, and requires the sampled grade to
intersect the declared proxy ray. It imports no CARLA module at import time.
The added CPU fake-world tests cover a grade with an opposing lane and reject
flat grade, a same-direction adjacent lane, and a truncated route. All nine
assignment tests pass in the refreshed `cpu-tests.log`. These checks are a
source-gated map-selection implementation; a real CARLA map and actual vehicle
rays have not been exercised on this CPU host. The one-way case still needs a
separate original topology binder and is not certified by this two-way binder.

### One-way exception construction follow-up

`native_map.bind_one_way_crest` now follows an original Native ego lane and a distinct adjacent same-direction lane across the grade. It rejects absent, opposite-heading, changing-lane and flat topology and returns sampled crest-proxy blockers while retaining explicit original public-highway and one-way-authority source requirements. Map topology is only a construction selector, not proof of the subsection 3 legal designation. `comparison_audit.py` rejects a one-way exception packet without an original authority source reference and SHA256. Twelve CPU tests pass in `cpu-tests.log`; the SHA256 is in `result.json`.

Next CPU work: bind an actual original Native map and original highway/one-way authority source; implement exact case capture/controllers, finalizers, diagnostic recipes and positive/negative compatibility, saved-only delivery audits and semantic proposals. The curve alternative still needs the batch lead to bind a compatible curve cell. Actual CARLA raycasts, motion and pixels remain later physical checks.

The refreshed assignment static check (`.venv-cpu/bin/python worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete`) exited 0 in `assignment-check.log`. The exact strict check with `--require-delivery-ready` exited 1 in `strict-gate.log` with `Preparation acceptance failed: partial/missing packages remain`; the package correctly retains `status: partial` until the remaining CPU deliverables and their proofs pass.

### Saved original crest observation follow-up (2026-11-24)

`saved_crest.py` joins byte-hashed original attempt sources for the four exact
crest case IDs: 20 Hz Native body history, original lane/highway context,
per-frame opposing-body corner rays, frame map, and four camera source files.
It rejects a changed or missing source, case/law drift, absent original
opposing-lane or one-way authority binding, frame gaps, ray/frame mismatches,
timestamp drift, and absent actor/body packets. It reports observed left-side
body and ray states, distance range and whether the intended construction
target was observed, while keeping hazard-distance judgment unresolved.
Text-only camera files in the CPU tests prove source binding only; media
decoding and physical pixel visibility are still unimplemented CPU/delivery
work and later physical checks. The one-way authority reference is required
but its external original document has not yet been independently validated.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s
work/testing__C104084__NRS-484B-213-2a__motor_vehicle_driver/tests -v`
passed 17 tests in `cpu-tests.log` (SHA256 in `result.json`). The saved join
is a source-observation component, not a canonical runtime finalizer or
acceptance receipt. Next CPU actions: implement exact Native controller/capture
with guaranteed cleanup and original camera acquisition, connect the saved
join to runtime finalization, build four positive/negative diagnostic recipes,
run offline/compatibility and saved-only delivery audits, and author proposals.
The exact scoped `worker_check.py --assignment testing__C104084__NRS-484B-213-2a__motor_vehicle_driver --complete` passed in `assignment-check.log`; the scoped `--require-delivery-ready` exited 1 in `strict-gate.log` because the package remains partial.
