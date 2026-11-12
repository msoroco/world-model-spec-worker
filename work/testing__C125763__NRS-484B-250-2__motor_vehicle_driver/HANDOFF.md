# C125763 CPU handoff — NRS 484B.250(2)

Status: **partial**. This frozen median-opening branch has a fixed yield sign. The witness relocates the device comparison from C125714. The exact law excludes official traffic-control-device intersections except as provided in subsection 4, so measured near-time entry at an official yield sign is not a violation finding. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps ego-left/right and close/separated entry timing plus opposite-direction left-turn exception context. `yield_sign_control.py` selects a Native sign whose trigger contains the approach waypoint. `simultaneous_entries.py` requires a source-declared single crossing, different highways, complete original-frame vehicle bodies, sign identity and video-frame joins. It reports body entry times and right-side geometry while leaving “approximately,” official status, legal yield and subsection-4 application unresolved. Three CPU tests pass in `cpu-tests.log`, including trigger selection, side geometry and wrong-sign/stale-frame rejection.

Next CPU work: source a real statutory crossing and official yield-sign governance, construct both vehicle routes and yield controller, capture four named raw cameras and original body/sign/road sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical crossing, sign, motion and visibility remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C144550__NRS-484B-223-1b__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## Median yield route construction checkpoint, 2026-11-12

`median_yield_route.py` now requires both declared routes to traverse the
interior of one source-reviewed median polygon. It checks different highways
for the ordinary comparison, or one highway with opposing headings and an
explicit other-driver left-turn intention for the exception case. It binds the
Native yield sign to ego's entrance lane and places the yield line before the
crossing. Its CPU controller brakes for an observed conflict, rejects passage
past the yield line into an uncleared conflict, and releases when clear. This
is a construction/controller component; no actual reviewed Native site or
physical sign status has been established.

Seven CPU tests pass in `cpu-tests.log`, including both approach routes,
opposite headings, wrong sign lane, wrong yield line, braking and release.
Next CPU work is the reviewed site packet, lazy Native actor/camera runner,
saved finalizer, diagnostic media, three distinct fallbacks per selected case,
semantic proposals and exact offline/compatibility/saved proofs. Status remains
partial and the work is worker-owned.

The latest assignment `worker_check.py --complete` exits 0 in
`assignment-check.log`. The final full
`worker_check.py --complete --require-delivery-ready` exits 1 in
`strict-gate.log` with `Preparation acceptance failed: partial/missing packages
remain`. The batch delivery gate has not passed. `result.json` remains partial
with the current seven-test log hash. No frozen inputs, runtime, batch file or
Git action was changed.

## Native yield actor construction checkpoint, 2026-11-12

`native_pair.py` now verifies the selected Native yield-sign trigger and ID at
the supplied ego entrance waypoint, spawns both owned vehicles, steers along
the source-reviewed median routes, applies measured conflict/yield decisions,
and destroys every spawned actor after capture errors or a failed second
spawn. `step_pair` emits separate ego and other control commands and keeps
the other vehicle braked until its scheduled release. Ten CPU tests pass in
`cpu-tests.log`, including Native construction and cleanup negatives and the
conflict brake/release path. The pinned CPU preflight passes in
`preflight.log`.

This is a portable construction component, not a completed capture. The
reviewed C125763 site packet, exact case configs, four source cameras,
original-body telemetry, finalizer, diagnostics, three fallbacks per selected
case, semantic proposals and exact offline/compatibility/saved proofs remain
worker-owned CPU work. Keep this package partial; no physical or legal
acceptance is claimed.

Final checks for this checkpoint: pinned `runtime.py preflight`, the ten CPU
tests, and the assignment `worker_check.py --complete` pass. The full
`worker_check.py --complete --require-delivery-ready` exits 1 in
`strict-gate.log` with `Preparation acceptance failed: partial/missing packages
remain`. `result.json` stays partial with the current test-log hash. No frozen
input, runtime, batch file or Git action was changed.

## Source-bound four-camera capture checkpoint, 2026-11-12

