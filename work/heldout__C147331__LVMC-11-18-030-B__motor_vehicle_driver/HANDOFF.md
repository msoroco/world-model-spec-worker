# heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: LVMC 11.18.030(B) — Where such traffic lanes have been marked, it shall be unlawful for the operator of any vehicle to fail or refuse to keep such vehicle within the boundaries of any such lane except when lawfully passing another vehicle or preparatory to making a lawful turning movement.
- Cell/actor: C147331 / motor_vehicle_driver; layout `one_way_multilane`, maneuver `travel`, control `lane_marking`.
- Exact input: `inputs/heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver/assignment.json` (SHA256 `92dfd9b7e7f6909014b19bef360d5d4de6fc48ebf7cff0941102b507f6e14f83`).
- Witness: `inputs/heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: st.lane, st.lane_marking, rel.occupies, drv.straddles_marking, drv.overtaking, drv.turning, sig.turn_indicator, drv.lane_change.

## Required source and construction review

1. Applicable jurisdiction and definition scope.
2. Document markings that establish traffic-lane boundaries, their direction and the connected ego route.
3. Establish municipal applicability, operator identity and vehicle classification.
4. Markings that establish traffic-lane boundaries, their directional governance and the ego route.
5. Passing and turn-preparation facts, including applicable external rules if an exception is asserted.
6. Preserve unresolved applicability of supplied state definitions.
7. Record vehicle footprint and motion relative to boundaries without inventing geometric or duration tolerances.
8. Retain both express exceptions and any passing, turn-preparation and external-rule facts needed to assess them; signaling alone does not establish an exception.
9. Vehicle extent, operator identity and motion relative to those boundaries.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## Draft branch and comparison plan

`case-plan.json` records three exact planned case IDs: `heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__within_marked_lane`, `heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__unexcused_boundary_crossing`, and `heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__passing_boundary_crossing`. The first comparison changes the path and measured footprint overlap; the second changes the presence and motion of an overtaken vehicle while holding the crossing path fixed. Each needs its own exact construction, raw source packet, measurement contract, all four camera streams, offline proof, positive and negative compatibility proof, saved-processing proof, and independent audit. These cases are **planned only**; the passing exception also requires externally sourced lawful-passing facts. No legal verdict is inferred from a path command or crossing distance.

The lawful-turn-preparation exception remains open because C147331 fixes `travel` rather than `turn`. Inspect `inputs/coverage/candidate-cells.json` for a compatible motor-vehicle turn cell and propose an additional binding to the lead for shared coverage. A turn indicator alone cannot establish the exception. The original text contains no numeric lateral or duration threshold; retain signed footprint-to-boundary distances and full frame history without imposing one.

The zero-recording evidence inventory was reviewed in `case-plan.json.evidence_review`; no existing-evidence claim is made. This checkpoint passes `.venv-cpu/bin/python worker_check.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver --complete` but fails strict readiness because the package is partial.

## Implemented CPU measurement helper

`lane_footprint.py` measures signed body-corner clearance to a supplied native lane polygon and detects segment crossings. It is value-free: it makes no legal cutoff or exception decision. The input must be frame-joined native lane geometry and measured vehicle corners; neither source is yet captured or wired to a saved finalizer. `tests/test_lane_footprint.py` checks containment and boundary crossing for both polygon orientations and rejects invalid geometry. The exact test command is `.venv-cpu/bin/python -m unittest discover -s work/heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver/tests -v`; output is `cpu-tests.log` with SHA256 `3a01caf7416f85ecd3beb2398df0c540e69cb68eebada50b2c3a750760b102c6` and exit code 0. This fixture does not demonstrate CARLA lane markings, visibility, or legal outcome.

The strict gate `.venv-cpu/bin/python worker_check.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver --complete --require-delivery-ready` exited 1; `strict-gate.log` (SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`) ends with `Preparation acceptance failed: partial/missing packages remain`. This is the correct partial status because the CPU deliverables listed above remain open.

## 2026-11-11 retained-source and comparison continuation

The pinned `.venv-cpu/bin/python runtime.py preflight` now passes with NumPy,
FFmpeg and Lean 4.28.0; earlier missing-tool diagnoses are obsolete.
`lane_sources.py` now reads an original Native waypoint and actor bounding box
for each tick, records both marking types, road/lane identity, local lane
polygon, vehicle footprint and velocity, and optional passing participant
identity/footprint/velocity to `marked_lane_sources.jsonl`. It rejects absent
markings, nonfinite geometry, repeated participant IDs and skipped frames.
`lane_measurement.py` reads that retained file and computes the signed lane
clearance per frame; it rejects missing sources, frame gaps, changed Native IDs
and missing passing participants. `lane_comparison_audit.py` checks exact case
identities, declared fixed map/lane/marking/camera/duration fields, source hash
fields, observed containment/excursion and passing motion source presence. Its
inputs are draft saved-measurement packets; promoted byte-hash binding and
saved-processing integration still need implementation. None of these helpers
assert legal exception status or realized physical visibility. The local
waypoint rectangle is a geometry proxy; a complete runner must sample curved
marking geometry and verify that the slice covers the full vehicle.

Seven CPU tests pass under `.venv-cpu/bin/python -m unittest discover -s
work/heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver/tests -v`; see
`cpu-tests.log` and its current SHA256 in `result.json`. The scoped static
`worker_check.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver
--complete` passes. The scoped strict gate with
`--require-delivery-ready` still exits 1 in `strict-gate.log` with
`Preparation acceptance failed: partial/missing packages remain`, correctly
reflecting the missing executable delivery package. Next CPU work is the
CARLA-lazy runner, full four-camera source capture, finalizer and one primary
case through exact offline, compatibility and saved-processing proofs, followed
by linked cases, risk-triggered fallbacks, semantic proposals and source-bound
audits. The lawful-turn exception must be bound to a compatible turn cell.

The frozen candidate-cell catalogue identifies unallocated `C5191` as an
actor-compatible `adjacent_lanes` / `left_turn` / `lane_marking` cell, with
LVMC-11-18-030-B in its annotation provenance. `case-plan.json` records this
as a proposed additional binding for the lawful-turn-preparation branch. It is
not yet allocated in shared coverage, and no lawful-turn claim is made.

Original capture now retains the ego light-state readback when available.
Saved measurement projects ego and passing-vehicle body centers onto each
Native lane heading, preserves per-frame signed longitudinal offsets, and
reports observed negative-to-positive order reversal. The passing comparison
checker rejects absent order reversal, absent motion-source hashes, source
hash fields, case identity errors and changed fixed conditions. Eight tests
pass with missing-evidence negative branches; current hash is in `result.json`.
`case-plan.json.source_observation_mapping` names all eight planning terms and
marks the still-missing turn source explicitly. The audit is a draft CPU helper;
actual promoted bytes and finalizer outputs must be bound before readiness.

`case-plan.json` now gives each of the three exact planned cases its own
physical motion or camera risk. Candidate constructions remain explicitly
`not_yet_implemented`; no fallback or receipt is claimed. The within-lane case
needs body-corner clearance and marking visibility, the unexcused crossing
needs measured boundary excursion, and the passing case additionally needs a
measured longitudinal order reversal. These are engineering triggers, not
legal thresholds or physical-success claims.

Latest scoped strict gate log `strict-gate.log` SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`; exit code 1 because status is correctly partial.
