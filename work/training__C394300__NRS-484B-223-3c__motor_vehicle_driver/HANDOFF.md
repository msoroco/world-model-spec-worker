# training__C394300__NRS-484B-223-3c__motor_vehicle_driver

Status: blocked. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.223(3)(c). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

merge before versus after 50 ft. Compare only `center_turn_lane_distance_after_left_turn` (ft) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 3 case definitions are unselected and have no observed values.

## Blocker and resumption

Strict recipe-backed v2 compatibility, Native physical feasibility, exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

## Saved CPU measurement draft

`native/measure_after_turn.py` measures an interval between the sampled end of a left turn from a distinct connector road into the center lane and the first full-body contact with the adjacent through lane. It requires a later full-body through-lane merge and hashes the original Native sample and geometry sources. Eight CPU tests cover the 45/50/55-foot boundary probes and reject wrong turn direction, missing original samples, interrupted center-lane travel, absent merge onset, absent complete merge, invalid frame order, and overlapping lane identities. `prove-draft-measurements.py` saved three source-hashed synthetic receipts; `audit-draft-measurements.py` independently checked source hashes, common approach frames, 20 Hz timing, fixed road/lane context, and threshold relations. The 50-foot interval remains unresolved. Authored lane bounds and synthetic pose transitions are diagnostics only: Native lane designation, CARLA feasibility, pinned offline/compatibility, saved Core processing, and acceptance audits remain unproven. All cases remain unselected and blocked.

The subsequent construction corrected the Native left-turn sign against the existing C394300 left-turn convention. `native/geometry.py` now authors an OpenDRIVE inbound road, left-turn connector and highway center/through lanes, with three routes that share the turn and vary only the requested merge station. CPU geometry checks cover XML links, route continuity, pavement and prospective body containment; an independent saved audit checks the common prefix and ordered merge stations. Three exact-source-row measurement contracts pass the pinned validator. Synthetic saved positives and missing-Native-source negatives pass for all three, with independent report/source-hash auditing. The authored map and routes are not CARLA physical evidence, exact four-candidate compatibility, or Core delivery acceptance.

`native/runner.py`, `controller.py`, `engineering.py` and `cameras.py` now form an unexecuted original-Native capture proposal. Three cases each have a primary plus fallbacks for inbound start, lookahead and camera framing, tied to measured original-body/turn-time, route-error and independent pixel-visibility thresholds. All twelve exact unselected bundles pass pinned offline with fourteen tests each; source/hash and controlled-input audits pass. The after-turn measurement was corrected to separate connector-to-highway transition from first full-body center-lane completion, and all synthetic receipts, contracts and bundle tests were rerun. All twelve unselected bundles now pass exact pinned v1 package positive and packaged missing-Native-source negative diagnostics on full-resolution synthetic 480-frame fixtures. An independent audit verifies the twelve receipts, fixture/implementation/runtime hashes, source-video decodes, Core conversion/render and negative logs (`draft-package-probe-summary.json`). These are diagnostic v1 proofs with retained graph templates; strict recipe-backed v2 receipts, scenario-specific physical CARLA evidence and independent delivery acceptance remain missing. Status and selected counts remain unchanged.

## Strict v2 fixture capability reproduction

The source/status reproducer at `work/training__C10014__NRS-484B-477-2__motor_vehicle_driver/reproduce-v2-fixture-limit.py` passes and records a 3-row pinned retained base for trace, frame map, evidence, and Native frames. This assignment needs 480 frames; `fixture_recipe.inspect` rejects a portable addition that replaces a pinned source with `Fixture addition shadows pinned source`. Log SHA-256: `f20eb84cf0cadbf412c915503b7d9c30f2fb724beb8c72b6766f4521d205b937`. See `v2-fixture-capability-blocker.json` in the C10014 assignment for the exact remedy. This does not establish physical execution or satisfy other CPU delivery requirements; the assignment stays blocked and unselected.