`site_packet.py` now binds a reviewed yield-sign median candidate to five
retained SHA-verified source documents for the crossing, all entrances, sign
governance, sign face and median spacing. `runner.py` checks exact C125763
identity, selected case, 20 Hz frame/duration contract, both Native spawn
road/lane IDs and the ego yield entrance before actor construction. Its lazy
Native path uses `native_pair.py`, retains four original RGB camera streams
through `capture_sources.py` and `camera_encoder.py`, writes original vehicle
body/sign/frame/controller history, and seals after world restoration. The
CPU `--check` path does not import or start CARLA.

Nineteen CPU tests pass in `cpu-tests.log`, including source SHA and claim
mismatch negatives, an unreviewed packet rejection, wrong Native lanes,
camera spawn/cleanup and original-frame joins. The tests use synthetic site
documents and source-shaped actors. They do not establish a genuine reviewed
C125763 physical site, an official sign, decoded real media or exact saved
processing. Next CPU work: construct a genuine site packet and all four exact
configs/manifests, run source-bound diagnostic compatibility and saved
processing, implement the finalizer and audits, then three tested fallbacks per
case and canonical proposals. Status remains partial; all listed preparation
remains worker-owned.

The original-source analyzer now also accepts the declared
`yield_opposite_left_turn` exception context: it requires one highway,
opposing approach headings, a controller-history source, original-frame turn
intention, and pre-entry bodies approaching the same crossing. It leaves the
ordinary left/right measure inapplicable for that case. A wrong heading or
missing original intention fails. The revised suite passes 20 CPU tests in
`cpu-tests.log`; this remains a source-shaped diagnostic, not a physical or
legal finding.

For the 20-test checkpoint, pinned `runtime.py preflight` and the scoped
`worker_check.py --complete` exit 0. The full
`worker_check.py --complete --require-delivery-ready` exits 1 in
`strict-gate.log` with `Preparation acceptance failed: partial/missing packages
remain`. `result.json` remains partial and cites the current test-log hash.
No frozen input, runtime, batch file or Git action was changed.

## Saved source finalizer checkpoint, 2026-11-12

`finalizer.py` now reads C125763's original `crossing_history.jsonl`,
`controller_history.jsonl`, `video_frames.jsonl`, `junction_context.json`,
trace, capture evidence and four camera sources. It checks exact selected case
identity, both complete body entries, Native yield-sign identity, original
frame/controller joins, relative side for ordinary cases, and the separate
opposite-direction left-turn intention source. It writes source-hashed crossing,
entry timing, device qualification, opposite-turn and yield-observation
measurements, two derived observation channels, and a Native `result.json`
through the pinned writer. `measurement-contract.json` binds the six
measurements to their retained inputs. A yield slowdown and conflict response
are measured without imposing a stop-sign rule or a legal timing threshold.

The 24 CPU tests in `cpu-tests.log` include a positive `finalize()` call at
nonzero ego speed and negatives for missing controller source, broken frame
join and absent opposite-turn controller intention. Their camera files are
placeholders, so this does not prove video decode, exact runtime compatibility,
recorded-only saved processing, physical visibility or legal application.
Next CPU work remains a genuinely reviewed site and exact configs/manifests,
source-bound diagnostic media and full offline/compatibility/saved proofs,
three fallbacks per case, canonical proposals and independent audits. Keep
C125763 partial.

For this 24-test checkpoint, pinned `runtime.py preflight` and the assignment
`worker_check.py --complete` exit 0. The final full
`worker_check.py --complete --require-delivery-ready` exits 1 in
`strict-gate.log` with `Preparation acceptance failed: partial/missing packages
remain`. `result.json` stays partial and binds the current test-log hash. No
frozen input, runtime, batch file or Git action was changed.

## Isolated primary offline and audit checkpoint, 2026-11-12

The current `cpu-tests.log` records **28 passing tests**. `audit_delivery.py`
independently checks retained source hashes, complete original-frame joins,
entry measurements and yield-sign identity. `audit_comparisons.py` checks fixed
crossing/sign/actor/source conditions and declared side or entry-time
differences for `yield_sign_relative_side` and `yield_sign_entry_timing`;
`tests/test_audits.py` exercises positive and missing/changed-source cases
against actual saved-finalizer outputs. These are software audits, and their
delivery report explicitly says `delivery_ready: false`.

