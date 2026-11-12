# C125745 CPU handoff — NRS 484B.250(2)

Status: **partial**. The frozen branch measures entry timing at a median-opening crossing in a stop-sign cell. The witness relocates this device comparison from C125714. The exact law excludes intersections controlled by official traffic-control devices except as provided in subsection 4, so near-time entry at an official stop sign is an observation, not a violation finding. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` names ego-left/right and close/separated entry-time cases plus opposite-direction left-turn exception context. `stop_sign_control.py` selects a Native stop sign whose trigger contains the ego approach point. `simultaneous_entries.py` requires a source-declared shared median crossing, two different highways, complete original-frame vehicle bodies and sign identity. It reports body entry times and spatial right-side geometry while leaving “approximately,” official-device status, legal yield and subsection-4 questions unresolved. Three CPU tests pass in `cpu-tests.log`, exercising trigger selection, side geometry and wrong-sign/stale-frame rejection.

Next CPU work: source a real statutory crossing through the opening, official sign status and all entrance obligations; construct two routes and stop/yield controllers; capture four named raw cameras and original body/sign/road sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Actual sign, crossing, body timing and visibility remain later source/CARLA checks; the listed construction and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125745__NRS-484B-250-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C125763__NRS-484B-250-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## Median route and opposite exception checkpoint, 2026-11-12

`median_route_control.py` now validates two declared routes through the same sourced median polygon, different-highway or opposite-direction relations, the Native stop sign bound to ego's lane, and an ego stop line before the crossing. `stop_yield_control` commands braking to a recorded stop and holds it while the conflict is uncleared. This is pure CPU control logic; scene coordinates remain a reviewed Native input, not a fabricated site. `simultaneous_entries.py` now accepts an opposite-direction left-turn source contract separately from its different-highway branch and returns right-side geometry as inapplicable for that exception. It still leaves official-device, approximate timing, yield and legal conclusions unresolved.

Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C125745__NRS-484B-250-2__motor_vehicle_driver/tests -v`; eight CPU tests pass in `cpu-tests.log`, including rejection of a wrong sign lane, route outside the crossing, missing left-turn intention and passage beyond the stop line without a stop. Pinned `.venv-cpu/bin/python runtime.py preflight` passed this turn. The assignment remains **partial**. Next construction work: source the actual median-opening site and all entrance/sign identities, bind the four case routes, implement the lazy Native runner and four-camera capture, then exact saved finalizers/fallbacks/proofs and independent audits. These are worker-owned CPU tasks. No frozen input, runtime, batch file or Git action was changed.

The pinned preflight output is retained in `preflight.log` (exit 0). The scoped `worker_check.py --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --complete` output is retained in `assignment-check.log` (exit 0). The full `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` run is retained in `strict-gate.log` (exit 1, `Preparation acceptance failed: partial/missing packages remain`). This package and the batch are still partial; the gate was not passed.
The opposite-direction analyzer additionally checks the original pre-entry body centroids against both declared approach headings; a heading/body mismatch fails. The revised eight-test suite passes in `cpu-tests.log`.
After the heading/body check, the assignment `--complete` recheck still exits 0; the final full strict recheck exits 1 at `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. `result.json` remains partial with the final eight-test log hash.

## Native runner and four-camera source checkpoint, 2026-11-12

`native_pair.py` constructs two owned Native vehicles, confirms the ego-governing stop sign ID against the source scene, applies route steering and stop/yield decisions, and destroys spawned actors even after a failed second spawn or capture error. `capture_sources.py` constructs all four 20 Hz source cameras (`overview`, `approach`, `reference_corner`, `driver_reference`), joins their frame IDs to the Native tick, and records original body vertices, road/lane IDs and sign identity. `camera_encoder.py` writes each raw BGRA stream as lossless FFV1. `runner.py` binds a local SHA-verified reviewed site packet, exact case identity and four camera poses; its CPU `--check` is CARLA-lazy. Its Native path restores the world, retains controller history, the context, original body history and frame map, and seals only a successful capture. None of this claims a reviewed physical crossing, official status, legal priority or physical acceptance.

The assignment suite now passes 18 CPU tests in `cpu-tests.log`, including CLI `--check`, wrong sign, second-spawn cleanup, stopped/yield release, camera lifecycle, four-frame join and stale packet rejection. Pinned preflight passes. The exact reviewed site packet is still absent; no invented map coordinates were returned. Next worker-owned steps: source a real C125745 median crossing with the stop sign and all entrance identities, bind the four exact case configs and verify the Native site packet, then implement the primary saved finalizer/measurement contract/diagnostic recipe and run exact offline, positive/negative compatibility and recorded-only saved processing before fallback expansion. Add three distinct physical-risk alternatives per selected case and independent comparison/delivery audits, then semantic proposals and strict gates. Status remains **partial**.
The current `preflight.log` exits 0; `assignment-check.log` exits 0. The final full strict command `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 in `strict-gate.log` at `Preparation acceptance failed: partial/missing packages remain`. `result.json` stays partial and its 18-test log hash is current. No frozen input, runtime, batch file or Git command was changed.

## Saved original-source finalizer checkpoint, 2026-11-12

