# training__C179480__NRS-484B-627-2__motor_vehicle_driver

Status: partial. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.627(2). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

stopped vehicle blocks versus does not block other traffic; necessity separately. Compare only `roadway_stop_blocks_traffic` (bool) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.

## Update058 roadway stop construction checkpoint

`stop_construction.py` now builds parameterized lane-centre blocking and right-shoulder clear stop targets from surveyed widths, retaining the same approaching through-traffic route in both cases. It rejects a shoulder that cannot clear the lane and requires an exact Boolean target. Necessity for safe operation, compliance with law, and actual impediment remain explicit source measurements, never inferred from planned geometry. `.venv-cpu/bin/python -m unittest discover -s work/training__C179480__NRS-484B-627-2__motor_vehicle_driver/tests` passed three tests (`update058-stop-construction-tests.log`). This is a construction component, not an executable CARLA package. Next: bind a verified C179480 map/lane profile, implement the Native runner/controller and four source cameras, select exact statutory cases including exceptions, then perform the primary/fallback offline, compatibility, saved and independent acceptance/comparison proofs. Status stays partial.

Update058 assignment scoped complete static gate passed (`update058-scoped-complete.log`). This does not satisfy delivery readiness; status remains partial.

## Update059 Native control and four-camera component

Added `native_controller.py` with lazy CARLA-facing four RGB source cameras at 20 Hz (1920×1080 overview and three 1280×720 detail streams), cleanup on partial spawn, and measured-pose/velocity stop commands. The controller steers toward an externally surveyed stop transform, brakes from measured speed and resumes approach when short of the stop radius; it does not treat target geometry as proof of actual traffic impediment. `.venv-cpu/bin/python -m unittest discover -s work/training__C179480__NRS-484B-627-2__motor_vehicle_driver/tests` passes six geometry/controller tests (`update059-controller-tests.log`). Pinned `runtime.py preflight` and `worker_check.py --updates` pass (`update059-preflight.log`, `update059-updates.log`).

The current `case-plan.json` still lists only block/nonblock and must expand the safe-operation and legal-compliance exceptions after reviewing the exact frozen law and C179480 cell geometry. The camera/control module is a component: a map-surveyed Native runner, synchronized original telemetry and four videos, source-bound finalizer, measurement contract, three fallback constructions per selected case, and exact offline/compatibility/saved and independent audits are still worker-owned CPU work. Keep result partial.

## Update059 exact-law exception planning and gates

Independent reread of `inputs/training__C179480__NRS-484B-627-2__motor_vehicle_driver/assignment.json` law text found the complete-stop prohibition has distinct safe-operation and compliance-with-law exceptions. `case-plan.json` now retains reference/contrast and adds unselected `__safe_operation_stop` and `__law_required_stop` cases, with exact controlled exception comparisons. A physical other-vehicle hazard and a separately verified governing legal stop requirement must be constructed and measured; the plan makes no legal determination from expected labels. The current C179480 cell has `other_vehicle` control, so the legal-compliance construction must establish compatible governing control or use the branch-allocation process before selection.

After this plan change, scoped complete passed (`update059-branch-scoped-complete.log`); scoped strict exited 1 at partial/missing packages (`update059-branch-scoped-strict.log`). Earlier update059 scoped logs predate this plan edit and are historical. Next: map survey and both exception constructions, then selected exact runner, source telemetry/finalizer and proof matrix. Status remains partial.

## Update059 source measurements and terminal checks

`case-plan.json` now records the frozen conditional witness and empty accepted-recording membership as an explicit evidence review. Each planned case binds roadway-stop, traffic-effect, exception and cell-scope gaps. Observation terms map to separate ego motion, roadway/shoulder grounding, lane footprint, following-vehicle speed/gap, governing-control and exception measurements; expected labels do not establish any of them. `source_measurement.py` reads frame-joined raw actor rows, rejects missing fields or frames, and reports observed stop, lane overlap, following speed drop and minimum gap without inferring normal-and-reasonable impediment, safety necessity or legal compliance. The engineering stop tolerance is 0.05 m/s and is not a statutory threshold.

`.venv-cpu/bin/python -m unittest discover -s work/training__C179480__NRS-484B-627-2__motor_vehicle_driver/tests` passes nine tests (`update059-source-measurement-tests.log`). Final scoped static gate passes (`update059-final-scoped.log`); final scoped strict exits 1 on partial/missing packages (`update059-final-strict.log`). Full strict `timeout 60 ...` exited 124 with empty `update059-full-strict.log`; no new batch gate diagnosis was obtained. The latest completed full strict error supplied by the user names frozen `runtime/pipeline/runs/scenario_pipeline/inputs/shared/manifest.json` as unapproved output; it was not edited. Continue map-surveyed Native runner/telemetry/sealing, exception construction, selected-case/fallback packages, compatibility and saved processing, independent acceptance and comparison audits. Status remains partial.