`finalizer.py` has six top-level measurement methods, and
`measurement-contract.json` binds them to the six selected requirement
dispositions in `case-plan.json` for
`testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time`.
Pinned measurement-contract validation returned six rows. `runner.py --check`
now loads materialized `config.json` by default, as required by the runtime
offline invocation.

`build_primary_bundle.py` builds
`cases/yield_ego_left_near_time/construction.json` and an isolated
`primary-candidate-manifest.json` from an explicitly synthetic five-document yield
site packet. Rebuild with:

```
.venv-cpu/bin/python work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/build_primary_bundle.py
```

The exact offline command below passed (`primary-offline-v4.log` and
`.runtime-work/c125763-yield-left-primary-offline-v4/offline.log`), with all
four named cameras, one materialized CPU test and `carla_started: false`:

```
.venv-cpu/bin/python runtime.py offline --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/primary-candidate-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --output .runtime-work/c125763-yield-left-primary-offline-v4
```

This is an isolated partial primary diagnostic. The synthetic packet does not
establish an actual reviewed median opening, an official sign or physical
camera visibility. Extend
the construction/configuration to the other three selected cases, implement
three distinct tested fallback constructions for each, complete canonical
proposals and compare all declared pairs. These are unfinished worker CPU
tasks, not an external blocker. No status is marked ready.

Rechecked with the installed CPU environment:

