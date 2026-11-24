## 2026-11-24 selected CPU delivery checkpoint

Status is `ready` with `delivery_prepared` after the exact
assignment-scoped strict CPU delivery gate passed. The exact selected left-turn pair is in
`selected-v2-manifest.json` SHA-256 `7dea33dfccdea1bcf879f096913b6c173c0d75eab9f9fe68fe1819cb88800a1a`. Each case has a source-hashed 600-frame,
20-Hz, four-camera primary and symmetric controller fallback. All four exact
selected paths passed pinned `runtime.py offline`, 11-check public
`runtime.py compatibility` with missing-source rejection, and recorded-only
`runtime.py process-saved`. Durable receipts reside under `selected-v2/proofs/`.

The independent CPU source and comparison audit passes:
`selected-v2/audit.json` SHA-256 `35e26806e9b0c441c1fcb1e8a53974bd691f9d982b2e43052ef118d7a998d294`. Canonical semantic stage validation passes:
`selected-v2/semantic-validation.json` SHA-256 `d33531a72fc753cc3f998a1fbe3b67a8bc836c9ba94057aaa42827fe2f251767`, with source-bound stage index
`proposals/semantic-index.json` SHA-256 `1a2d0f7583ef50bb20bb7676645dc150f2cc2c63817f274eded5db79150cb910`. The exact `full-train` delivery contract
validates both selected cases, including positive and negative audit tests:
`selected-v2/delivery-contract-validation.json` SHA-256 `b1a30647d3e09600b6fc4d3a430d2943e0153db7aba1aff76dbbb663a1253fb9`.

Original-attempt delivery audit implementation is
`selected-v2/delivery_audit.py` SHA-256 `130a8658fd2472a679d75015ce40d9376cd81b86e197fefc021ac41cdb61a9df`. Its CPU fixtures pass for both cases;
each negative rejects a changed driver-reference original camera hash.
Original-attempt comparison audit implementation is
`selected-v2/comparison_audit.py` SHA-256 `91a04cb30f3d7c2d34210d1d03b89d45f32ca093c5693c87e170291d846a1b23`; CPU positive passes and altered-road
negative rejects, as proven by `selected-v2/comparison-positive.log` SHA-256 `477d25423fef94f9dc490fd40755e6f73264e16e8bc63338706fbd6f7e6dcea1` and
`selected-v2/comparison-negative.log` SHA-256 `4ba9a1e52c5131193e3f82a77de665c30e42561cc3c05c4cd98d572a83b24a70`. Its actual mode requires both
original Native attempts and independent physical review receipts, checks
each sealed source and all 600 original frame/camera joins through the delivery
auditor, verifies common fixed conditions, and demands observed distinct
circulating lanes. No actual mode was run and no physical or legal finding is
claimed.

The canonical root package is now materialized at
`execution-manifest.json` SHA-256 `7dea33dfccdea1bcf879f096913b6c173c0d75eab9f9fe68fe1819cb88800a1a` with root `construction.json`, `runner.py`,
`config.json`, and `tests/test_route.py`. Pinned execution-manifest validation
and primary package compatibility receipt checks pass for both exact cases:
`selected-v2/canonical-validation.json` SHA-256 `3e9350666eb95d3f4d8f61496f9bc01e3c7acbd6c2ff193cd8939e78f8ba06d4`. Three synthetic physical
outcome fixtures per case cover complete, incomplete, and missing evidence;
their source-bound proof receipts are
`selected-v2/physical/witness1/proof.json` SHA-256 `909ad8998fcf66b5ebc93b86402359f17ddffb78819d57b7dff8066c2f98ca83` and
`selected-v2/physical/witness2/proof.json` SHA-256 `3ec008532783aa405f45d47e977d6248797faba584db730e705845f5b85035ad`. Root four-test suite passes:
`selected-v2/root-unittest.log` SHA-256 `eb70817cc439ba39a893c76765fa02f746b9b7f9445230e2dd090f210b092df8`. These remain CPU fixture outcomes,
not observed original passage outcomes.

Statutory branch review is `proposals/statutory-branch-review.json` SHA-256 `f75f92375f832fbe1d0bcaa96919547e94222cc35ace72949ffa95d6f49463ec`.
This assignment's frozen cell supports the left-turn pair. The exact-law
`training__C131055__LVMC-11-43-010-C1__motor_vehicle_driver` assignment must
bind the separate U-turn alternative; do not treat this left-turn pair as
covering it. Original legal interpretation remains for local review.

Replay commands from repository root (all scratch must stay under
`.runtime-work/`):

