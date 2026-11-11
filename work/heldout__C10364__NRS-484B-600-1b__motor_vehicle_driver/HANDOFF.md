# heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 pinned decode and participant visibility audit continuation

The current `.venv-cpu/bin/python runtime.py preflight` passes with the pinned
CPU environment and FFmpeg/Lean on PATH. `delivery_audit.py` now runs the pinned
`worker_exchange.media.audit` over the complete composed original `raw.mkv`,
binds the frame-map hash, and returns the exact source-decode receipt path, hash,
and auditor revision. Native audit requires an independent
`participant-visibility-review.json` that names a reviewer and identifies a
visible original frame for ego, pedestrian, and property, each bound to the
corresponding source-camera SHA-256. Missing, stale, or incomplete review is
rejected. A complete decode by itself does not assert participant visibility.
Marked synthetic fixtures report these Native-only checks false.

`tests/test_delivery_pixel_review.py` tests positive source binding and missing
or stale review rejection. The 25-test suite passes (`cpu-tests.log` SHA-256
`07ba96e0eff586ed695afc87e19a4498b1b83993b698a2c8d7805cdff61237fc`).
Nine positive and tampered-source negative diagnostic delivery audits pass. The
rebuilt `execution-manifest.json` SHA-256 is
`3282c43265863a154296ffc9eb3cc9d4aa593627f37468789c2c240c96c24ac7`.
All nine primaries and 27 fallbacks pass current exact offline and
positive/negative compatibility; `execution-reproof.json` SHA-256 is
`6d49e8f27de5f617ece2d31bcb64be4126039a1e1546afd8dcace5047bd4fa56`.
All nine primaries pass exact synthetic saved-only processing;
`execution-saved-proofs.json` SHA-256 is
`cf479ed70a5ab8ddc67755e252d78c428e4b2a358b8b65c652c354c976d50450`.
The pinned execution validator passes. Scoped `worker_check.py --complete`
passes; scoped `--complete --require-delivery-ready` still rejects the partial
result (`worker-check-strict.log`).

Status remains **partial**. Supplied inputs do not contain an original Native
alley polygon/map source with coordinates. The current polygon and all media are
explicitly synthetic diagnostics. Before readiness, bind a verified Native alley
source, run any affected exact proofs, and review actual original pixels and
motion through the Native audit. No physical or legal acceptance is claimed.

## Frozen scope and source

- Law: NRS 484B.600(1)(b) — It is unlawful for any person to drive or operate a vehicle of any kind or character at: Such a rate of speed as to endanger the life, limb or property of any person.
- Cell/actor: C10364 / motor_vehicle_driver; layout `alley`, maneuver `travel`, control `person`.
- Exact input: `inputs/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/assignment.json` (SHA256 `c5bac8329baa1a05a6bd8b0f93ebc799b83b7cda9088e67ab6256b20c7866b63`).
- Witness: `inputs/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/witnesses.json`, source index 200; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: kin.speed, drv.time_to_conflict, rel.surface_gap, ru.pedestrian, drv.vulnerable_road_user, drv.stopping_distance, rel.contact, st.obstruction.

## Required source and construction review

1. Construct the person's location, motion and owned property relative to the ego route and verify alley clearance and actor support.
2. Establish qualifying motor vehicle, driving or operation, driver identity and automation status.
3. Establish qualifying vehicle, driving or operating activity, physical control and automation status.
4. Leave endangerment and all surrogate cutoffs unresolved; preserve missing statutory definition references.
5. Preserve life, limb and property as protected interests without requiring contact, injury or damage.
6. Realize the person as a stationary pedestrian beside the alley, as a construction choice rather than a catalog classification.
7. Retain speed, time to conflict, surface gaps, stopping distance, pedestrian and vulnerable-road-user observations, obstruction geometry and any contact outcome.
8. Specify alley geometry, clearance, the person's stationary location and owned property's geometry relative to ego.

## Current result and exact next CPU actions

### 2026-11-11 saved-only finalizer checkpoint

