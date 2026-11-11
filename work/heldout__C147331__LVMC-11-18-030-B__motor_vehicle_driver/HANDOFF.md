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

## 2026-11-11 Native construction probe and offline proof

`lane_construction.py` now selects a connected marked, same-direction pair of
driving lanes and rejects a road with opposite-direction sampled lanes, absent
markings, junction intrusion or ambiguous continuation. It builds three
case-specific route targets. The crossing and passing cases share the same
lateral route; the passing case additionally specifies a separately spawned
participant. `control_step` makes bounded steering/throttle/brake requests from
Native position, heading and velocity, using one engineering policy for linked
cases. `tests/test_lane_construction.py` exercises both travel directions, all
three paths, missing geometry and controller readbacks.

`native_construction_probe.py` is a CARLA-lazy diagnostic entrypoint. Its
`--run` path selects the route, spawns the ego and optional overtaken vehicle,
executes controller ticks, retains original waypoint/participant source rows
and synchronizes four named source-camera FFV1 streams at 20 Hz.
`lane_camera_capture.py` creates overview 1920x1080 and approach,
reference_corner, driver_reference 1280x720 streams; its fake Native test
exercises sensor creation, frame join, duplicate rejection and cleanup. The
probe does not seal Native output or claim delivery readiness. No CARLA run or
physical camera visibility claim has been made.

`construction-probe.json` and `construction-probe-manifest.json` bind the first
`__within_marked_lane` construction to SHA256
the current per-case SHA256 values in `probe-case-proofs.json`.
The exact `runtime.py offline` command and current hashed positive log are in
`probe-case-proofs.json`; each passes the materialized entrypoint `--check`
and its bundled CPU tests. The complete local suite passes 13 tests under the command
in `result.json`. These proofs validate construction software only.

Next CPU work is to promote this probe to a complete selected-case delivery
runner with original frame map, Native sealing, four-camera acquisition checks,
source-bound finalizer, diagnostic recipe, positive/negative compatibility and
saved-only processing. Build separate exact crossing and passing constructions,
then risk-triggered fallbacks and audits. Keep all cases partial until the
scoped strict gate passes.