```sh
export PYTHONDONTWRITEBYTECODE=1
export SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c131364-selected-refresh"
.venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/selected-v2/audit.py
.venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/selected-v2/validate_semantic.py
.venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/selected-v2/validate_delivery_contract.py
.venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/selected-v2/validate_canonical.py
.venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/selected-v2/comparison_audit.py --cpu-test positive
.venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/selected-v2/comparison_audit.py --cpu-test negative
.venv-cpu/bin/python worker_check.py --assignment training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --assignment training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver --complete --require-delivery-ready
```

The comparison negative must exit nonzero with `Comparison fixed condition
differs: road_sha256`. The case plan now binds the exact camera profile and
every frozen observation term to retained source or the separate U-turn handoff.
The full assignment-scoped strict CPU gate passed on current source hashes.
Local physical work requires two actual Native
captures, original pixel/roundabout/left-turn/lane-history review receipts,
and original comparison audit. Historical notes follow.

## 2026-11-24 current v2 Native and fallback CPU checkpoint

The current pinned 30-second/600-frame/four-view diagnostic primary has two source-hashed cases. Both `runtime.py offline`, public `runtime.py compatibility` (11 checks including missing roundabout-track negative), and recorded-only `runtime.py process-saved` passed. `v2-diagnostic/audit_cpu_receipts.py` independently checks source and receipt hashes, 600-frame joins, comparison invariants and the deliberate lane -1 versus -2 difference. Receipt `v2-diagnostic/audit-cpu-receipts.json` SHA-256 b4b380b69355061ca2e188a213d45c374481bb951498ae92af1dab826bca54a5.

A separate current-v2 Native draft binds `runner.py` to `native/v2_native_capture.py`, including 600 original ticks, four source cameras, original road/lane readbacks, cleanup/restoration and capture sealing. `native/v2_native_finalize.py` contains a saved-only branch for original readbacks; diagnostic fixtures still take the explicitly synthetic branch. Both draft cases passed pinned offline, 11-check public compatibility and recorded-only process-saved. Audit command: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/v2-native-draft/audit.py`. Draft manifest SHA-256 c7ae04e955df505cd46ad3f44609651622d91a4ae74a0dfc6988fe7e3c105d2b; audit receipt SHA-256 ed8e1d0bcfdf90416c64ff0d10cdfcedc011185e90e2321a917f6f7c235ded7c. `native/test_v2_capture_fake.py` passed a 600-frame/four-camera fake-world attempt and an injected camera-frame mismatch; the negative restored the world and left no seal. The fake original-readback finalizer also accepted the joined 600 rows and rejected a rebound frame mismatch. Test log SHA-256 9b2c19a7d779f0953308de0f0d9dc2f746fec74eabd55bb253a9c8036df88f3b. The independent `native/v2_source_audit.py` (SHA-256 5fc77690964bd9c61ca65d0c5a4c5979e003d7b8deca7c5c62e82a0a66a4a352) checks source seals, original frame/actor/track/map joins, full four-video decode and restoration; the fake-world test exercised its positive path and a source-frame tamper negative. This mock is a CPU state-machine proof, not a CARLA physical result.

A paired `fallback1` controller draft changes the requested speed from 6.0 to 7.5 m/s for both linked witnesses, triggered only if original readback has no road 12 sample after road 11 before frame 600. It leaves law/cell/actor/recording contract and the deliberate lane comparison intact. Both fallback cases passed pinned offline, public compatibility with missing-source rejection, and recorded-only process-saved. Audit command: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver/v2-fallback-draft/audit.py`. Fallback manifest SHA-256 90e54009707fb39cb278bc590813bd71f11d071d288b3e8fd686f9092f4ba87c; audit receipt SHA-256 477ce77d2e9ce4dd2410d28307435a6d023590e095aa3cb3ea89f5da738e54e4.

`proposals/roundabout-binding-draft.json` (SHA-256 3f7c7f7f24eb5aef2107d6b52f567b5b0d692d12222b9e3cc76884d930e29ce9) binds the exact statute, left-turn pair, source observation requirements and pending U-turn alternative. It is not a canonical semantic stage chain. No original CARLA execution, physical roundabout/lane/pixel review or legal verdict is claimed. The selected delivery manifest, full semantic chain, U-turn branch binding, actual original Native run, independent physical/pixel acceptance and comparison audits, and strict ready gate remain. Status: `partial`; selected cases: 0.


## 2026-11-23 source-bound saved CPU continuation