```
MPLCONFIGDIR=/tmp/c125763-mpl .venv-cpu/bin/python runtime.py preflight
.venv-cpu/bin/python worker_check.py --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

The first two exit 0 (`preflight.log`, `assignment-check.log`). The full gate
exits 1 (`strict-gate.log`): `Preparation acceptance failed: partial/missing
packages remain`. `worker_check.py --updates` reports version 0, no notices
and no paused assignments. `result.json` remains partial and binds the
current 28-test log hash. No frozen inputs, runtime, batch file or Git action
was changed.

## Primary compatibility and saved processing checkpoint, 2026-11-12

`build_primary_diagnostic.py` now writes `diagnostic.json` and its SHA-bound
`diagnostic-recipe.json`. The diagnostic has 60 original-frame crossing,
controller, frame-map, trace, Native frame and capture-evidence rows, compact
per-frame graphs, a capture manifest, and four generated 20 Hz camera sources.
All are synthetic software inputs, with no physical or legal acceptance claim.
`build_primary_bundle.py` now emits the current exact construction and root
`primary-candidate-manifest.json` with 60 frames. The proposal at
`proposals/cases.json` describes this isolated primary diagnostic; it is not a
complete four-case stage proposal.

The exact primary compatibility command passed in `primary-compat-v6.log`:

```
.venv-cpu/bin/python runtime.py compatibility --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/primary-candidate-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --output .runtime-work/c125763-yield-left-primary-compat-v6 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck
```

Its retained `primary-compatibility-receipt.json`, `primary-analysis.log` and
`primary-negative-analysis.log` bind actual finalization, Native validation,
the required observations, Lean decoder, four source cameras, final video
decode, selected measurements and rejection when
`controller_history.jsonl` is removed. `finalizer.py` now wraps the saved
instance context under the required `entry_context` field. The current
28-test `cpu-tests.log` passes after that change.

Recorded-only saved processing of the same retained positive attempt also
passes in `primary-saved-v1.log`:

```
.venv-cpu/bin/python runtime.py process-saved --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/primary-candidate-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --attempt .runtime-work/c125763-yield-left-primary-compat-v6 --output .runtime-work/c125763-yield-left-primary-saved-v1 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck
```

`primary-saved-receipt.json` reports `passed: true`, `recorded_only: true`,
`originals_preserved: true`, `physical_acceptance_claimed: false`. The
isolated primary manifest binds its current construction hash, offline log and
compatibility receipt. It is deliberately not the complete
`execution-manifest.json`: three other selected cases, their tested fallbacks,
complete canonical proposals, audits of all real comparison pairs and full
assignment readiness still need CPU construction and proof. Preserve partial
status until those proofs pass. Rebuilds change hashes and require rerunning
the affected offline, compatibility and saved checks. No frozen inputs,
runtime, batch file or Git action was changed.

After these changes, `.venv-cpu/bin/python worker_check.py --assignment
testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete` exits 0
in `assignment-check.log`. The final full
`.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`
exits 1 in `strict-gate.log` with `Preparation acceptance failed:
partial/missing packages remain`. This is the current batch status; the
primary synthetic proof is a partial checkpoint only.

## Source-bound right-side case and comparison checkpoint, 2026-11-12

`site_packet.py` now includes both approach routes and the ego yield line in
the hash-bound crossing source document. The new
`test_changed_approach_route_rejected_by_source_binding` rejects a route edit
when its review source has not changed; the assignment suite now passes **29
tests** in `cpu-tests.log`. Rebuilding the primary changed its construction
hash, so its exact offline, compatibility and saved-processing proofs were all
rerun. The current primary logs are `primary-offline-v5.log`,
`primary-compat-v7.log` and `primary-saved-v2.log`; the corresponding current
receipt is `primary-compatibility-receipt.json`.

`build_right_case.py` constructs
`testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_right_near_time`
with the other approach routed from the north through the same synthetic
crossing, a reversed approach heading and a reviewed-source hash updated for
that route. Its diagnostic moves the original pre-entry other body to the
opposite side while holding the first complete-body entry-time difference
fixed. `right-candidate-manifest.json` binds its current construction and
recipe. Build it after the primary bundle and diagnostic:

```
.venv-cpu/bin/python work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/build_primary_bundle.py
.venv-cpu/bin/python work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/build_primary_diagnostic.py
.venv-cpu/bin/python work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/build_right_case.py
```

The right case passes exact `runtime.py offline` in `right-offline-v1.log`,
positive and missing-`controller_history.jsonl` negative compatibility in
`right-compat-v1.log`, and recorded-only `runtime.py process-saved` in
`right-saved-v1.log`. The retained right compatibility and saved receipts are
`right-compatibility-receipt.json` and `right-saved-receipt.json`.
`audit_comparisons.py` now reads the actual `analysis-report.json` emitted by
compatibility and passes the exact `yield_sign_relative_side` pair in
`relative-side-audit-v1.log`, using the current primary attempt
`.runtime-work/c125763-yield-left-primary-compat-v7` and right attempt
`.runtime-work/c125763-yield-right-compat-v1`. Both measured entry-time
differences are 0.05 s; the measured relative side changes as declared.
This is software evidence from synthetic sources, not physical or legal
acceptance.

The next selected construction is
`testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_separated`:
retain the sourced crossing, sign, lanes and left-side approach; change the
other release timing and build a source-shaped diagnostic that demonstrates a
larger measured complete-body entry-time difference without assigning a legal
cutoff. Then prove offline, compatibility, saved processing and the declared
`yield_sign_entry_timing` comparison. The opposite-direction left-turn case,
all required tested fallbacks, full canonical proposals and delivery audit
remain worker-owned CPU work. Both near-time manifests are isolated partial
diagnostics; neither is a complete assignment execution manifest. No status
was marked ready and no frozen input, runtime, batch file or Git action was
changed.

The final recheck for this two-case checkpoint passed pinned
`runtime.py preflight` (`preflight.log`), the 29-test assignment suite
(`cpu-tests.log`), and scoped `worker_check.py --assignment
testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete`
(`assignment-check.log`). `worker_check.py --updates` reports version 0 and
no paused assignments (`updates.log`). Full
`.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`
still exits 1 in `strict-gate.log` with `Preparation acceptance failed:
partial/missing packages remain`. `result.json` stays partial and binds the
current CPU test log hash.

## Four selected-case CPU checkpoint, 2026-11-12

The installed pinned CPU environment passes `preflight.log`; the assignment
suite passes 29 tests in `cpu-tests.log`. The near-time primary and right
constructions were rebuilt with `other_release_frame: 20` so the configured
release precedes the observed body entry at frame index 30. Their current
exact offline, compatibility and saved-processing logs are
`primary-offline-v6.log`, `primary-compat-v8.log`, `primary-saved-v3.log` and
`right-offline-v2.log`, `right-compat-v2.log`, `right-saved-v2.log`. These
supersede earlier proof versions. The bound receipts are
`primary-compatibility-receipt.json`, `primary-saved-receipt.json`,
`right-compatibility-receipt.json` and `right-saved-receipt.json`.

`build_separated_case.py` constructs `yield_ego_left_separated` from the
same synthetic sign, crossing and left-side approaches, with other release
at frame index 5 and original-body entry at index 20. It passes exact
offline (`separated-offline-v1.log`), positive and missing-controller-source
negative compatibility (`separated-compat-v1.log`), and recorded-only saved
processing (`separated-saved-v1.log`). Its isolated manifest and receipts are
`separated-candidate-manifest.json`, `separated-compatibility-receipt.json`
and `separated-saved-receipt.json`.

`build_opposite_case.py` constructs `yield_opposite_left_turn` with an
opposing same-highway approach, a source-bound turn route and original-frame
left-turn intention in both the crossing and controller histories. Its first
offline attempt exposed a missing site relation declaration; that was fixed
in the builder before its exact proofs. The current exact offline
(`opposite-offline-v2.log`), positive and missing-controller-source negative
compatibility (`opposite-compat-v1.log`), and recorded-only saved processing
(`opposite-saved-v1.log`) all pass. `opposite-candidate-manifest.json` binds
the current construction and receipt; the retained receipts are
`opposite-compatibility-receipt.json` and `opposite-saved-receipt.json`.

The source-integrity checks in `audit_comparisons.py` pass both declared
software pairs on the current compatibility attempts: relative-side entry
gaps are 0.05/0.05 s (`relative-side-audit-v2.log`); timing entry gaps are
0.05/0.55 s (`entry-timing-audit-v1.log`). The complete declared-pair audit
passes in `comparisons-audit-v1.log`. It checks the controlled release-frame
change as well as the measured original-frame gap. These are synthetic CPU
diagnostics with physical and legal acceptance explicitly unresolved; no
numeric legal cutoff was inferred.

All four selected cases have isolated partial manifests. A complete
`execution-manifest.json` and full canonical proposals are still needed.
Build and prove three distinct physical-risk fallback constructions per
selected case, then run their exact offline, compatibility and saved checks,
the full independent delivery audit, the assignment readiness gate and the
strict batch gate. The fallback and site-review work is worker-owned; no
status was changed to ready. `result.json` remains partial and binds the
current test log. No frozen inputs, runtime, batch file or Git action was
changed.

The final recheck passed `worker_check.py --updates` (`updates.log`) and the
scoped `worker_check.py --assignment
testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete`
(`assignment-check.log`). The full `.venv-cpu/bin/python worker_check.py
--complete --require-delivery-ready` exited 1 in `strict-gate.log` with
`Preparation acceptance failed: partial/missing packages remain`. Delivery
readiness has not passed; continue the worker-owned fallback and delivery
construction from this checkpoint.

## Twelve fallback proof checkpoint, 2026-11-12

`build_fallbacks.py` prepares `fallback1`, `fallback2` and `fallback3` for
each of the four exact selected cases. The changes respond to distinct
physical risks: insufficient ego braking distance (move ego spawn 5 m
upstream), other-vehicle spawn clearance (move the other spawn 5 m upstream),
and overview visibility (shift and raise that camera). Each fallback keeps
its case identity, crossing, approach headings, release timing, observation
contract and comparison variable. The first two source-bound approach changes
also update the crossing-geometry source document and site hash. All three
alternatives are available with the same policy across linked cases.

All twelve pass exact `runtime.py offline --candidate fallbackN` in
`{primary,right,separated,opposite}-fallback{1,2,3}-offline-v1.log`.
All twelve pass positive and missing-controller-source negative
`runtime.py compatibility --candidate fallbackN` in the corresponding
`-compat-v1.log`; retained `-compatibility-receipt.json`, `-analysis.log` and
`-negative-analysis.log` files are bound in the four isolated manifests.
All twelve pass recorded-only `runtime.py process-saved` in the corresponding
`-saved-v1.log`; the retained `-saved-receipt.json` files are also bound there.
For example, the exact primary fallback1 commands are:

```
.venv-cpu/bin/python runtime.py offline --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/primary-candidate-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --candidate fallback1 --output .runtime-work/c125763-primary-fallback1-offline-v1
.venv-cpu/bin/python runtime.py compatibility --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/primary-candidate-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --candidate fallback1 --output .runtime-work/c125763-primary-fallback1-compat-v1 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck
.venv-cpu/bin/python runtime.py process-saved --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/primary-candidate-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --attempt .runtime-work/c125763-primary-fallback1-compat-v1 --output .runtime-work/c125763-primary-fallback1-saved-v1 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck
```

The runtime `candidate_constructions.validate` accepts all four case entries
with `required=True`, `require_alternate=True` and `candidate_count=4` in
`fallback-validation.log`. The nonmutating fallback geometry test checks the
changed knobs and preserved comparison variables for all four cases; the
assignment suite now passes 30 tests in `cpu-tests.log`. Pinned preflight
remains passed in `preflight.log`. `worker_check.py --updates` passes in
`updates.log`; the scoped `worker_check.py --assignment
testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete` passes in
`assignment-check.log`.

The next CPU work is a complete canonical `execution-manifest.json` and
semantic proposals, physical-preparation fixtures for complete, incomplete
and missing-evidence outcomes, independent delivery acceptance audits and
their negative proofs, then exact assignment readiness and the batch strict
gate. The current four manifests are isolated partial diagnostic manifests;
they do not prove canonical physical or legal acceptance. `result.json`
remains partial with the current 30-test log hash. No frozen inputs, runtime,
batch file or Git action was changed.

The fresh full `.venv-cpu/bin/python worker_check.py --complete
--require-delivery-ready` exits 1 in `strict-gate.log` with `Preparation
acceptance failed: partial/missing packages remain`. This is a batch
readiness failure, not a failure of the twelve bound fallback CPU proofs.

## Canonical manifest and physical-classifier checkpoint, 2026-11-12

`build_execution_manifest.py` assembled the four selected case entries,
including their twelve proved fallback candidates, into the draft canonical
`execution-manifest.json`. The manifest retains partial status and names
remaining delivery work. `audit_delivery.py` passed original-source integrity
checks on all four current primary compatibility attempts in
`source-audit-four-cases.log`; each has 60 joined original frames and reports
`delivery_ready: false`.

`physical_fixture_proof.py` and `build_physical_proofs.py` now generate and
bind a per-case CPU classifier receipt under `physical-proofs/<case>/`. For
each selected case they exercise an authored complete crossing-clearance
motion, held incomplete motion, missing body history, failed encoder
rejection, premature owner-release rejection, and the ordered capture seal,
Native exit, owner release and saved-processing lifecycle. The complete
motion is a synthetic classifier fixture derived from the case's source
shape; it is not a CARLA capture or a claim that real motion occurred.
`physical-proofs-current.log` records all four passing fixture runs. The
frozen runtime `physical_preparation.validate` accepts every bound receipt.

The exact `.venv-cpu/bin/python` validation of
`worker_exchange.execution_manifest.validate(repo, assignment_id)` now
passes for the four-case `execution-manifest.json` in
`execution-manifest-validation.log`. The expanded assignment suite passes
32 tests in `cpu-tests.log`, including stale physical-proof rejection.
The remaining CPU work is validated canonical semantic stage proposals,
independent delivery-acceptance positive and negative proofs, and
recorded-only saved reruns using the canonical manifest path. These are
worker-owned; retain partial status until the full assignment and batch
readiness gates pass. No frozen inputs, runtime, batch file or Git action
was changed.

## Canonical manifest snapshot saved processing, 2026-11-12

All four current primary cases also pass `runtime.py compatibility` and
`runtime.py process-saved` when invoked with the new canonical
`execution-manifest.json`, in `canonical-{primary,right,separated,opposite}-compat-v1.log`
and `canonical-{primary,right,separated,opposite}-saved-v1.log`. Their retained
receipts and current manifest SHA are bound in `canonical-proof-index.json`.
For example, the primary commands are:

```
.venv-cpu/bin/python runtime.py compatibility --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --output .runtime-work/c125763-canonical-primary-compat-v1 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck
.venv-cpu/bin/python runtime.py process-saved --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --attempt .runtime-work/c125763-canonical-primary-compat-v1 --output .runtime-work/c125763-canonical-primary-saved-v1 --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck
```

Candidate-selection receipts bind the manifest bytes. Future edits to
`execution-manifest.json` require rerunning these canonical-snapshot checks
and refreshing `canonical-proof-index.json`. The assignment suite now passes
33 tests, including the current snapshot receipt/hash join. The manifest and
all receipts still explicitly retain partial/software scope.

The final checkpoint rerun passes `worker_check.py --updates` in `updates.log` and the scoped `worker_check.py --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete` in `assignment-check.log`. The full `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 in `strict-gate.log` with `Preparation acceptance failed: partial/missing packages remain`. The goal and this package remain active/partial.

