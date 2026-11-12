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
`cases/yield_ego_left_near_time/construction.json` and its isolated
`candidate-manifest.json` from an explicitly synthetic five-document yield
site packet. Rebuild with:

```
.venv-cpu/bin/python work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/build_primary_bundle.py
```

The exact offline command below passed (`primary-offline-v2.log` and
`.runtime-work/c125763-yield-left-primary-offline-v2/offline.log`), with all
four named cameras, one materialized CPU test and `carla_started: false`:

```
.venv-cpu/bin/python runtime.py offline --manifest work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/cases/yield_ego_left_near_time/candidate-manifest.json --case testing__C125763__NRS-484B-250-2__motor_vehicle_driver__yield_ego_left_near_time --output .runtime-work/c125763-yield-left-primary-offline-v2
```

This is an isolated partial primary diagnostic. The synthetic packet does not
establish an actual reviewed median opening, an official sign or physical
camera visibility. This candidate manifest also lacks a diagnostic fixture
recipe and does not yet satisfy the full execution-manifest and compatibility
contract. Construct that recipe from retained source-shaped capture data,
place an exact manifest at assignment root when all selected cases are ready,
then run exact compatibility and recorded-only saved-processing proofs. Extend
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
