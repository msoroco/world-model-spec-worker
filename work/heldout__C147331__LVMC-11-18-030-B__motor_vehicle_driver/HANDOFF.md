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

## Source-expanded contract and physical preparation checkpoint

The delivery recording description now declares seven case-specific channels:
original-derived lane clearance, lane boundary geometry, ego footprint,
clearance overlap, passing participant context, ego indicator readback and ego
motion. `lane_finalizer.py` regenerates each channel only from retained
original frame-joined sources. Three primary and nine fallback inline
constructions were rebuilt with that description, and every affected exact
offline/compatibility proof was rerun. Three primary saved-processing receipts,
three independent four-camera source audits and the new
`delivery-comparison-audit-v2.json` pass on the current hashes.

The canonical `proposals/semantic-index.json` now validates through the frozen
seven-stage semantic chain for all three selected C147331 cases. It includes a
baseline and two explicitly incomplete physical judgment sweep specifications:
passing needs independently sourced applicable rules and a frozen physical
grid; turn preparation needs an allocated compatible turn cell. These are
recorded as incomplete rather than supplying invented legal thresholds or
pretending the fixed travel cell completed a turn.

`physical_fixture.py` tests all three case-specific measured outcomes using
synthetic Native-shaped original sources: complete motion, incomplete motion,
and missing required lane source. `lifecycle_fixture.py` exercises actual
runtime seal, Native exit, owner-release and saved-processing functions in the
required order with a synthetic diagnostic fixture. All nine outcome runs and
three lifecycle runs pass and are source-hashed under `physical/`.
`execution-manifest.json` validates through the frozen execution-manifest
validator, including the current fallback and physical-preparation receipts.
This proves CPU preparation behavior only, not actual CARLA realization.

Status remains **partial**. The two judgment sweeps are not complete; C5191 is
unallocated. Canonical delivery acceptance proofs, first-case canonical
construction/config contract, and final handoff/queue checks remain CPU work.
The scoped strict gate must be rerun and pass before setting ready.

## Delivery acceptance and canonical first package checkpoint

`lane_physical_outcome.py` requires independent source recomputation, measured
case-specific motion, four fully decoded original camera streams and a
source-hashed pixel-review record covering markings and bodies. It leaves
legal exception judgments unresolved. `acceptance_fixture.py` exercises the
positive path and rejects a deliberately stale approach-camera review; all
three exact case pairs pass. `execution-manifest.json` binds those positive and
negative logs as delivery acceptance contracts, and frozen
`delivery_handoff.validate_case` passes for each selected case.

The manifest now also binds primary compatibility receipts, original-source
negative logs and all seven acquisition channel implementations. Frozen
`package_compatibility.check_receipts` passes. Canonical `config.json`,
`construction.json` and `runner.py` are present for the first exact case;
`runner.py --check` passes against that canonical config. `case-plan.json` now
has the exact four-view camera profile and source-observation channel mapping.
The first GPU dispatch command is populated in `result.json`, while status
remains partial. These CPU fixtures do not assert actual pixel visibility or
physical realization. The two incomplete judgment sweeps and C5191 allocation
still prevent a truthful ready declaration; the global queue belongs to the
shared handoff and has not been edited by this worker.

## 2026-11-11 six-case passing sweep and strict gate checkpoint (latest)

This section supersedes older three-case counts above. Status remains **partial**. The exact C147331 travel-cell delivery manifest now contains six primary cases: within marked lane, unexcused boundary crossing, passing boundary crossing, and passing excursion fractions 0.4, 0.6, and 0.8. Each has three distinct physical-risk fallback constructions. `extend_passing_sweep.py` builds the sweep variants from the reviewed passing construction, with exact case IDs and source-measured clearance; `runner.py` accepts only each variant's declared fraction. `tests/test_lane_construction.py` proves the three requested paths are distinct on a connected marked route. A requested fraction is an engineering control, not an observed clearance or legal threshold.

`prove_delivery_cases.py` and `prove_delivery_fallbacks.py` passed exact offline and positive/negative compatibility for all six primaries and 18 fallbacks. `prove_delivery_saved_cases.py` passed saved-only processing for six primaries, and `prove_delivery_source_audits.py` independently decoded and bound all four retained camera sources for each. `bind_physical_fixtures.py` passed complete/incomplete/missing-evidence outcome and ordered Native closure protocols for all six; `bind_acceptance_fixtures.py` passed positive and stale approach-camera rejection for all six. These are synthetic CPU protocol tests and make no actual physical or legal acceptance claim. `audit_passing_sweep.py` binds the three exact constructions to their retained diagnostic measurements, while explicitly withholding any physical clearance trend claim. The two original saved comparison audits remain valid for their three source cases. The case plan now declares the third sweep comparison.