## Four-camera independent CPU decode checkpoint, 2026-11-12

`audit_delivery.py` now optionally checks the exact requested case, probes all
four named original streams and fully decodes all 60 frames in each stream,
binding the decoded RGB sequence and source SHA to the joined frame map.
`prove_delivery_decode.py` ran this check on all four retained canonical
compatibility attempts and then rejected an attempt missing `approach.mkv`
for each case. The exact command is:

```
.venv-cpu/bin/python work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/prove_delivery_decode.py
```

`delivery-decode-proof.log` holds four positive/negative results. The
`full-decode-{primary,right,separated,opposite}.log` files hold decoded
source hashes and frame counts. `runtime.py preflight` and the 33-test
assignment suite pass in `preflight.log` and `cpu-tests.log`. These CPU
proofs establish source integrity and complete decoding of synthetic
retained videos. Independent actor-pixel review, actual Native motion,
physical completion and a per-case delivery acceptance contract still need
authored proofs. The package remains partial and delivery_ready is false.
No frozen inputs, runtime, batch file or Git action was changed.

The same-law and same-actor canonical `proposals/template.json` is now
authored by source-backed reuse from C125714. `template-validation.log`
confirms it passes the frozen `batch_pipeline.stages.validate('template', ...)`
contract with C125763's exact law record. The relevance, observables,
bindings, cases and semantic index remain to be assembled and validated.