`alley_finalizer.py` now consumes the retained `participant_footprints.jsonl`, `ego_motion.jsonl`, `trace.jsonl` and `video_frames.jsonl` through `alley_measurement.measure`, checks the exact six-case identity, writes separate pedestrian/property original-gap channels and provenance hashes, and calls the pinned `physical_result` for source-based physical status. An original body-center before/after check records pedestrian and property passage separately. It returns false physical/legal acceptance and makes no legal speed cutoff. A synthetic original-source test validates the worker Native result schema and checks positive passage, wrong identity and missing motion source. The local suite now passes 17 tests (`cpu-tests.log` SHA-256 `2a0064aafe7242478a2a959aa92caab0b982a45b6ca2bceff85a28a2fb496402`). Assignment-scoped `worker_check.py --complete` exits 0. This is a saved-processing component proof, not an exact `runtime.py process-saved` receipt: the source-backed alley polygon, Native runner, construction/manifest and saved execution remain to be built. Status stays partial.

### 2026-11-11 exact settings, Native capture and semantic stage checkpoint

`alley_case_setup.py` validates all six exact person/property 3/5/7 m/s engineering cases, 160 original frames at 20 Hz, a named hashed alley polygon source, source coordinates matching the selected polygon, and a five-metre usable alley width. `native_alley_cases.py` is CARLA-lazy: it selects a source-bounded connected route, places and retains distinct Native subject, stationary pedestrian and property actors, captures original footprint/motion/trace/frame-map sources plus the four named lossless cameras, confirms extraction only after a complete capture, restores world settings and seals the completed lifecycle. The copied `alley_camera.py` enforces four synchronized original source streams. No exact source polygon has yet been selected or claimed; the synthetic polygon in the unit test proves the guard and tests source tamper rejection, not alley existence on a target Native map.

`build_semantic_proposals.py` now authors the exact-law relevance, template, judgment observables, alley binding and six selected case proposals with source hashes. `validate_semantic_stages.py` runs the pinned canonical stage validators successfully. The judgment sweep is explicitly incomplete because exact source geometry and generated points are not constructed; it does not insert a legal cutoff or anticipated judgment. Current 19-test `cpu-tests.log` SHA-256 is `df573b1849a32ae1c006e0d560572debdb6836d7d56ec458e8a210b147ca068d`; semantic validator log SHA-256 is `711092f208ab72b853c04d9a242f2188aa7967b355c9b9a6c53a26be258d1b15`; semantic index SHA-256 is `af08bf80d2d3b30af16916db09a0453289579e4249ad811c1713c01778d1d307`. Scoped `worker_check.py --complete` passes. The exact next CPU step is to select or construct a verifiable alley polygon source and bind first `__person_3mps` config/construction to the new runner/finalizer, then run exact offline, compatibility positive/negative and saved processing. Expand the remaining five cases and three distinct fallbacks each, complete the qualitative sweep and delivery/comparison audits, and run scoped strict only after their proofs pass. Status remains partial; no physical/legal result is asserted.

### 2026-11-11 six-case exact diagnostic software proof

`build_first_probe.py` now materializes six exact inline constructions with the current CARLA-lazy runner, saved finalizer, four-camera capture, source modules and tests. All six pass pinned `runtime.py offline`. `build_first_compatibility.py` provides a compact source-shaped diagnostic fixture transferred from an earlier marked synthetic graph/video fixture and augments it with C10364 participant-footprint and motion rows. `expand_compatibility.py` binds all six case-specific measurement contracts. Every case passes pinned `runtime.py compatibility` with its positive and removed-original-motion negative path; all six receipts pass `package_compatibility.check_receipts`. Every case also passes pinned `runtime.py process-saved` on its current exact inline construction, with `originals_preserved=true`, `missing_evidence=false`, `physical_acceptance_claimed=false` and `legal_acceptance_claimed=false`. `check_six_diagnostics.py` verifies the current six construction hashes and offline/compatibility/saved receipts. This is a software proof on synthetic data; the reused graph/video fixture does not establish an actual C10364 alley or realized 3/5/7 m/s motion.