`native/prepare_long_saved.py` now derives 600 timestamped saved rows per
proposed primary witness from the 30-second synthetic packet. Each row binds
the exact source track and all four encoded camera streams by byte hash and
frame/native-frame join (4,800 joins total). It preserves `observed_lane_id:
null`, `camera_pixels_reviewed: false`, and no physical or legal verdict. Two
positives and two altered-source negatives passed: a third-camera frame join,
and a lane mutation with the track hash rebound. `native/audit_long_saved.py`
independently replayed both source/saved joins. Proof and audit:
`native/long-saved-proof.json` SHA-256
`129584d32e74e796cc0c3ae0ef2faea5a6b396fbfa0795b9194ed3e40671d253`;
`native/long-saved-audit.json` SHA-256
`043c610cc9f431565d825272e5481118ec6a055a6e75d85df3d71e8951016d88`.
The saved rows reside only under `.runtime-work/c131364-saved-run/proof-20261123-b/`.

Pinned `runtime.py preflight` and scoped `worker_check.py --complete` passed.
The legacy copied offline proof replay passed eight positives and 40 source
negatives after its temporary directories were moved under `TMPDIR`. That
legacy manifest is not the current runtime `cases` format: `runtime.py offline`
rejected it with `KeyError: 'cases'`. Its independent package audit also found
stale copied source bytes. The first entry's copied assignment hash is
`42034713010efcc100933a0f2d2c68fbc2f66990e715c562168f133989ca630b`,
while the current frozen assignment is
`4dcdfa64a0cff2e2bd3ce50ee41fdf9eb5dbc97d2b73c143d09ba3fd62644be3`;
its copied case-plan hash is
`72c679de4da778ae16be0b7e935469461ea7d3106f4bb848fc2017c988d7f1f3`,
while the current case plan is
`b508fd3e448c5d3faac89abf62e9dcb4074450476223c492f49a4d8aab9236ee`.
The earlier legacy proof therefore covers only its historical copies.

Next: rebase exact construction packets against the current frozen assignment
and case plan, replace the legacy manifest with a current selectable
construction manifest, migrate the connected Native runner and saved processor
to 600 frames and four actual camera sources, then run pinned offline,
compatibility, final decode, and independent acceptance checks. A 160x90
synthetic color packet cannot establish camera visibility, real Native geometry,
continuous lane occupancy, or the observed exit. Both witnesses remain
unselected and the assignment remains `partial`.

## 2026-11-23 current CPU continuation

The pinned `.venv-cpu/bin/python runtime.py preflight` passed, as did
`.venv-cpu/bin/python worker_check.py --assignment training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver --complete`.

`native/long_duration_diagnostic.py` constructs two separate 600-frame, 20 Hz,
30-second authored primary left-exit trajectories, one per proposed circulating
lane. Each has entry, circulation and bounded exit phases. It also encodes four
named synthetic FFV1 streams and binds all 2,400 camera frame identities per
witness to the authored track and video byte hashes. Two positive checks and
three altered-source negatives passed: changed fourth camera frame join,
second camera hash, and route phase with rebound track hash. Receipt:
`native/long-duration-proof.json`, SHA-256
`4633af60d92d0333fc500fd7acad8c5d492cdbe86a76aa26ad04e56a387112e2`.

`native/audit_long_duration.py` independently checked both 600-frame routes,
the radial circulating lane positions, exit bounds, eight full video decodes,
and 4,800 camera frame joins. Receipt: `native/long-duration-audit.json`, SHA-256
`3a59dd0d2e4c0085ca61f59f48297f1787b2b8ace159a6dc5f9057b6bb6c81b7`.
Generated media and frame ledgers are in ignored
`.runtime-work/c131364-long-diagnostic-20261123/`.

These are synthetic CPU source-join diagnostics. The existing exact connected
Native bundles, runner, saved processor and comparison still use 240 frames and
two cameras. They must be migrated to 600 frames and four actual source cameras,
then rerun through current pinned offline, compatibility, saved processing and
independent acceptance paths. The two proposed witnesses remain unselected.
Original Native exit, lane occupancy, physical roundabout geometry, camera
pixels, intended exit evidence and legal interpretation have not been reviewed.
The assignment remains `partial`; no delivery readiness is claimed.

Actor: `motor_vehicle_driver`. Frozen cell: `multilane_roundabout` / `left_turn` / `lane_allocation`.

Exact statutory source: LVMC 11.43.010(C)(1). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Intended left-turn exit.. Planned comparison variable: `roundabout_exit_lane`. Requests: left-exiting driver uses left circulating lane; left-exiting driver uses right circulating lane. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject is in a multi-lane roundabout; the subject intends to turn left or complete a U-turn.

Timing to retain: the intended exit is shown by the exit actually taken, so the whole passage from entry to exit is needed; the left lane must be held through the circulating movement.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: 'intends to exit' is intention; the exit taken is the observable substitute. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.