`proposals/relevance-batch.json` and `proposals/relevance.json` now bind
the same-law review to C125763's exact median-opening cell and actor.
`relevance-validation.log` records both canonical stage validators passing.
The other semantic stages and the aggregate index are still pending.

Final gate rerun: `.venv-cpu/bin/python worker_check.py --assignment
testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete`
exits 0 in `assignment-check.log`. The full `.venv-cpu/bin/python
worker_check.py --complete --require-delivery-ready` exits 1 in
`strict-gate.log` with `Preparation acceptance failed: partial/missing
packages remain`. Continue from the remaining semantic stage chain and
independent delivery acceptance checks; retain partial until their CPU
proofs and both readiness gates pass.

Four same-law `proposals/judgment-observables-{1,2,3,4}.json` files and
exact-cell `proposals/bindings.json` now pass their stage validators in
`observables-bindings-validation.log`. A cases-stage validation of the
existing C125763 diagnostic draft was attempted in
`cases-stage-validation.log`; the validator requires the missing declared
controller/behavior variables, a shared baseline, and a complete recording
description. The cases file was not changed by this failed trial. Author
those missing case details without changing exact selected case IDs or their
construction recording descriptions, then build and validate the semantic
index.

## Canonical semantic-stage checkpoint, 2026-11-12

`build_semantic_cases.py` now fills the four exact case proposals with all
declared binding variables, a separate shared baseline, honest comparison
differences, and four unresolved qualitative sweep plans. The case IDs and
recording descriptions remain exactly those in the four construction files.
C125763's judgment observables now name the actual `entry_timing` stream
and source-hashed `entry_context` packet produced by its finalizer; the packet
contains crossing, approach, device, turn-intent and yield-control
measurements derived from retained original sources.

The aggregate `proposals/semantic-index.json` binds all stage hashes.
`semantic-validation.log` records
`worker_exchange.semantic_delivery.validate(...)` passing for the exact
frozen assignment and current four-case execution manifest. The canonical
semantic proposals remain drafts; no legal judgment or physical acceptance
is inferred. Independent per-case delivery acceptance and final manifest
refresh remain worker-owned.