Current SHA-256: `cpu-tests.log` `a8461bab8c49badb08529d8a8f870b6628d20291b1a3b57b6407b1be65e48750` (19 tests); `semantic-stage-validation.log` `711092f208ab72b853c04d9a242f2188aa7967b355c9b9a6c53a26be258d1b15`; `six-diagnostic-proofs.log` `cf6262968178ab420a00d38b6f80949e645338214947b0e51602042ed7f912b1`; `construction-probe-manifest.json` `02a9b15cf7bf17f182b9166736a02a951273ab8adc9859fe30ec6102387e3148`; `probe-compatibility-manifest.json` `8bd0ae3b00a2d7e544ef0bbf583ecdce5e7246533f1ed328490409db155bdfc5`; compact diagnostic fixture `921f6f88ef8720c43397ca87acf075a4506f7921f62042ebc4ab2073dd51963b`; recipe `38c8c16d74397e05651118eef7c342fb34052df91c9e721b4e35091e4bd34c55`. Assignment-scoped `worker_check.py --complete` passes. Status remains partial; the next CPU work is three distinct risk-triggered fallbacks per case, a complete qualitative sweep, source-bound alley route/physical protocol and independent delivery/comparison audits, followed by the exact execution manifest and scoped strict gate. Do not run `build_first_compatibility.py` alone after this checkpoint: rebuild/expand all six entries and rerun exact proofs if fixture or construction sources change.

### 2026-11-11 six four-candidate exact diagnostic checkpoint

The primary Native runner now supports three bounded, distinct physical-risk fallback changes without altering the observation contract: westbound route when the eastbound sourced polygon route is disconnected, one-waypoint shorter controller lookahead when original motion drifts from the corridor, and a 2 m higher overview mount when original frames occlude the person or property. `build_alley_fallbacks.py` constructed all 18 inline alternatives. All six primaries and 18 fallbacks pass exact pinned `runtime.py offline` and positive/removed-original `runtime.py compatibility`; the pinned four-candidate validator and compatibility receipt checker pass every case. All six current primaries pass synthetic saved-only processing. `check_six_diagnostics.py` validates the exact current construction, compatibility and saved receipts. Physical causation and actual Native alley existence remain unverified; these are marked software diagnostics.

Current SHA-256 superseding the prior six-case hashes: `cpu-tests.log` `c66600082015037057155d70c0bfa85df1d24d104cd1b0cb65a270ee33c027df` (20 tests); `six-diagnostic-proofs.log` `db449ff5ab4f05a873394c7969304506789b9b9799b0ca0227aac1149e16f840`; `construction-probe-manifest.json` `10c0f740dbb94f609b5d7a4d02fbdefcf73697fbc47a167fedde7fa21bc68029`; `probe-compatibility-manifest.json` `807f0941ddb76a3f95163ae9e2c6d12e5b6a12e76656dfee7c1d04730cf3ff5e`; scoped complete gate `worker-check.log` `042998b01b6533c72a6cffdcfee0d7a8010973a06cf87259d4f5fd9907da5ebe`. Status remains partial. Next, construct the nonduplicate qualitative judgment sweep and exact generated cases/fallbacks, then bind source-backed physical, independent audit and execution handoff proofs.

Status is **partial**. The geometry, original-source measurement, and draft comparison audit described below exist; no executable case, fallback, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## 2026-11-11 CPU continuation

The pinned `.venv-cpu/bin/python runtime.py preflight` now passes with the installed
NumPy/FFmpeg/Lean toolchain. The previous dependency diagnosis is obsolete.

`case-plan.json` now plans six exact cases: `__person_3mps`, `__person_5mps`,
`__person_7mps`, `__property_3mps`, `__property_5mps`, and `__property_7mps`
(each prefixed by this assignment ID). Its three comparisons sweep measured speed
for each protected interest and compare which object is nearer at the 5 m/s
target. These speeds are engineering probes; no statutory numeric boundary or
expected endangerment verdict is asserted. The frozen evidence inventory has zero
recordings, so neither branch claims existing-evidence reuse. Life and limb share
the same stationary pedestrian exposure; owned property is measured separately.

`alley_geometry.py` constructs a route-relative stationary pedestrian and property
position and rejects placements outside the alley or overlapping the nominal
vehicle corridor. Its CPU tests exercise both travel directions and a rotated
route. `alley_source_capture.py` writes measured original-tick ground footprints
and ego motion readbacks for three distinct Native actors and rejects missing
frames or bad geometry. `alley_measurement.py` reads those retained sources with
trace and frame-map, joins Native identities and times, measures original-frame
speed and surface gaps, and rejects missing sources and participant changes. It
also computes a forward-projection time-to-station proxy and a braking-distance
proxy from the original instantaneous acceleration. The braking proxy is unknown
when deceleration is absent; neither proxy is a legal cutoff.
`alley_comparison_audit.py` checks three exact case identities, declared fixed
conditions, original-source hash fields, measured speed order and measured gaps;
it reports an incomplete comparison when speed order is not realized. It is not
yet wired to saved processing or validated against promoted source bytes. Twelve
tests pass:

`.venv-cpu/bin/python -m unittest discover -s work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/tests -v`

The log is `cpu-tests.log` (SHA256
`d2965c04265f747fd8edaf1a3a7bbed69c56930946ce64fc6112304cfc24652a`),
also recorded in `result.json`. The checkpoint
command `.venv-cpu/bin/python worker_check.py --assignment heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver --complete`
passes static checks in `worker-check.log`. This is **partial**: the case plan is
not yet an executable case package. Next, select and verify a real C10364 alley
route and participants in a CARLA-lazy runner, retain four named camera sources
and original footprint/motion sources, then finish the first `__person_3mps` case
through exact offline, positive/negative compatibility and saved processing before
expanding its comparisons and risk-triggered fallbacks. Bind the raw-source
proxies through the finalizer and implement all audits and semantic proposals.
Rerun this assignment's strict gate after all CPU proofs pass; keep
physical motion and visibility as later GPU checks.

The rerun of `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`
still fails with `Preparation acceptance failed: partial/missing packages remain`;
see `work/_shared/batch-strict-gate.log`. This package remains partial for the
CPU tasks above, as do other incomplete assignments. The failure is not a tool
or package dependency failure.

## 2026-11-11 sourced alley route and feedback checkpoint

`alley_route.py` now selects a connected, nonjunction Native map lane inside a supplied alley polygon, with both east and west approach support. It requires a named original polygon source, checks that the complete vehicle width plus an engineering edge margin fits inside the polygon and mapped lane, and rejects an out-of-polygon, wrong-way, narrow or branching route. The pure feedback controller uses measured position, heading and velocity to request steering, throttle and brake toward a case speed. The polygon and target speed remain authored construction inputs; a speed command and diagnostic polygon do not establish actual endangerment or legal status. No selected C10364 alley polygon has yet been sourced, and no Native run is claimed.

