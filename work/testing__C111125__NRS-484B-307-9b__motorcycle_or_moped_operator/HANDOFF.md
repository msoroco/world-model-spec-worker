# testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator

## 2026-11-24 source-gated Native event session checkpoint

- `native_session.py` adds a concrete event acquisition bridge for all six exact straight-route cases. It verifies the case-matched nondiagnostic site packet and SHA-sealed map, route, signal, stop and crosswalk sources, copies those original bytes into the pinned runtime's materialized attempt directory, checks for prior acquisition files, binds the Native map/head/blueprint through `signal_exception.construct_native`, records 900 original event frames through `original_capture.capture_original`, and destroys the ego in a `finally` block. It records the unchanged site SHA and explicit `camera_media_status: not_acquired_by_event_session`. The operator-owned session remains responsible for world lifecycle, actor/sensor context and restoration; this bridge does not assert a complete video capture or physical/legal acceptance.
- Each rebuilt bundle runner now accepts `runtime.py capture`'s `--output-dir --host --port` shape using explicit `SCENARIO_SITE_PACKET` and `SCENARIO_NATIVE_ADAPTER` operator bindings. Its embedded test mocks the exact dispatch, and `tests/test_native_session.py` checks source copying, actor cleanup after failure and missing/reused source rejection. Pinned CPU preflight, 25 focused tests, all six exact `runtime.py offline` checks and scoped static pass. Exact scoped strict exits 1 on truthful partial. All commands and log hashes are in `result.json.tests`.
- Remaining CPU work: reviewed original composite-head/detector and stop-reference site, four-camera same-frame acquisition and decode, canonical semantic proposals/manifest, positive/negative compatibility, saved delivery and independent audit receipts. The turn branch is outside this fixed straight cell. No diagnostic event source proves detector causality, participant lawfulness or pixel visibility.

Status: partial construction and audit draft. Six exact cases are planned; no Native recording or physical acceptance is claimed.

Exact law: NRS 484B.307(9)(b) — Where the signal is a steady red with a green turn arrow: A person driving a motorcycle, moped or trimobile or riding a bicycle, an electric bicycle or an electric scooter facing the signal may proceed straight through or turn in the direction opposite that indicated by the green turn arrow if: (1) The person stops before entering the crosswalk on the nearest side of the intersection where the sign or pavement marking indicates where the stop must be made or, in the absence of any such crosswalk, sign or marking, before entering the intersection; (2) The person waits for two complete cycles of the lights or lighted arrows of the applicable official traffic-control device and the signal does not change because of a malfunction or because the signal failed to detect the presence of the motorcycle, moped, trimobile, bicycle, electric bicycle or electric scooter; (3) No other device at the place prohibits the turn, if applicable; and (4) The person yields the right-of-way to pedestrians lawfully within an adjacent crosswalk and to other traffic lawfully using the intersection.
Assigned branch(es): Straight-through permission.
Cell: C111125 (intersection, straight, traffic_light); actor: motorcycle_or_moped_operator.
Frozen accepted recordings reviewed at metadata level: 0. `case-plan.json.evidence_review` identifies the empty inventory and exact missing original evidence.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Resolve source-surveyed C111125 Native map, official composite steady-red plus green-arrow head, exact stopping-reference hierarchy and motorcycle blueprint; make the source packet used by `signal_exception.py` for each case. Its detector/malfunction packet must document a positive causal source; unchanged light alone is insufficient.
2. Build the six exact runner/config/construction/finalizer bundles and measurement contracts for `case-plan.json.cases`. Wire the local Native adapter to `original_capture.capture_original`, then bind its event receipt and `saved_measurement.process_saved` to the finalizer. Add lawful-status source facts and participant motion for the pedestrian and traffic cases.
3. Produce canonical semantic proposals, exact offline and positive/negative compatibility receipts, saved-only receipts, independent pixel review and risk-triggered candidate receipts. Bind `comparison_audit.py` and `delivery_audit.py` to the saved attempt path; expand tests to those integration paths.
4. Rerun the exact strict gate and mark ready only if it passes. Keep original inputs and runtime frozen.

## Implemented coverage and CPU proofs

`case-plan.json` maps the fixed straight task to `two_cycles_clear`, `one_cycle_entry`, `rolling_entry`, `no_causal_record`, `pedestrian_crosswalk`, and `lawful_traffic`. Five comparisons cover complete-cycle timing, stop evidence, causal failure evidence and yielding to crosswalk pedestrians and other traffic. The rolling case cannot have two cycles *after* a stop that never happened; its separate approach-phase cycle target is explicit, and the comparison records that resulting temporal coupling. The opposite-arrow turn named by the statute is outside this fixed straight cell; a separate compatible turn cell is needed for that branch in the shared branch matrix.

`signal_exception.py` source-seals the map/route/head/stop/crosswalk/cause packets, requires the fixed actor and straight route, verifies Native map/head/blueprint readback before spawn, measures original stop and composite aspect-return cycles, and applies a conservative hold/yield controller. The causal packet must affirm malfunction or missed detection with a supported original method and matching head, actor and interval. `original_capture.py` now records exactly 900 20 Hz Native-shaped world snapshots, including original head/ego/participant readback; it rejects frame gaps, rate drift, actor substitutions, authored-target samples and missing participant inventories before writing a SHA-256-sealed event trace. Its receipt feeds `signal_exception.measure_attempt` directly. The local runner still needs to supply a real Native adapter. `comparison_audit.py` checks fixed source hashes and deliberate measured differences without legal verdicts. `delivery_audit.py` checks an independent saved attempt for sealed original sources, 900 contiguous frames, head/actor continuity and four synchronized 20 Hz camera inventories; a later pixel review must establish legibility and visibility.