The canonical semantic proposal chain validates seven stages and six selected exact cases. Passing excursion sweep expansion is complete in the proposal and matches the execution manifest. The passing lawful-facts judgment sweep still needs jurisdictional facts and applicable passing rules; the lawful-turn-preparation branch is separately proposed against unallocated candidate cell C5191 and is not a C147331 travel-cell construction. No exception verdict is inferred. The first GPU delivery command remains the exact within-marked-lane command in `result.json`; it has not been executed.

The three CPU fixture scripts now set `SCENARIO_PIPELINE_OUTPUT_ROOT` to ignored `.runtime-work/c147331-pipeline-output` before importing the adapter. A prior diagnostic had generated `runtime/runs/scenario_pipeline/inputs/shared/manifest.json` and two map-cache files; those exact generated files and empty directories were removed. No runtime source or frozen input was changed.

`cpu-tests.log`: 21 tests passed. `scoped-complete-gate.log`: `.venv-cpu/bin/python worker_check.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver --complete` passed. Frozen semantic delivery, execution manifest, compatibility receipt, and six exact delivery handoff validations passed. `strict-gate.log`: the same scoped check with `--require-delivery-ready` fails only at `Preparation acceptance failed: partial/missing packages remain`, consistent with truthful partial status. Resume with the incomplete passing judgment facts/turn allocation and Native physical verification; do not promote fixture measurements to physical evidence or change status to ready until all required CPU proof and strict readiness conditions are satisfied.

## 2026-11-11 passing sweep unit review

The current complete passing excursion plan varies `lane_crossing_fraction` at 0.4/0.6/0.8 (dimensionless controller requests), but declares `lane_clearance_m` as the realized observable in metres with the same numeric axis limits. The pinned `realized_coverage` calculation compares measured observable values directly with those limits, so this mixes units. The three retained diagnostic measurements are all -1.4 m despite distinct requests. They test source binding and construction, not realized sweep separation. Next CPU step is to retain adjacent-lane center on original Native ticks and derive an observed dimensionless lateral fraction from original body/lane geometry, or replace the controller with a metre-valued clearance target and reprove all affected exact cases/fallbacks/saved/audit receipts. Do not infer a legal cutoff or a physical trend from the current fixtures. The package stays partial.

## 2026-11-11 passing sweep unit correction

The canonical passing sweep no longer compares dimensionless requested fractions 0.4/0.6/0.8 against metre-valued `lane_clearance_m`. Its planned axis is now dimensionless observed `lane_crossing_fraction`, derived as maximum original ego-center displacement from the retained lane center projected across lane heading, divided by the original lane width. `audit_passing_sweep.py` independently reads the saved original source, binds its hash and reports all three diagnostic observed fractions as **0.625**. Requested controls remain 0.4/0.6/0.8; diagnostic realization has no separation. The sweep status is `incomplete` until a retained original fraction channel, distinct Native realizations and applicable passing-rule facts are available. The six selected constructions and 18 fallback proofs were not changed.

