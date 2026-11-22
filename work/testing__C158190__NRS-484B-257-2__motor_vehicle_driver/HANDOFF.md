# C158190 CPU handoff — NRS 484B.257(2)

Status: **partial**. The frozen binding assigns stop-sign governance on a one-way-to-two-way intersection to this cell because C158208 has a fixed yield sign. The exact law requires compliance with the sign before entry and continued caution/yield to non-obligated traffic within or immediately approaching the intersection; officer and signal control are express exceptions. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` names stop/occupancy, approaching-traffic, no-traffic, rolling-response and signal-exception cases. `stop_entry_measurements.py` reads original-frame speed, stop-reference and complete-body occupancy observations, a source-backed full entrance inventory and original video-frame join. It reports whether a complete stop preceded entry and whether another body occupied the junction, leaving immediate hazard, caution and legal yield unresolved. Two CPU tests pass in `cpu-tests.log`; they include active-officer and stale-frame rejection.

Next CPU work: source a non-through-highway junction and all entrance obligations, construct actual Native stop sign and two routes, implement stop controller and four raw source cameras, approaching-hazard timing source channel and saved finalizer, three distinct physical-risk fallbacks per selected case, semantic proposals and independent audits. Run exact offline, compatibility and saved-processing proofs, then assignment-scoped strict gate. Physical geometry, control, motion, visibility and judgment context remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158190__NRS-484B-257-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The full strict gate now reports missing result `testing__C158208__NRS-484B-257-1__motor_vehicle_driver` in `strict-gate.log`. It is unfinished worker preparation, not an external dependency.

## 2026-11-22 stop-sign construction checkpoint

Authored `native-map-plan/stop-sign-crossing.xodr` with a lane-valid OpenDRIVE type 206 stop control at the one-way C158190 entrance. `stop_site.py` validates the road inventory, one-way and two-way lane connections, junction membership, sign control and Native sign trigger readback. Its CPU authored-site validation passed; Native loading, face legibility, entrance obligations and non-through-highway status remain source review checks.

`stop_construction.py` stages four stop-sign cases on the authored lanes: competing vehicle inside, approaching, absent and rolling-response contrast. It rejects the signal-control exception until a separate Native control variant is authored. Its `StopStage` requests a pre-reference halt, holds while the competing path is occupied and then requests crossing; it records construction targets only, never a legal stop or hazard verdict. `tests/test_stop_entry.py` covers the authored site, wrong-sign rejection, exact case staging and controller hold/release. The pinned CPU preflight and six CPU unit tests passed. Assignment-scoped `worker_check.py --complete` passed with truthful partial status.

Next: implement and test the full Native runner with four source cameras and source channels, then one primary exact saved-processing path; add signal exception construction, remaining case bundles, fallbacks, independent delivery/comparison audits and scoped strict gate. Keep status partial until those proofs pass.

`stop_site.observe_stop_control` now retains exact Native stop-sign identity, four trigger vertices, other stop/signal controls and crosswalk inventory at each joined frame. A CPU fake-world test verifies valid sampling and rejects stale frames or sign identity changes. Sign face, non-through status and all entrance obligations remain explicit source-review questions.

## 2026-11-22 first Native capture path

Added `config.json` and `runner.py` for `stop_other_inside`. The CPU `runner.py --check` command exited 0 without starting simulation. The runner stages the authored stop-sign world and selected motor vehicles, requests a stop before the authored engineering reference, captures all four named source cameras at 20 Hz for 30 seconds, joins each sensor frame to a Native tick, retains per-frame control inventory and actor body/speed/occupancy rows, invokes the pinned PipelineCapture and seals only after lifecycle cleanup. Its original `intersection_context.json` deliberately leaves non-through-highway status, officer/signal exception and entrance obligations unresolved pending original-source review; these are not asserted by the CPU check. `stop_entry_measurements.py` now accepts only the authored approach/crossing/exit route and rejects off-route histories. Eight CPU tests pass.

Next CPU work: add a hash-bound source-review receipt without editing captured originals, then a saved finalizer and a primary diagnostic process-saved proof; complete the other cases, signal exception, fallbacks, proposals and audits.

## 2026-11-22 source-review and saved-finalizer checkpoint

`stop_entry_measurements.py` now accepts a separate `stop_context_review.json` only when its reviewer, method, Native map/sign identities, stop-reference hierarchy, full entrance inventory and exact SHA-256 bindings to the original context, frame histories, Native control inventory and four camera files match. It never modifies captured originals. The review findings are scoped to source observations; the analyzer still leaves immediate hazard, caution, yielding and legal conclusion unresolved. A mutated camera is rejected.

The same module exposes saved-only `finalize --attempt --output`. It reads immutable original sources and the review, writes three measured channels plus a review channel, invokes the pinned physical-result assessor and writes a native result without physical-acceptance or legal claims. A source-shaped three-frame diagnostic fixture exercised this path and verified the output channels/result; it is not a full media or planned-duration proof. Ten CPU tests pass. Next CPU work: bind the module into an exact construction/manifest, generate a 600-frame four-view diagnostic fixture and run `runtime.py offline`, positive/negative `compatibility`, and `process-saved` for the primary case; then complete remaining cases and audits.

## 2026-11-22 first exact offline proof

`construction.json` inlines the current runner, stop-site map/validator, controller, saved analyzer, config and ten CPU tests. `execution-manifest.json` binds the first exact `stop_other_inside` construction SHA and primary offline proof. `runtime.py offline` materialized this bundle under `.runtime-work/` and ran its `--check` plus ten tests successfully; its output is appended to `cpu-tests.log` and hash-bound in the manifest/result. The first invocation with a relative `--python` could not resolve the interpreter after the runtime changed working directory; rerunning with `$PWD/.venv-cpu/bin/python` succeeded. No CARLA or physical acceptance was involved.

The manifest is deliberately partial: it has only the first exact case and no fallback or compatibility receipts. Next is first-case positive/negative compatibility and recorded-only process-saved proof, then the other four cases and three distinct physical-risk fallbacks each, semantic proposals, independent audits and scoped strict gate.

## 2026-11-22 first-case measurement contract refresh

The authored-site and actor-staging modules were consolidated into `runner.py` to meet the 8,600-file return cap. All ten CPU tests pass. The first-case `construction.json` now embeds the current runner, saved finalizer, `measurement-contract.json`, configuration, map and tests. The five selected requirement rows bind stop observation, other occupancy, signed-entrance inventory, control exceptions and approaching-hazard context to named saved outputs and source hashes; the finalizer test uses the pinned measurement verifier. Legal hazard and caution judgments remain unresolved. The exact `runtime.py offline` materialization passed at `.runtime-work/c158190-stop-other-inside-offline-20261122-g`; construction SHA-256 is `95c42dd5758350ad8856148d983d91100064a67b5b4989927d44dd2fcc856652`, and the bound `cpu-tests.log` SHA-256 is `4282af55c114518fc6fc69a9256c3b241787b15ee27fc7fcaae1693ec385cc0d`. Pinned preflight and assignment-scoped partial checker pass.

Next worker CPU construction: build a source-inventoried diagnostic fixture and positive/negative compatibility receipt, then recorded-only saved processing. Complete the other four exact cases, including a distinct signal-control construction, case fallbacks, proposals, comparisons and independent audits. Status stays partial until the scoped strict gate passes.

The sampled approaching-hazard context now retains other-vehicle position and speed from joined Native rows. Occupied-intersection rows without a source position fail validation. Eleven CPU tests and the current exact offline materialization pass. The analysis still makes no immediate-hazard legal cutoff or verdict.

## 2026-11-22 first-case compatibility and saved-processing proof

The current first-case construction SHA-256 is `ee44a42736ff3026f9cd19e6f6a977a860484fc18295acd70e4ec9dcb0d34bd6`. The authored intersection polygon is bound to original ego body vertices for sampled clearance; the saved analyzer cross-checks source occupancy flags against those vertices. Eleven unit tests and exact offline materialization pass. `diagnostic-recipe.json` inventories the authored map and source-shaped four-frame diagnostic specification; `proposals/cases.json` contains a draft exact first-case semantic row. The positive compatibility path runs saved analysis, Native validation, Core conversion, Lean decoder and four-view media decode. Its negative path removes `entry_history.jsonl` and rejects it. `first-primary-compatibility.json`, `first-primary-compatibility-analysis.log` and `first-primary-negative-analysis.log` bind the current recipe and contract. Direct pinned receipt verification passes. Recorded-only `process-saved` passed on the generated synthetic primary attempt with the default primary selection and preserved original sources; `first-primary-saved.log` records that result. `execution-manifest.json` binds these proofs and explicit acquisition mappings. These four diagnostic frames do not claim planned 30-second capture or physical/legal acceptance.

The scoped partial checker passes. Remaining CPU work is the other four exact constructions, a distinct signal-control exception, per-case risk fallbacks, semantic index, physical fixture checks, delivery and comparison audits, queue bindings and scoped strict gate. Do not mark ready until those checks pass. Keep the full gate deferred while batch packages remain partial.

## 2026-11-22 approaching-other offline checkpoint

`cases/stop_other_approaching/construction.json` binds the second exact case to the existing authored through route with the other vehicle initially outside the junction. Its embedded case-specific config and unit-test expectation are distinct from the first case. Eleven embedded unit tests and exact `runtime.py offline` passed with no simulation; construction SHA-256 is `97862985ac837fce069cff4e4ee50ba0d750cbc15f9f295194e7ee1ef5244fd6`, with the hash-bound result in `second-primary-offline.log`. `proposals/cases.json` now has draft semantic rows for both exact cases. Source-shaped approaching diagnostic, selected-measurement contract, positive/negative compatibility and recorded-only saved proof remain next for this case. The assignment remains partial.

## 2026-11-22 four-case proof checkpoint

The approaching-other case now has a source-shaped diagnostic and passing positive/negative compatibility and recorded-only saved-processing proofs. The other vehicle approaches from outside the junction; the fixture records distinct outside and inside samples without claiming an immediate-hazard legal judgment. Construction SHA-256 is `97862985ac837fce069cff4e4ee50ba0d750cbc15f9f295194e7ee1ef5244fd6`.

The no-other case has a distinct construction and source-shaped diagnostic that omit the other actor throughout original entry history, capture and graph sources. Eleven embedded tests, exact offline, positive/negative compatibility and recorded-only saved processing pass. Construction SHA-256 is `c53420154de352495e13910e67981f41f6174506e2b46d4c999e57904ea13f0f`.

The no-halt case has a distinct requested rolling response, a pre-entry diagnostic sample with nonzero ego speed and case-specific test that rejects a stopped fixture as a match for its requested target. Eleven embedded tests, exact offline, positive/negative compatibility and recorded-only saved processing pass. Construction SHA-256 is `fa96d64534ce79bf8cb0137c771e2fade31284dfa059f0065414cef6f0d96b08`.

`execution-manifest.json` binds four case constructions and their offline, compatibility, negative and saved-processing proof paths. Direct pinned `package_compatibility.check_receipts` passes for all four; the assignment-scoped `worker_check.py --complete` passes with partial status. `proposals/cases.json` contains four draft semantic rows. No physical fixture or legal conclusion is claimed from the four-frame diagnostic media. Next CPU construction is a distinct signal-control exception variant and saved analyzer, then per-case risk fallbacks, physical fixture checks, independent delivery/comparison audits, dispatch and the assignment-scoped strict gate. Keep result partial until every required proof passes.

## 2026-11-22 signal-control exception construction checkpoint

Added `signal_exception.py` as a distinct OpenDRIVE map variant generator. It retains the authored type 206 stop sign on road 158190 lane -1, adds a dynamic type 1000001 head farther along that lane, and binds the head to a junction controller. Its CPU `self_check()` rejects a mutated controller reference, checks the exact signed/control IDs and exercises Native affected-lane, trigger-geometry and state readback against a fake world. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C158190__NRS-484B-257-2__motor_vehicle_driver/signal_exception.py` exited 0; generated variant SHA-256 is `7b71aad9b46579ab649eeea705de3447c8a975d26c59a82363ec614508a1729b`. Actual Native signal governance remains unobserved.

The four existing case constructions include the original `tests/test_stop_entry.py` byte-for-byte. A first attempt to add the exception test there caused the partial checker to reject a construction-content mismatch, so that bundled file was restored exactly and the exception self-check lives in its separate module. The existing eleven package tests pass with current `cpu-tests.log` SHA-256 `5500b4f397330eec792e202d75213bff4d63ab8618147a729705f6b3d3d661fa`; the assignment-scoped partial checker passes. Next: connect the variant to an exact fifth-case runner, capture original light state and governing lane each frame, add a distinct saved analyzer and its source-bound proofs, then continue fallbacks, physical fixtures and audits. Status remains partial.