`saved_measurement.py` joins that same event receipt with the independently checked saved acquisition, exact site hashes, exact case identity and measured participant regions. It leaves participant lawfulness unresolved and writes no legal or physical acceptance. A 900-frame diagnostic fixture exercises its positive path and a site/acquisition hash mismatch rejection. The diagnostic camera files only exercise the inventory join; they do not establish decoded media or visible bodies.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator/tests -v` passed 16 tests. See `cpu-tests.log` and its SHA-256 in `result.json`. The new positive tests round-trip a 900-frame sealed trace into the original measurement and saved join; negative tests reject frame, time, actor and source defects. The tests use small source-shaped fixtures and fake Native world injection, not a CARLA run. Exact strict assignment check fails with `Preparation acceptance failed: partial/missing packages remain`, as expected for the truthful partial status; see `cpu-strict-check.log`.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU continuation

Cycle measurement now counts aspect-return cycles only when both boundary frames precede intersection entry. The measured output preserves `cycle_frame_bounds_before_entry`; an early-entry regression rejects later cycles as waiting history. `media_decode.py` verifies the source hash, 20 Hz stream, dimensions and exact frame count with ffprobe and fully decodes video with ffmpeg. This is an independent saved-camera check for eventual real media; the existing textual diagnostic camera inventory still does not establish physical image evidence. Its positive test generates a small temporary FFV1 video, and negative tests reject count, hash, corrupt media and incomplete four-view inventory. No binary media is returned.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator/tests -v` passed 21 tests (`cpu-tests.log`, SHA-256 `8fd24bff566bb19234da946200b76390022a4e3723abf9c8867b997df9d063cd`). Scoped `worker_check.py --assignment testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator` passed static checks (`cpu-static-check.log`). Exact scoped `--complete --require-delivery-ready` failed on truthful partial status (`cpu-strict-check.log`).

Next CPU actions: implement actual Native adapter and source-surveyed signal/stop hierarchy; bind the media decoder to source-sealed real capture and physical pixel review; finish six exact case bundles, semantic proposals, offline and compatibility receipts, saved-only processing, and justified candidates. Rerun focused and strict checks before any ready claim.

The saved-media command line now accepts an exact source-hashed manifest, requires 900 frames at 20 Hz for all four views, and writes a case-bound decode receipt while leaving physical visibility unreviewed. A temporary 900-frame FFV1 positive test and manifest-hash negative test exercise this path.

## 2026-11-23 six-case offline diagnostic bundle checkpoint

`build_offline_draft.py` now packages all six exact straight-route cases with source-sealed construction, 900-frame capture, saved measurement, comparison, delivery and media-decode modules. Each runner binds its case parameters and case-plan SHA256, requires 20 Hz for 45 seconds and pinned overview/approach/reference_corner/driver_reference camera names, and refuses unsourced Native launch. `tests/test_offline_bundles.py` verifies exact case coverage, construction hashes, copied source files and per-case parameters. All six exact `runtime.py offline` checks pass without starting simulation; 22 focused tests, pinned preflight and scoped static pass. Scoped strict exits 1 on truthful partial. These are diagnostic bundles; production Native adapter, source-surveyed map/head/stop/detector facts, canonical proposals and manifest, positive/negative compatibility, saved-only delivery and independent audit receipts remain CPU work. No physical or legal acceptance is inferred.

- `cpu-bundles-offline-two_cycles_clear.log` SHA256 `17e295c6bd47297b1f1c190f96cb01e49955c63cbe583ec6983d21b61eb7ed23`.
- `cpu-bundles-offline-one_cycle_entry.log` SHA256 `b39d0f5f8fa60679fd887000cdfe918cbb89ed882e1f39e84350078897ca8fe2`.
- `cpu-bundles-offline-rolling_entry.log` SHA256 `50a74f77e0e88b79b9e2183665dbac00a1f43374459c6380aafc53a7b17f5fe0`.
- `cpu-bundles-offline-no_causal_record.log` SHA256 `fe0ab571db084b42f4f644d8c3619316ce8e778ffb11e8a56e0c9bbebf58b159`.
- `cpu-bundles-offline-pedestrian_crosswalk.log` SHA256 `715dc6d37f110a779b4e9cd52939041bbf97019f9fec8c57b891f7bead87778a`.
- `cpu-bundles-offline-lawful_traffic.log` SHA256 `844cc8cbf854d696a901b086f5b58e64ce466de708452755e763300a73897c9d`.
- `cpu-bundles-build.log` SHA256 `b79e7729570b9217e7d2c99557393d9657190f277abd6ec82ff4b2bf49436d0a`.
- `cpu-bundles-tests.log` SHA256 `cc6c6b964b89e7a625a691d2fce5a7e1d674f7f6c971c20ba65e0c4abc7dec72`.
- `cpu-bundles-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `cpu-bundles-static.log` SHA256 `d335ac8877e30febadcb5366d0c1d9ab7b2949d3897022e1d86298fe7ffec1e4`.
- `cpu-bundles-strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.