Canonical semantic index SHA-256 `2065588b7e90f9d9358c59b24892d1b5819c7a493f97ae01912634b09358e573`; corrected source sweep audit SHA-256 `b51c57f95d1afa14676d38e89ec851b96971957b8b6381de628e047dda783907`. Seven-stage semantic validation and scoped `worker_check --complete` pass. Scoped strict gate still fails at truthful partial status (`strict-gate.log` SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`).

## 2026-11-11 distinct passing diagnostic sources

`build_passing_sweep_diagnostics.py` now generates separate source-shaped original ego trajectories for the three unchanged exact requested controller fractions. The fixture updates original body corners, trace, captured ego/participant evidence, graph attributes and capture trace hash together. All six primary and 18 fallback offline/positive-negative compatibility receipts were regenerated, followed by six saved-only proofs, original-source four-camera audits, synthetic physical/lifecycle and positive/stale-source delivery acceptance fixtures. A fresh saved comparison audit is `delivery-comparison-audit-v3.json`.

The independent saved-source sweep audit measures diagnostic observed lateral fractions **0.4, 0.6, 0.8**, with minimum body clearances **-0.5, -1.3, -2.1 m** respectively. This is synthetic CPU source realization and does not prove Native route control, actual pixel visibility, physical completion or lawful passing. The canonical sweep stays `incomplete` pending a retained original fraction recording channel and physical/legal facts.

- `delivery-construction-manifest.json` SHA-256 `1c2fa8a0b65a800ae7548cede3fac06324f41b004d5ada1aea0071cf4b6704a9`
- `execution-manifest.json` SHA-256 `dc469d7afef7a90b9d16dbc909f5b2853ae470605f916a66e4b7b62033a064d7`
- `proposals/semantic-index.json` SHA-256 `ce156c043f212fa86fcdae0128097357b896acee4e18e39574d89221b47e1e13`
- `delivery-passing-sweep-audit.json` SHA-256 `fd81e8596f698e25bfe0a3bb26b2dfe4ec795e91b54399a74ccc53ccea7a9922`
- `delivery-comparison-audit-v3.json` SHA-256 `98fc04f05f78a33c78d05b3d326f452dbd0e2322c22c21660b77e8e6d9ad8bd3`

## 2026-11-11 retained fraction channel and complete CPU passing grid

This supersedes the preceding incomplete diagnostic sweep notes. `lane_finalizer.py` now writes `lane_crossing_fraction.jsonl` from original ego body corners and retained lane center, heading and width; the saved result summarizes its max over the original frame window. The three case-specific diagnostic originals and controller targets follow the canonical grid order: `passing_excursion-0000` 0.4, `0001` 0.8, `0002` 0.6. The canonical passing sweep spec is `complete`, has a dimensionless fraction axis and matches the three selected judgment sweep cases. Frozen `recording_evidence` validation recomputes all three saved summaries from the raw channel. Independent source audit reports diagnostic 0.4/0.8/0.6 and body clearances -0.5/-2.1/-1.3 m. Actual Native realization, physical completion and legal passing remain unverified.

All six primary and 18 fallback exact offline/positive-negative compatibility receipts, six saved-only proofs, six original-source/four-camera audits, synthetic physical/lifecycle and delivery acceptance protocols were rerun after runner/finalizer/config/fixture changes. `delivery-comparison-audit-v4.json` is the current saved comparison proof. Canonical first `construction.json` source content was rebound; scoped `worker_check --complete` and seven-stage semantic validation pass. Scoped strict gate still fails truthful `partial`, because the separate turn-preparation sweep and Native/legal facts remain unresolved.

- `construction.json` SHA-256 `5c3931ef9a791d70cfc00876f06dc78ec99923a1f142f46618959f3598e55b8d`
- `delivery-construction-manifest.json` SHA-256 `9ec49c6e555eac78e4e469352f9d2c98aab8c029be71f71eab6b52f028696d2a`
- `execution-manifest.json` SHA-256 `7e2f3c362b0cf1173f88ffb4a750af7180524f11f898916a7d953997325f514c`
- `proposals/semantic-index.json` SHA-256 `8f72a61ca1f571deab89e27ada09b01bc9f069161c7a7bf6f18001b051aecd8b`
- `delivery-passing-sweep-audit.json` SHA-256 `16c23de0f304439d5cb76a4a7bd6971327c66126a5b2a0c86ef4b7432843b114`
- `delivery-comparison-audit-v4.json` SHA-256 `98fc04f05f78a33c78d05b3d326f452dbd0e2322c22c21660b77e8e6d9ad8bd3`
- `strict-gate.log` SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`

## 2026-11-11 compatible turn-cell cross-reference

The C147331 fixed travel cell cannot locally construct the lawful-turn-preparation exception. Supplemental C5191 is now allocated and has six selected exact connected-left-turn cases, 18 fallbacks and a complete source-derived .2/.6/.4 turn excursion CPU grid. `case-plan.json.cross_cell_alternatives` cites its manifest and semantic index; C147331 keeps its local turn sweep and requirement disposition pending rather than inventing a travel-cell turn case. Its passing grid remains complete. Both scoped complete checks pass; strict checks remain partial.

- C5191 execution manifest SHA-256 `ff9b56869ad6bd94ff1af7d8ab9065832b29fc118f8a70d9cee92c2904c40b26`
- C5191 semantic index SHA-256 `669f28cedaae643cf505606fceef31006209f205ce815b82faad98fefd329b98`
- C147331 case-plan SHA-256 `8942bc3e83a31667dc474ce52a35b98a3e360b964c354f67abdfcec355a67cb4`
- C147331 semantic index SHA-256 `5d8ecbe5dee705fdc76192a1132710656e22b1b449591d596cd7d635220b2536`

Zero-byte synthetic diagnostic logs were source-preservingly compacted into `work/_shared/prune-history.json` (`compacted_zero_logs`) to respect the frozen return-file cap. Their exact former paths and empty-byte SHA256 are retained; restore them with `work/_shared/restore_compacted_zero_logs.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver` before its scoped strict proof sweep. The assignment remains partial.

2026-11-12 return-cap compaction: 47 small UTF-8 diagnostic logs have exact path, contents and SHA256 stored in `work/_shared/prune-history.json.compacted_text_files`. Scoped nonstrict preparation passes after compaction. Restore before any strict completion sweep with `.venv-cpu/bin/python work/_shared/restore_compacted_zero_logs.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver`; status remains partial.

Additional cap compaction after the previous note archived 61 more UTF-8 diagnostic logs under the same hashed shared inventory. Total newly compacted on 2026-11-12: 108 files. Scoped nonstrict still passes. The same restore command restores all compacted logs for this assignment.

Final cap compaction in this wave archived the remaining 28 UTF-8 diagnostic logs. Total newly compacted on 2026-11-12 is 136 files; full text/path/SHA256 remain in the shared inventory. Scoped nonstrict passes. Restore all 136 before strict with the same command above.

2026-11-12 return-cap checkpoint: 42 source-hashed UTF-8 physical fixture and fallback compatibility receipts are preserved with full text/path/SHA-256 in `work/_shared/prune-history-3.json`. Restore before scoped strict with `.venv-cpu/bin/python work/_shared/restore_compacted_zero_logs.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver`. Status remains partial.

2026-11-12 return-cap checkpoint: 31 source-hashed UTF-8 diagnostic audit/proof receipts are retained with full text/path/SHA-256 in `work/_shared/prune-history-3.json`. Restore before future scoped strict with `.venv-cpu/bin/python work/_shared/restore_compacted_zero_logs.py --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver`. Status remains partial.

## 2026-11-12 turn-preparation control and current CPU proof checkpoint

The fixed C147331 one-way travel cell now assigns its turn-preparation requirement to the `within_marked_lane` case as an original-source **negative/control measurement**. `lane_finalizer.py` retains frame-joined video index, light state, position, heading, speed and lane identity under `turn_preparation_control`; the first measurement contract requires that output. The control has no selected turn or lawful-turn conclusion. `case-plan.json.cross_cell_alternatives` explicitly identifies the supplemental C5191 left-turn cases and comparisons as the positive branch; its Native lawful-turn facts remain unverified.

The four affected within-lane inline constructions have been rebuilt. Their current exact offline and positive/negative compatibility runs pass, including absence of `marked_lane_sources.jsonl` as the negative case. The primary also passed fresh `process-saved` and independent original-source/four-camera decoding under ignored `.runtime-work/c147331-control-staged`; three synthetic physical outcomes and ordered lifecycle closure passed. The first physical receipt is rebound to the current construction SHA in `execution-manifest.json`. These fixtures establish CPU protocol behavior only.

**Status remains partial.** The returned bundle still cites source-hashed historical proof paths compacted into `work/_shared/prune-history.json` and `prune-history-3.json`; approximately 68 result test logs and 97 execution-manifest paths are absent at this checkpoint. Restore or replace those exact references, rebind the saved/delivery/comparison proof sweep and verify scoped strict before setting `ready`. Do not infer a Native physical turn or lawful exception from the travel control.

## 2026-11-12 scoped strict readiness

The scoped strict command `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready --assignment heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver` now passes. `result.json.status` is `ready` with `delivery_prepared` scope. The current first-case saved receipt, independent original-source/four-camera audit, and saved comparison audit are returned as `turn-control-*.json`; exact offline and positive/negative compatibility logs and receipts are bound in `execution-manifest.json`. Source-hashed historical paths required by the manifest and nested physical proofs were restored from shared inventories without overwriting refreshed logs. The per-case passing sweep acquisition now names its emitted `lane_crossing_fraction` channel. Root `config.json` covers all six selected IDs.

The straight-travel control makes no lawful-turn or Native physical-success claim. Supplemental C5191 supplies the CPU-proven positive turning comparison; actual Native site facts and legal judgments remain for the delivery operator.