Scoped strict gate still exits 1 with `Preparation acceptance failed: partial/missing packages remain`; latest `strict-gate.log` SHA256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`.

## 2026-11-11 three-case saved processing and independent audit

The current `construction-probe-manifest.json` binds all three planned C147331
case IDs to distinct source-hashed inline constructions. Each embeds the
CARLA-lazy Native route/controller/source-camera probe, exact config,
`lane_finalizer.py`, and CPU tests. `probe-case-proofs.json` records each exact
`runtime.py offline` and `runtime.py compatibility` command, construction SHA,
passing log hashes and positive receipt. Every compatibility receipt includes
`actual_analysis`, Native validation, mandatory observations, Lean decoder,
render, final decode, four camera sources, selected measurements, and negative
`marked_lane_sources.jsonl` removal. The selected measurement is recomputed
from the new case-specific original lane source. The frozen generic graph and
trace fixture shapes are retained only for software adapter compatibility;
they are synthetic and do not demonstrate this law's physical facts. The
`__unexcused_boundary_crossing` diagnostic contains a measured body excursion;
`__passing_boundary_crossing` additionally contains a participant and measured
longitudinal order reversal. No legal crossing tolerance or lawful-passing
status is assigned.

`probe-saved-proofs.json` records three passing `runtime.py process-saved`
commands. Each selected candidate is primary, original acquisition bytes
remain unchanged, `missing_evidence` is false, and the renderer/full video
decoder pass. `delivery_audit.py` independently recomputes lane measurements
from retained sources, checks source hashes and fully decodes each of four named
cameras. `probe-source-audit-proofs.json` binds all three passing saved-source
audits and their auditor hash; its unit test rejects changed or missing source
bytes. `audit_saved_comparisons.py` binds each saved result and source hash,
compares the original fixed map/lane geometry/markings/camera plan/duration,
and checks measured containment, excursion and passing order.
`probe-comparison-audit.json` records both passing software comparisons. The
local CPU suite now has 18 tests; one materialized-config test is skipped in
the repository checkout but runs in each exact offline bundle.

This remains **partial**. The Native probe still identifies itself as
`construction_probe_only` and does not seal a deliverable attempt. Complete
original FrameMap/PipelineCapture output, actual first-case delivery runner,
risk-triggered fallback constructions and proofs, canonical semantic stage
proposals, final source-bound acceptance handoff and C5191 turn branch are
unfinished CPU work. No synthetic receipt proves physical visibility, motion,
municipal applicability or a legal exception. All current commands and log
hashes are recorded in `result.json` and the named proof JSON files.

## Delivery construction checkpoint (2026-11-11)

`runner.py` is now a CARLA-lazy Native delivery entrypoint for the three exact
C147331 cases. It records the original `PipelineCapture` trace/capture tree,
`video_frames.jsonl` via `FrameMap`, `marked_lane_sources.jsonl` from Native
waypoints and participant bodies, and four FFV1 source streams. It restores
world settings and seals the attempt only after full frame and camera checks.
The earlier `native_construction_probe.py` and probe receipts remain separate
historical diagnostics and do not represent a deliverable capture.

`delivery-construction-manifest.json` binds three primary delivery
constructions and nine distinct fallback constructions. Every case has a
physical-risk assessment. Fallback triggers are (1) insufficient connected
marked route at 2 m sampling, addressed by 1 m sampling; (2) body excursion
from controller overshoot, addressed by reduced requested speed/gain; and (3)
failed primary route spawn, addressed by the next sorted verified route.
These are engineering alternatives with unchanged case identity, observations,
recording description, four-camera plan and duration. Their triggers require
Native evidence; CPU compatibility does not claim their physical success.

`delivery-case-proofs.json` records passing exact offline and positive/negative
compatibility checks for all three primaries. The nine fallback offline and
compatibility receipts and their source hashes are embedded in the delivery
manifest; `candidate_constructions.validate(..., required=True,
require_alternate=True, candidate_count=4)` passes for every exact case.
`delivery-saved-proofs.json` records three passing saved-only processing runs,
with originals preserved and missing evidence false. `delivery-source-audit-proofs.json`
records independent recomputation and full decodes of all four cameras for
those three saved outputs. `delivery-comparison-audit.json` records both passing
software comparisons over the saved outputs. All media in those checks are
synthetic adapter diagnostics and remain under ignored `.runtime-work`.

Status stays **partial**. The canonical semantic stage proposals and full
statutory branch including proposed C5191 turn remain unfinished. The canonical
`execution-manifest.json`, first-case `construction.json`/`config.json`, delivery
job queue, and acceptance fields have not yet been reconciled to the strict
gate. No CARLA capture, municipal applicability finding, physical visibility
finding, lawful-passing determination or legal verdict is claimed. Next CPU
work: implement the turn case and finalizer/source audit, complete semantic
stage proposals, reconcile canonical package artifacts, then rerun all affected
proofs and the scoped strict gate before changing status to ready.

## Semantic and turn branch checkpoint

The six law/cell semantic draft artifacts in `proposals/relevance_batch.json`,
`relevance.json`, `template.json`, `judgment_passing.json`,
`judgment_turn.json` and `bindings.json` now pass the frozen stage validators.
`semantic-draft-proof.json` binds their hashes. The template preserves both
express exceptions as distinct unresolved judgment phrases. This is not yet a
canonical `semantic-index.json`: the current `proposals/cases.json` still lacks
the baseline, complete bound variable assignments and physical judgment sweep
coverage required by the stage contract. It must be expanded and independently
validated before strict readiness.

`proposals/c5191-turn-branch.json` cites the exact frozen law assignment and
candidate-cell inventory for C5191, which is `adjacent_lanes/left_turn/lane_marking`
and is not allocated in `batch.json`. It defines three proposed exact comparison
cases without adding them to the C147331 delivery manifest. `turn_route.py`
adds a CARLA-lazy selector for a connected marked approach and genuinely
leftward exit waypoint. The local tests exercise accepted left-turn geometry
and rejection of rightward or unmarked exits. A complete C5191 runner,
original turn evidence, finalizer and audits remain to be authored after an
exact allocation; C147331's frozen `travel` cell must not be silently changed.

`execution-manifest.json` now carries the three delivery primaries, their exact
offline log hashes, all nine tested fallback receipts, and the Native handoff
variables. Running the frozen execution-manifest validator reaches its next
specific CPU gap: `physical_preparation` is absent for the first case. That
contract requires three measured physical-outcome fixture classes and an
ordered Native owner-release lifecycle proof per case. These must be authored
and tested from retained sources; the existing saved-processing receipts alone
do not satisfy that gate. The manifest remains a partial draft until this and
the semantic/delivery handoff requirements pass.
