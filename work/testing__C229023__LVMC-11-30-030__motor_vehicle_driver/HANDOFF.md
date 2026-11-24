# testing__C229023__LVMC-11-30-030__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.30.030 — Whenever any vehicle is stopped at a marked crosswalk or at any unmarked crosswalk at an intersection to permit a pedestrian to cross the roadway, the driver of any other vehicle approaching from the rear shall not overtake and pass such stopped vehicle.
Assigned branch(es): Unmarked crosswalk at an intersection.
Cell: C229023 (road, overtake, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229023__LVMC-11-30-030__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 exact-case and saved-source measurement checkpoint

The exact LVMC 11.30.030 text covers a vehicle stopped at a marked crosswalk or an unmarked crosswalk at an intersection to permit a pedestrian to cross, and the rear-approaching driver overtaking and passing it. The frozen witness selects the conditional unmarked branch in broad road cell C229023. `case-plan.json` now preserves six exact targets: unmarked/marked pass and wait, plus unmarked pass and wait with a different lead-stop purpose. Five comparisons isolate pass behavior, crossing kind and stop purpose. No frozen accepted recording exists for this assignment; these are planned targets, not accepted evidence or verdicts. The unmarked branch needs reviewed opposite sidewalk lateral-line and curb/traveled-edge geometry, and divided-roadway intersection rules when applicable.

`crosswalk_measurements.py` reopens hash-sealed original context and trace bytes and rejects diagnostic receipts. It requires an actual road intersection, marked-source or unmarked sidewalk/curb source references, a separate stopped-purpose source, three actor identities, a unit road axis, 20 Hz ordered frames, and eight original world-space body vertices per vehicle. It records sampled rear approach only when ego front is behind lead rear and sampled full pass only when ego rear is ahead of lead front. It also reports stopped lead frames and pedestrian-in-polygon frames separately. It does not infer purpose from the pedestrian motion, establish legal crosswalk applicability, or render a legal judgment. The CLI writes replayable JSON only after successful measurement.

Eight focused CPU tests passed in `cpu-crosswalk-tests.log`, including CLI replay and negative missing geometry, purpose source, marked source, changed bytes, dropped frames, missing vertices and diagnostic provenance. `.venv-cpu/bin/python worker_check.py --assignment testing__C229023__LVMC-11-30-030__motor_vehicle_driver --complete` passed in `assignment-check.log`; exact scoped strict failed because status remains partial in `strict-gate.log`. Proof hashes are current in `result.json`. Next CPU work: source-reviewed Native intersection/crosswalk packet and six executable scene bundles; actor controllers and synchronized four-camera acquisition; case finalization, semantic proposals, exact offline and positive/negative compatibility, saved-only delivery and independent media/comparison audits. Actual physical actor motion and camera visibility remain unverified.

## 2026-11-23 geometry construction checkpoint

`crosswalk_construction.py` now creates an unmarked crossing polygon from opposite sidewalk lateral lines and a curb/traveled-edge source, or accepts a source-marked polygon. It requires a qualifying road intersection rather than an alley junction, positions the lead before the crossing and the ego behind it, routes the pedestrian across the roadway, and builds either a wait route or a laterally clear pass route. It rejects missing sidewalk geometry, an alley junction and inadequate passing clearance. Six new synthetic construction tests bring the package to 14 passing focused tests. The six planned cases now identify this construction tool and the physical geometry risk. A blueprint does not establish an actual map intersection or stopped purpose.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `eeb67c23f65639bb53ba04e322f2a147f100279525c3725d3d64fb76d1e09800` |
| `crosswalk_construction.py` | `89290d61bc3cd82bc4f9116c9f4e3033f0857985fcd46e4f131c4ad90ae16c73` |
| `tests/test_crosswalk_construction.py` | `8c0bc50ba4eb5723448e09c66f7ed96a48cd337d37460c398895b60a2757da00` |
| `preflight.log` | `8d44a451750484a6bb4cee1ff67be8369823709670f3671d968a1c24324bf48f` |
| `cpu-crosswalk-tests.log` | `d90660e0a51a73fd4eeebbb696783c0e949e76f647c85e19cba88d3979adfbe4` |
| `assignment-check.log` | `cc0634d76bab4ebe7685f30ec47975c999d0a86e219581dad0d777a5d29ec680` |
| `strict-gate.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `ec2603c3e9724a3f232e4b8aba0cf2ca3a900d1e8afb2baaf4a99d9467fc294f` |

Pinned preflight, 14 focused tests and scoped static exit 0. Exact scoped strict exits 1 on truthful partial status and is retained here and in `strict-gate.log`, outside successful `result.json.tests` receipts. Next CPU work: bind actual source intersection, sidewalk and crosswalk geometry; implement physical actor controllers, case finalizers and exact bundles; prove positive/negative compatibility, saved-only processing and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.

## 2026-11-24 source-bound crosswalk site construction

`crosswalk_construction.build_sourced` now requires distinct regular source files beside the site packet for the original map, qualifying road intersection, opposite sidewalk geometry, curb/traveled edge and independently observed stopped purpose; marked cases also require original marking source. It verifies their bytes, SHA-256 and citations and binds the site map SHA to the map source before producing the existing geometry and ego/pedestrian routes. Symlinks, missing purpose, altered sidewalk bytes, changed map identity and mismatched curb citation are rejected. This is a custody and consistency guard; source authority, physical intersection status, pedestrian intent and legal applicability remain unreviewed.

All 24 focused tests pass (`cpu-sourced-site-tests.log`), pinned preflight passes (`cpu-sourced-site-preflight.log`), and exact scoped static passes (`cpu-sourced-site-static.log`). The exact scoped strict check exits 1 on truthful partial (`cpu-sourced-site-strict.log`). Commands and SHA-256 receipts are in `result.json`. Next CPU work: integrate a real reviewed Native site packet and six executable scene bundles, actor controllers and synchronized camera capture, semantic proposals, positive/negative compatibility, saved delivery and independent comparison audits.


`case_construction.construct` now selects all six exact case IDs from the fixed plan and requires the sealed stopped-purpose observer source to match each case. It binds crossing kind, ego request, map/source inventory, plan hash and a 20 Hz/900-frame four-camera capture plan, without asserting physical or legal success. A changed observed purpose is rejected. This is a source-bound construction proposal, not a completed Native runner or canonical bundle.


`case_construction.compare_constructions` independently checks the exact ordered plan pair, plan hash, fixed map/capture/pedestrian/source facts and each declared changed dimension. Stop-purpose comparisons may change only the observer source while preserving map, geometry and route; wrong pair and changed original map/pedestrian sources are rejected. These are source-bound construction audits and do not substitute for post-capture observed comparison acceptance.

All five declared construction comparisons now pass their exact source/fixed-condition checks in the focused suite; this remains a construction proof only.

## 2026-11-24 passing footprint construction guard

The passing geometry now requires positive finite site-declared values for ego and combined vehicle half widths, keeps the ego footprint inside the road lateral bounds, and checks lateral clearance against the stopped lead. It rejects an edge lane whose center is inside the road but whose body extends outside. The route is still a proposal; no map, motion or physical crossing is asserted. Twenty-eight focused tests pass in `cpu-road-footprint-tests.log`; the measurement also rejects boolean frame, time, speed and point values and its tests use `.runtime-work/` scratch; scoped static passes in `cpu-road-footprint-static.log`; exact strict exits 1 on truthful partial in `cpu-road-footprint-strict.log`. Reviewed site, Native runner, canonical bundles and saved delivery work remain.

The saved source measurement now rejects an original crossing kind or stopped-purpose claim that differs from the exact case ID, after requiring the appropriate crossing source. A marked-source context cannot be relabeled as an unmarked case, nor can a different stopped purpose be relabeled as pedestrian-permitting. The focused suite includes both negative probes; this is source-consistency checking, not physical or legal acceptance.

## 2026-11-24 synchronized Native source recorder

`native_crosswalk_capture.NativeCrosswalkRecorder` checks three distinct original actor IDs, consecutive Native frame IDs, 20 Hz/900-frame duration, same-tick identities from four cameras, finite centers, eight world-space vehicle vertices and nonnegative measured speeds. It writes a SHA-sealed context, trace, frame map and receipt into a fresh capture directory; the saved crosswalk measurement reopened the full 900-frame CPU fixture. This adapter is a join and custody step. The caller still must implement actual CARLA actors, camera encoding, reviewed site context and saved media audit. CPU fixtures do not establish physical motion or visibility.

Thirty-one focused tests pass in `cpu-native-capture-tests.log`; scoped static passes in `cpu-native-capture-static.log`; exact scoped strict exits 1 on truthful partial in `cpu-native-capture-strict.log`. All three logs are SHA-bound in `result.json`. Next implement Native actor/camera setup and the selected canonical case bundles, then positive/negative compatibility and independent saved delivery/comparison audits.
