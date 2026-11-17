# training__C177225__NRS-484B-560-7b__bus_driver

Status: partial. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.560(7)(b). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

rail-crossing officer direction obeyed versus not obeyed. Compare only `bus_obeys_officer_direction` (bool) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.

## Update057 first CPU construction slice

`officer_direction.py` implements a deterministic directed-stop controller target for both rail approaches. It requires a named authorized officer, exact bus recipient, crossing, approach direction, issued/governing frame interval, stop line before the near rail, and enough far-side exit space for the 12 m bus. It exposes obey and continue requested controls under the same signal/geometry and does not infer an observed stop or legal verdict. `test_officer_direction.py` verifies both directions, identical fixed context for the two requested behaviors, rejection of mere officer presence/wrong recipient, timing order and bus clearance; all four tests passed in `update057-officer-direction-tests.log`. This is construction code, not yet a selected package or accepted Native observation.

Next CPU actions: map the crossing stations to checked CARLA road/rail geometry and independently recorded Native map readback, make a real officer actor/signal with visible camera coverage and recipient-bound history, integrate this controller into a runner and source packets, then build both selected cases with three distinct risk-triggered fallbacks and run offline, positive/negative compatibility, saved processing, delivery and comparison audits. Preserve the fixed comparison variable `bus_obeys_officer_direction`; do not infer a universal crossing-stop rule or priority for conflicting instructions. Status remains partial.

Update057 scoped static complete check passed (`update057-scoped-complete.log`); this validates the truthful partial checkpoint, not delivery readiness.

## Update058 Native scene and raw observation construction

`native_scene.py` now makes CARLA `spawn_actor` calls for the exact bus blueprint, a named officer actor, two explicit rail assets, and four named source-camera sensors. It checks Native driving-lane waypoints at start and stop, bus length against exit clearance, both approach directions, and destroys partially spawned actors on failure. A specific installed `static.prop.*` rail asset still must be selected and verified against the actual Native world; a prop ID or intended placement alone is not physical crossing evidence. `measure_direction.py` derives value-free stopped-before-line and crossing-entry observations from synchronized raw bus velocity/station, officer direction and video frame-map rows. It rejects missing Native velocity, wrong recipient or crossing/time scope, and unsynchronized frames. It makes no legal verdict and does not consume fixture-provided derived channels. `update058-construction-and-measurement-tests.log` passed 12 tests across controller, actual spawn calls, both directions, cleanup and missing-source negatives. `update058-preflight.log` passed CPU preflight.

The primary selected case is still not integrated into a runnable Native package or pinned offline/saved path. Next: author/verify installed rail geometry and qualifying officer communication in a runnable CARLA scene; retain Native map, actor, signal and four-camera sources; materialize exact reference and contrast constructions with three risk-triggered fallbacks each; run pinned offline, positive/negative compatibility, saved processing, delivery and comparison audits before requesting readiness. Keep C177225 partial.

Update058 final check: added opposite-approach raw observation test. All 13 tests pass in `update058-construction-and-measurement-tests.log`; CPU preflight passes. Scoped static complete passes (`update058-scoped-complete.log`), while scoped strict exits 1 on `Preparation acceptance failed: partial/missing packages remain` (`update058-scoped-strict.log`). Result stays partial.
