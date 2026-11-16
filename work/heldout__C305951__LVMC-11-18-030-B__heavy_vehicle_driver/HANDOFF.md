# heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: LVMC 11.18.030(B) — Where such traffic lanes have been marked, it shall be unlawful for the operator of any vehicle to fail or refuse to keep such vehicle within the boundaries of any such lane except when lawfully passing another vehicle or preparatory to making a lawful turning movement.
- Cell/actor: C305951 / heavy_vehicle_driver; layout `three_lane_road`, maneuver `travel`, control `lane_marking`.
- Exact input: `inputs/heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver/assignment.json` (SHA256 `f283c22a20926d105199e58158ae65a52f1297bb5c63f01cf4d27a4942edf2b5`).
- Witness: `inputs/heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: st.lane, st.lane_marking, rel.occupies, drv.straddles_marking, drv.overtaking, drv.turning, sig.turn_indicator, drv.lane_change.

## Required source and construction review

1. Applicable jurisdiction, vehicle classification and operator identity.
2. Establish municipal applicability, operator identity and vehicle scope.
3. Heavy-vehicle dimensions, clearance and motion.
4. Other-vehicle and intended-turn context needed to assess the express exceptions.
5. Preserve the exceptions for lawfully passing another vehicle and preparation for a lawful turning movement. Supply other-vehicle, intended-turn and applicable external-rule context when either exception is asserted.
6. Preserve uncertainty about municipal incorporation of state definitions and the relationship between operator and driver.
7. Record vehicle extent and motion relative to boundaries without selecting a statutory tolerance or vehicle-component test.
8. Specify the three lanes' directional allocation, actual marked boundaries, governed route and heavy-vehicle dimensions.
9. The actual three-lane allocation, marked boundaries and their governance of the selected route.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## 2026-11-15 exact heavy-vehicle case decomposition

The plan now names four exact cases: `__within_marked_lane`, `__unexcused_boundary_crossing`, `__passing_boundary_crossing`, and `__lawful_turn_preparation_boundary_crossing`. It binds three controlled comparisons and six mandatory original-source measurements, including heavy-vehicle footprint, marked boundary geometry, passing/turn context, and all four camera originals. All three law requirements are selected with assigned case IDs. The fixed travel cell can carry turn *preparation* only if a source-recorded intended turn and independent lawful-turn premise are supplied; an indicator alone is insufficient. The package remains **partial**: this is case decomposition, not executable construction or a proof.

Next implement a source-surveyed three-lane Native route and heavy-vehicle full-body footprint recorder for the within-lane case. Require the original marked boundaries, lane direction allocation, municipal applicability/operator identity, body dimensions and four camera streams. Build its exact config/runner/finalizer/primary and three physical-risk fallback bundles; run pinned offline, positive/missing-original compatibility, fresh saved-only processing and independent source audits before extending to the three comparisons. Keep geometric tolerance and external-law permission undecided. Then add semantic proposals, physical/lifecycle and delivery proofs, and rerun the scoped strict gate. CPU construction is worker-owned; actual Native physical and legal judgments are later source checks.