`finalizer.py` now reads the captured `crossing_history.jsonl`, `controller_history.jsonl`, `video_frames.jsonl`, `junction_context.json`, trace, capture evidence and four camera streams. It checks exact C125745 case identity and approach relation, complete body entry, recorded stop, relative side for non-opposite cases and original controller/frame joins. It writes `channels/entry_context.json`, `channels/entry_timing.jsonl`, a source-hashed six-output measurement report and the pinned Native `result.json` through `physical_result`/`write_result`. `measurement-contract.json` records the six source/input/output bindings and a missing-source negative. Official-device, approximate timing, subsection-4, yield and legal conclusions remain unresolved.

The current assignment tests pass in `cpu-tests.log` (21 tests). They include an actual `finalize()` call using a small source-shaped saved attempt and the pinned Native result writer, plus missing controller-source and broken original-frame join negatives. The test's camera files are placeholders: it does **not** prove full video decode, exact runtime compatibility, `runtime.py process-saved`, or physical visibility. Next worker-owned work is a reviewed C125745 site packet and exact first-case config/construction, a full four-camera diagnostic recipe, then offline, positive/negative compatibility and recorded-only saved-processing proof before fallback expansion. Subsequent case contracts, three distinct fallbacks per selected case, semantic proposals and independent audits remain unfinished. Status remains **partial**.
The opposite-direction exception now requires `junction_context.json.turn_intent_source` to name `controller_history.jsonl` and verifies every joined controller row records `other_left_turn_intended: true`. The revised 22-test suite passes its positive opposite case and rejects missing controller intention. This proves source binding in the CPU fixture, not actual turn motion or statutory application.
The final test log executes 22 distinct tests; the temporary 26-run log duplicated four imported tests and was replaced. The result log hash now matches the 22-test run.
Final pinned preflight (`preflight.log`) and scoped `--complete` (`assignment-check.log`) exit 0. The final `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 in `strict-gate.log` at `Preparation acceptance failed: partial/missing packages remain`. This is unfinished package preparation, not an external dependency; C125745 remains partial. No frozen input, runtime, batch file or Git action was changed.

## Independent software delivery and comparison audits, 2026-11-12

`audit_delivery.py` independently rehashes all original sources named by the Native result and six saved measurements, verifies exact C125745 case identity, complete original frame count/join and stable governing stop-sign ID, and rejects missing or altered sources. It returns `software_source_integrity_passed: true` but `delivery_ready: false`; it does not claim actual pixels, full decode or physical completion. `audit_comparisons.py` checks both declared `stop_sign_relative_side` and `stop_sign_entry_timing` comparisons against source-audited saved attempts. It enforces fixed crossing, ego approach/sign, actor, rate, duration and required observation contract, then verifies the declared side or ordered time difference without a legal cutoff.

The 25-test assignment suite in `cpu-tests.log` passes. Its audit fixtures call the real finalizer and pinned Native writer, then prove rejection of stale camera bytes, a changed crossing with freshly bound sources, and a missing comparison attempt. The camera bytes are synthetic placeholders; these are software source and comparison tests only. The full `worker-delivery-audit` acceptance receipt, real media decode, exact construction/compatibility/saved proofs, and physical/canonical review remain unfinished. This work is **partial**, not a GPU or external blocker.
Current `preflight.log` and `assignment-check.log` exit 0. The final full strict `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 in `strict-gate.log` at `Preparation acceptance failed: partial/missing packages remain`. `result.json` remains partial with the current 25-test log hash. No frozen input, runtime, batch file or Git action was changed.

## Source-bound site construction checkpoint, 2026-11-12

`site_packet.py` requires a structured reviewed candidate packet and five
retained, source-hashed review documents. Each document identifies its role,
review basis, and exact crossing, entrance, sign, face-video or median-spacing
claims. `runner.load_config` rejects changed or mismatched sources before Native
capture. These checks establish source integrity and internal consistency;
the actual reviewed Native median site packet is still to be constructed.

`runner._native_approaches` checks both spawn road/lane identities and the ego
stop-entrance road/lane. The Native sign trigger is checked at the stop entrance
instead of the potentially distant ego spawn. The 28 CPU tests in
`cpu-tests.log` cover a changed review source, a changed sign claim, an
unreviewed packet, wrong other approach, and wrong stop entrance. The pinned
`runtime.py preflight` passes in `preflight.log`.

Next CPU work: construct a genuine reviewed median site packet with its five
retained source documents; bind exact case configs and manifests; author three
distinct physical-risk fallbacks per selected case and source-bound diagnostic
recipes; run exact offline, compatibility, saved-processing and comparison
proofs. The synthetic test packet is only a CPU fixture. Status remains partial.

Final checks for this checkpoint: pinned preflight and all 28 CPU tests pass;
`worker_check.py --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --complete`
exits 0 in `assignment-check.log`. The full
`worker_check.py --complete --require-delivery-ready` exits 1 in
`strict-gate.log` with `Preparation acceptance failed: partial/missing packages
remain`. The batch delivery gate has not passed. `result.json` retains partial
status and the current CPU test-log hash. No frozen inputs, runtime, batch file,
or Git action was changed.