`tests/test_alley_route.py` exercises both approach directions, missing source, geometry rejection and feedback response. The full local suite passes 15 tests: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/tests -v`; `cpu-tests.log` SHA-256 `d4c9317e3d52b8426dd40d21cacbe6d18eb4c0caca831af375b171daa233ccb6`. The assignment-scoped static check exits 0; `worker-check.log` SHA-256 `042998b01b6533c72a6cffdcfee0d7a8010973a06cf87259d4f5fd9907da5ebe`. Status remains partial.

Next CPU work: bind an actual source-backed alley polygon and participant placements to the first `__person_3mps` config, author the CARLA-lazy runner with four source cameras and original footprint/motion capture, then finalize and run exact offline, positive/negative compatibility and saved processing. Preserve the six planned cases, measured fixed-condition comparisons and unresolved endangerment judgment. Continue fallback, semantic and independent audit work after the first case passes.

## 2026-11-11 nine-case finite alley judgment sweep checkpoint

The finite qualitative judgment sweep now adds three selected 5 m/s pedestrian placements to the six original person/property speed cases. `build_semantic_proposals.py` and `extend_sweep_plan.py` bind all nine canonical semantic cases and their comparison intent. The sweep axis is **authored lateral pedestrian offset** (1.5, 1.95, 2.4 m); the observable is **measured original-source minimum body gap**, never an assumed equality to that authored offset. The generated diagnostic fixtures preserve ego motion, property body, trace and frame sources and shift only the pedestrian body polygon by the exact requested offset delta. `audit_alley_sweep.py` independently checks each source hash and exact body geometry, recomputes gaps from the retained original footprint rows, checks monotonicity and rejects a tampered setpoint. The synthetic diagnostic gaps are 7.300053405761716, 7.30843940155716 and 7.3437589269113674 m respectively. They are not Native observations or legal thresholds.

`build_first_probe.py`, `build_first_compatibility.py`, `expand_compatibility.py`, `build_alley_fallbacks.py` and `build_sweep_fixtures.py` materialize nine exact primary inline constructions and three bounded fallback constructions for each. All 36 current constructions pass pinned `runtime.py offline` and positive/missing-original `runtime.py compatibility`; all nine primaries pass exact pinned `runtime.py process-saved` using marked synthetic fixtures, with original sources preserved and physical/legal acceptance false. `check_nine_diagnostics.py` validates current construction hashes, offline receipts, compatibility receipts and saved flags. `validate_semantic_stages.py` validates nine cases across six canonical stage outputs. The test suite passes 20 tests. The assignment-scoped `worker_check.py --complete` passes.

Current SHA-256: `cpu-tests.log` `df1d3fe514b3032f21e5618aa1fdac6c73a7232d261243b6d0c7afc027ec2f16`; `semantic-stage-validation.log` `431942346047db7b462a0829da797d8f884253a693e727f12b3fb5f99587727e`; `nine-diagnostic-proofs.log` `9ee8108518f7b7b052eae34175b9d6e4019a7d7c05c78f33ea2519a97ed47655`; `alley-sweep-audit.log` `53566eb5924169733bd3f56e7645bfc3163830d3a514b2d3d3071defdb89bf88`; `construction-probe-manifest.json` `ee0c7f92753306c90c23f777b8a94d3f42597750f6926df302b08d1b45a1ef0a`; `probe-compatibility-manifest.json` `03b2798eec8681d73562b363ebef4d4b04669631ad47f90bcad6d8686ab92a9b`; `worker-check.log` `042998b01b6533c72a6cffdcfee0d7a8010973a06cf87259d4f5fd9907da5ebe`.

Status remains **partial**. The selected polygon and graph/video are synthetic diagnostics. Remaining CPU work is to identify and bind a verified Native alley source/polygon, complete the source-bound physical protocol and exact execution manifest, and run independent delivery/comparison acceptance. Actual CARLA motion and visibility remain later GPU checks and are not the reason for partial status. No physical or legal acceptance is claimed.

## 2026-11-11 independent audit and physical protocol checkpoint

`delivery_audit.py` independently checks exact case identity, original source hashes against the saved analysis, frame/participant joins, all four full camera decodes, saved result binding and Native closure/passage prerequisites. `build_delivery_audit_proofs.py` ran its marked-fixture positive path for all nine cases and a negative path with a tampered original-source hash for each; no diagnostic result claims physical or legal acceptance. `source_comparison_audit.py` reads exact saved roots, verifies original source and alley polygon hashes, holds fixed setup conditions constant, and tests each declared difference for all four comparisons. The synthetic speed and protected-interest comparisons remain `comparison_complete=false` because their intended physical differences are not realized. The generated placement comparison records distinct measured gaps and is only a diagnostic software result. Four new tests cover fixed-condition, deliberate-difference and missing-source rejection; the suite passes 24 tests.

`physical_probe.py` uses all nine current exact configs to exercise original-body complete passage, incomplete passage, missing ego-motion rejection and premature-seal rejection followed by restored closure. These are synthetic original-shaped protocol tests and do not establish actual motion. `build_execution_manifest.py` binds the nine current primary/fallback constructions, saved commands, independent delivery audits, physical protocol proofs and four comparison commands. The first exact case passes `runtime.py offline` against `execution-manifest.json`. The other execution-manifest cases still need exact reproof under this manifest, and source-backed alley geometry remains unresolved; the current polygon is explicitly diagnostic. Status stays **partial**.

Current SHA-256: `cpu-tests.log` `ee517cfb4ba58fc93c42f0b83ecb9baaa2476997e07ec4ff18aacb65f6f5f82a` (24 tests); `delivery-audit-proofs.log` `b30c9b8cf043dafbc13eda58901ae6fa61b0d3ed1b92db98e61421400ec67721`; `delivery-audit-proofs.json` `7eec1bbac098abbecf0ed4816a5478c7a4919bed9da5cf1afa6095afa2caca98`; `comparison-proofs.log` `931a3f6dd619c38780da9b597c56f41cde242e9184b8ef77fb42e9be8da01243`; `comparison-proofs.json` `5dcb0b127b36d9a844700bcc8f8137cb5f235b3e7a8697a77fc76fb61b034ed5`; `physical-preparation-proofs.log` `9e257734d2ac0d608496b0ad038e1c97f282b21516fd3a9f4796bcbaf0b1c4be`; `physical-preparation-proofs.json` `75ffdcf12bb30b66d1f16769f9e01b05cd824042edee2ea2a2b80d99835bdbe6`; `execution-manifest.json` `df2b4c9b67c9a087d5d91d507f23b81448c4bc686da89e67faf91169d3b0ae60`; `execution-offline-first.log` `f023747153c4bb35cd593c251b8311d9b031d66ccad3b35df1309ce28ce04a67`. Assignment-scoped `worker_check.py --complete` passes. Exact next CPU action: reprove all nine execution-manifest primary/fallback candidates and saved paths, inspect a source-backed Native alley map/polygon source if available in supplied materials, then run the assignment-scoped strict gate. No CARLA has run.

## 2026-11-11 gate-shaped physical and final execution-manifest reproof

`physical_case_probe.py` now runs each selected exact case through separate marked synthetic complete-motion, incomplete-motion, missing-original and closure fixtures. `build_gate_physical_proofs.py` records per-case result/log SHA-256 and lifecycle ordering in the pinned `worker-physical-preparation-proof` shape. Its nine receipts pass the pinned `physical_preparation.validate` through `validate_execution.py`. The complete path has original-body passage and realized observables; the incomplete path is `not_met`; the missing-trace path is `unverified`; premature sealing is rejected before a restored seal. None is a CARLA observation.

The current `execution-manifest.json` is stable at SHA-256 `1889de32119da590ff045e387e50f54a60946d442e30dc81ff9ed47cd042cb20`. Against that exact manifest, `reprove_execution_manifest.py` passed pinned offline plus positive/missing-original compatibility for all nine primaries and 27 fallbacks; `execution-reproof.json` SHA-256 `9439864f03108da3047fd36035bb7bf77075fc366eb9c4c449949dd3eaf60ea4` binds that manifest hash and all 36 exact construction/receipt hashes. `reprove_execution_saved.py` cloned only marked synthetic original attempts, rebound their candidate-selection receipts to the current manifest, and passed pinned process-saved for all nine primaries; `execution-saved-proofs.json` SHA-256 `b60c8b47e19ac085aefc59f2a8b57c7ddf01a7761b40bf0448e6e5dc1ff81872` binds the same manifest hash. Original bytes are preserved, no missing evidence is reported in these diagnostics, and physical/legal acceptance remains false. `validate_execution.py` passes pinned exact execution, physical-preparation and delivery-acceptance binding checks for nine cases.

Current proof logs SHA-256: `physical-preparation-proofs.log` `bf307b498fe467a390a0de9c731558e1ca0a1c6601677e2217c44396711878ba`; `execution-reproof.log` `e90d12402c2a884c58977fbe6a76930c134fe57fc10fe72f7d10e3d3fc4e4cd3`; `execution-saved-proofs.log` `eb6f6915d2efd8fd72181b46fcb121c73080ceeb1fbef0b23ca530c5a4dad437`; `execution-validation.log` `19148b9df9d8c7f22fc66a748fd903b5b59aa3291ed02b9d25b29d3959022433`. The 24-test suite still passes. Assignment-scoped `worker_check.py --complete` passes. Scoped `--complete --require-delivery-ready` fails with `Preparation acceptance failed: partial/missing packages remain` (`worker-check-strict.log` SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`) because this assignment remains **partial**.

Read-only source inventory: `inputs/coverage/candidate-cells.json` names C10364 as a grounded `alley`/`travel` cell but has no coordinates or Native scene source. `rg --files inputs | rg -i 'map|xodr|polygon|world|geometry|alley'` found no supplied map/XODR/polygon. The exact source requirement is a named original Native map or scene record that establishes an alley polygon, connected lane and bounded vehicle/pedestrian/property positions; the current `diagnostic-alley-polygon.json` and media are marked synthetic and cannot fill it. Source-bound pixel/decode acceptance for an actual Native recording and canonical local execution are unproven. These are not claims that the code or law has passed physical review. Next CPU work is to strengthen the Native independent audit to bind a source-decode receipt and explicit participant visibility evidence, then bind a verified Native alley source if supplied. Keep status partial until the scoped strict gate passes without weakening source requirements.
