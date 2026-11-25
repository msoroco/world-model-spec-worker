# testing__C158208__NRS-484B-257-1__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.257(1) — Except when traffic is being controlled by a police officer or a traffic-control signal: When proper signs have been erected, the driver of a vehicle shall stop or yield at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, then at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After having stopped or, in the event of a yield sign, slowed or stopped, the driver shall yield the right-of-way to other vehicles which have entered the intersection from such through highway or which are approaching so closely on such through highway as to constitute an immediate hazard during the time such driver is moving across or within the intersection.
Assigned branch(es): Yield sign; neither stop line nor crosswalk; nearest-view location..
Cell: C158208 (one_way_to_two_way_intersection, travel, yield_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 11. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 4. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C158208__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Judgment probe planning: `judgment-probe-plan.json` records source-hashed below/inside/above targets for 4 exact law/actor ranges. These are unmeasured construction targets. 2 ranges have a domain endpoint that makes an outside probe impossible; review each endpoint_limit and preserve the explicit limitation.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-22 nearest-view saved-source construction checkpoint

`build_branch_plan.py` now binds all eight frozen comparison topics and eight unique reviewed case identities to source-hashed accepted metadata in `branch-plan.json`. Every physical-sufficiency decision remains unverified; the original video and trace bytes were not supplied in this export. The two nearest-view response alternatives are retained rather than adding a case ID.

`nearest_view_measurement.py` is an executable saved-source processor. It requires reviewed proper-sign, no-stop-line, no-crosswalk (including sidewalk-derived), through-highway, viewpoint and no-officer/no-signal context; strictly ordered original samples; first observed view before intersection entry; and through-vehicle occupancy during crossing. It preserves the approach minimum speed, through-vehicle center station at first view, and the full participant history without treating engineering values as legal cutoffs. Its CLI hashes the source packet. Seven positive/negative CPU tests pass in `cpu-tests.log` (SHA-256 c804002379ff3544107d28189a228146e00dd9017da15cee0a040b89db067c83). Static assignment check exits 0.

Next: bind the original Native map/sign/viewpoint and through-highway packet, implement the exact configuration-driven yield approach and source capture, then run pinned offline, compatibility, saved processing and independent delivery/comparison proofs. The current source inventory and synthetic measurement test do not establish legal, physical or pixel acceptance. Status remains partial. No Git command was run.

Final strict batch check exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c158208-current.log`). A non-Git scan checked 3,840 returned UTF-8 files under `work/`: largest 1,628,889 bytes, zero size, whitespace or conflict-marker issues. C158208 remains partial. No Git command was run.

## Paired response construction and latest gate

`yield_control.py` is a CARLA-lazy, configuration-driven nearest-view engineering controller. The response and uninterrupted diagnostic constructions share approach geometry, target speed, governing sign, source-verified viewpoint and traffic observation; only conflict response differs. It requires observed through-vehicle occupancy and rejects unsourced viewpoint input. Four control tests plus seven saved-source/branch-plan tests pass in `cpu-tests.log` (SHA-256 59da31a5c235428306260dedf0279e5017b3d0ad21f23ffa379e16dec7efb18b). The branch plan names `observed_conflict_response` as its comparison variable. This controller has not yet been embedded in pinned Native bundles or run in CARLA.

Current exact static check exits 0. Complete-batch strict check exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c158208-controller.log`). Keep status partial. Next worker-owned construction: source-bind actual Native sign/viewpoint/through-traffic geometry; embed the controller in exact bundles, run pinned offline and positive/negative compatibility, then prove original saved measurement, independent delivery and controlled comparison. No Git command was run.

## 2026-11-22 pinned exact diagnostic offline bundles

`build_offline_draft.py` now embeds `yield_control.py`, an exact selected config, frozen review-context bytes with SHA-256, a scene, and three embedded tests into each of the existing `nearest_view_response` and `nearest_view_uninterrupted` case identities. `execution-manifest.draft.json` binds both construction hashes. The entrypoint verifies exact case membership and context hash, exercises the controller, and refuses Native capture while only diagnostic review context is present. Both pinned `runtime.py offline` invocations exit 0; their logs are `cpu-nearest_view_response.log` and `cpu-nearest_view_uninterrupted.log`, and each materialized bundle ran three tests. Eleven assignment tests pass in `cpu-tests.log`. Five current proof entries and hashes are in `result.json`.

`runtime.py preflight` and the exact static assignment check pass. The strict batch gate exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c158208-offline-draft.log`). C158208 stays partial. Next worker-owned work: review and bind genuine Native sign, map, viewpoint, crosswalk and through-highway source packets; implement actual source capture and saved finalizer; run pinned positive/negative compatibility and saved processing, then independent physical, pixel, delivery and comparison audits. Current offline bundles are diagnostic construction proofs only. No Git command was run.

## 2026-11-22 original-tick acquisition adapter checkpoint

`source_tick_capture.py` now derives the nearest-view sample packet from supplied original body vertices, ego velocity, snapshot frame/time and a retained `native_raycast` visibility probe. It computes ego front station, through-vehicle center station and polygon occupancy against declared geometry; rejects degenerate bodies, invalid route axes, missing sign/probe, noncontiguous frames, non-20-Hz times, reused attempts and outputs under frozen `runtime/`. `TickCapture.close()` seals raw ticks and packet hashes; `verify_seal()` rederives all samples from raw ticks before analysis. The probe and scene geometry remain diagnostic in the current bundles and cannot establish actual visibility or statutory applicability.

The adapter is embedded in both exact nearest-view diagnostic constructions. Eighteen assignment CPU tests pass (`cpu-tests.log`, SHA-256 447bdf5ab3949e4a3fcdbbe5c02c6b83311608afb41c4da56528d687b6a87eb2). Fresh pinned `runtime.py offline` v4 checks pass for response and uninterrupted bundles with three embedded tests each; `result.json` binds five current proof logs. `runtime.py preflight` and exact static `worker_check.py --assignment ... --complete` pass; update version remains 0 with no pauses.

The strict batch gate still exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c158208-tick-capture.log`). Status stays partial. Next: bind genuine reviewed site packet and Native map/sign/viewpoint to acquisition, implement an actual CARLA-lazy runner that records original ticks and four cameras, then run pinned positive/negative compatibility, saved processing, physical completion and independent delivery/comparison audits. No Git command was run.

## 2026-11-22 sealed physical outcome CPU checkpoint

`physical_completion.py` now rechecks the sealed original 20 Hz tick source and measures full ego body traversal from before the reviewed intersection to a clear far edge. It returns `met`, `not_met`, or `unverified` from source evidence; missing or tampered original ticks cannot become completed motion. The assessor is embedded in both exact diagnostic constructions. `prove_physical_preparation.py` created three explicitly synthetic fixtures per exact case, with six hashed result/log pairs, and a lifecycle ordering test that rejects saved processing without owner release. Both receipts pass the pinned `physical_preparation.validate` gate; they do not claim an actual CARLA run or actual Native ownership closure.

Twenty-two assignment tests pass in `cpu-tests.log`. Both pinned `runtime.py offline` v5 exact-case checks pass with three embedded tests each. `.venv-cpu/bin/python runtime.py preflight` and the exact static assignment check pass. Seven current CPU proof log entries and hashes are in `result.json`. Status remains partial. Next worker-owned construction: bind a genuine reviewed site packet, implement Native scene/camera acquisition and source tick capture in the actual runner, then run positive/negative compatibility, saved processing, independent delivery, and paired comparison proofs. No Git command was run.

The full strict batch gate exits 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/full-strict-c158208-physical.log`), after the exact assignment gate passed. A non-Git hygiene scan checked 3,873 files under `work/`: largest 1,628,889 bytes; no UTF-8, size, trailing-whitespace, conflict-marker or C158208 proof-hash errors. C158208 remains partial.

## 2026-11-23 original visibility ray/body binding continuation

`source_tick_capture.derive` now rejects an asserted Native visibility ray unless its origin lies within the observed ego body and its target lies within the observed through-vehicle body. It also rejects a claimed through-vehicle center outside that body. Three new negative tests prevent a probe on another object from determining the nearest-view branch. The original probe still needs an actual Native raycast and a reviewed site packet; this CPU invariant does not establish visibility or right of way.

Both exact diagnostic constructions were rebuilt with the updated source adapter and passed pinned `runtime.py offline` (`cpu-nearest_view_response.log`, `cpu-nearest_view_uninterrupted.log`). `prove_physical_preparation.py` now uses a fresh `.runtime-work` fixture directory on each run; its six synthetic motion outcomes and two lifecycle receipts were rebuilt against the new construction hashes, and pinned physical-preparation validation passes (`cpu-physical-validator.log`). The 25-test assignment suite passes (`cpu-tests.log`), CPU preflight passes (`.runtime-work/c158208-raybind-preflight.log`), and exact static check passes (`.runtime-work/c158208-raybind-static.log`). `result.json` binds current log hashes and stays partial.

Next worker-owned CPU work is a genuinely source-bound site packet, CARLA-lazy original scene/camera runner and positive/negative compatibility, saved processing, delivery and controlled comparison proofs. Original physical motion, pixels and legal applicability remain unverified. No Git command was run.

Both exact and full strict delivery-ready gates exit 1 at `Preparation acceptance failed: partial/missing packages remain` (`.runtime-work/c158208-raybind-strict.log`, `.runtime-work/full-strict-c158208-raybind.log`). Non-Git scan of 10,374 returned UTF-8 files found zero size, trailing-whitespace, conflict-marker or C158208 proof-hash issues; largest file is 1,846,854 bytes.

## 2026-11-23 paired original-source comparison audit

Added `pair_comparison.py` for the exact `nearest_view_response` and `nearest_view_uninterrupted` cases. Each attempt must carry a case-bound capture identity tied to its sealed original ticks, construction hash, reviewed site packet hash, map OpenDRIVE hash and provenance kind. The audit rederives samples from original ticks, checks full-body intersection traversal and saved nearest-view measurements, then enforces fixed site/map/geometry/context, through-vehicle history and view/entry timing while requiring a realized lower approach speed for the response. It reports motion-only provenance; video and legal status remain unresolved. Diagnostic fixtures require an explicit flag and cannot pass the default 900-frame original-capture branch.

Thirty focused tests pass in `cpu-tests.log`; positive/negative pair tests cover provenance, case swap, seal tamper, site hash, geometry, context, through history and speed separation. Exact static check passes in `cpu-assignment-static.log`. Exact strict readiness check exits 1 in `cpu-assignment-strict.log` because this remains partial. Next CPU work: implement source-bound Native scene/camera acquisition and actual capture identity, review a genuine site packet, then positive/negative compatibility, saved processing and delivery audits. No physical or legal acceptance is claimed.

The paired audit now requires exact independently reviewed construction/site/OpenDRIVE expected hashes and 900 original frames in default mode; a diagnostic flag is needed for the five-frame test fixtures. An additional negative test checks reviewed-hash and full-capture rejection. Thirty-one focused tests pass.

## 2026-11-23 capture identity construction and regenerated proofs

`source_tick_capture.write_capture_identity` now writes a single-use exact-case identity from verified sealed ticks, a construction file, a reviewed site packet and loaded OpenDRIVE bytes. It rejects an unreviewed or wrong-map packet and requires 900 original frames outside explicit diagnostic mode. Two focused positive/negative tests bring the suite to 33. The reviewed site packet is not present yet; the current tests use clearly synthetic local packets and do not claim source review.

Regenerated both `construction-*.json` diagnostic bundles to embed the current source adapter, reran both pinned `runtime.py offline` checks, rebuilt six synthetic physical outcome fixtures and lifecycle proofs, then passed pinned `physical_preparation.validate` for both cases. Proof logs and hashes are current in `result.json`. Next CPU actions remain real site-source review, CARLA-lazy scene/camera acquisition and exact compatibility/process-saved/delivery audits.

## 2026-11-23 source-bound four-camera saved audit continuation

`camera_sources.py` now records the four exact camera names (`overview`, `approach`, `reference_corner`, `driver_reference`) from PNG bytes supplied by Native sensors. It requires a sealed original tick packet and exact-case capture identity, checks each camera's frame and time against the 20 Hz original world tick, and retains per-image SHA-256 hashes in separate original PNG archives. Actual-mode dimensions are 1920x1080 for overview and 1280x720 for each detail view; actual mode requires 900 ticks and original-capture provenance. The writer refuses reused media paths.

`audit_camera_sources` independently reopens every archive, checks source hashes, exact member ordering and frame/time joins, verifies every per-image hash, and fully decodes every PNG. The default original pair audit now requires this saved-media audit for both cases and reports decoded-image counts while keeping visual and legal acceptance unresolved. Synthetic diagnostic mode remains explicitly separate. The 900-frame synthetic fixture decoded all 3,600 camera images; a three-frame fixture covers missing camera, changed frame time, archive tamper, capture identity and provenance rejection. These are CPU source-integrity proofs, not evidence that the real yield sign, road users or approach are visible.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C158208__NRS-484B-257-1__motor_vehicle_driver/tests -v` passes 38 tests (`cpu-tests.log`). Exact static assignment check passes (`cpu-assignment-static.log`). Exact strict check exits 1 (`cpu-assignment-strict.log`) because this assignment remains partial. `result.json` records all proof-log SHA-256 values. No Git command was run.

Next worker-owned CPU actions: source-review a genuine Native site/map/sign/viewpoint packet, write the CARLA-lazy scene and sensor runner that feeds original ticks and camera bytes to these recorders, then author source-bound positive/negative compatibility, process-saved and delivery acceptance proofs. Actual motion, pixel quality and statutory conclusions remain for later local review.

## 2026-11-23 sealed saved finalizer checkpoint

`saved_finalizer.py` (SHA-256 `2e260a96af77eb6e1af5b3e65a77f8c75c665a524e2eb85ac347087c539cf210`) now joins the independently verified original tick seal, exact capture identity, fully decoded four-camera source archive and the selected nearest-view measurement in one saved-only report. It records hashes for the identity, tick seal, source packet and camera manifest, the measured first view and intersection entry, and the decoded-image count. It refuses an existing output, missing media, altered sealed context and synthetic provenance in original mode. The output explicitly leaves physical acceptance false and legal status unresolved.

The full focused CPU suite passes 40 tests (`cpu-saved-finalizer-tests.log`, SHA-256 `deed176962d1cb1a4c11165c89fca5e9dfc01e2dff265e7eda9a385abae82902`), including positive source joins and missing/stale-source negatives. Pinned preflight exited 0 (`preflight-saved-finalizer.log`, SHA-256 `79f2e0f8623e78e39573f8ae43905f6babe1b4b8c2811b19161b91ea5df770be`). Exact scoped static exited 0 (`static-saved-finalizer.log`, SHA-256 `5d6a52e3ac3676f689ef42a0d023b341b13484b36161a633bb95587b2217a899`), while exact scoped strict exited 1 on truthful partial status (`strict-saved-finalizer.log`, SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). The finalizer is not yet embedded in a canonical compatibility/process-saved bundle. Next CPU work is the CARLA-lazy runner, source-bound compatibility and process-saved proof, and delivery acceptance. No Git command was run.

## 2026-11-23 Native owner and source-bound response checkpoint

`native_attempt.py` joins the reviewed C158208 site and loaded OpenDRIVE map to original world ticks, observed ego/through body geometry, a retained raycast probe, four synchronized camera PNG streams and the exact capture identity. The response controller now receives speed, conflict occupancy and distance to the reviewed viewpoint from the same derived observations that are sealed in the tick packet. The owner destroys actors in reverse order and requires pinned world restoration readback before writing `native-owner-release.json`; source failure or restore failure leaves no release receipt. The adapter still needs an actual CARLA implementation and genuine reviewed site packet. Diagnostic tests use explicit synthetic provenance.

Four new lifecycle tests bring the focused suite to 44 passing tests. Both exact diagnostic bundles were regenerated, pinned offline checks passed, and both physical-preparation receipts were rebuilt and validated against current construction hashes. Preflight and scoped static pass. The exact scoped strict gate exits 1 on truthful partial status. Positive/negative compatibility, canonical manifest, process-saved and delivery acceptance remain CPU work; no actual motion, camera quality or statutory conclusion is claimed.

Current SHA-256 bound logs:

- `cpu-tests.log`: `737a0de94d67e19f78abba2681501c4502abac127b3a7e0b1ab0f9dfa2e9e5ba` (exit 0)
- `branch-plan-build.log`: `4ca92634e917e84ff4821365be8d42fedacd94b6c1573681bf99fd373a9bd536` (exit 0)
- `cpu-draft-build.log`: `b7f015a78bc7d6331ee51a630df516b4ddd81de327de7b2c8fb0815f54cddbce` (exit 0)
- `cpu-nearest_view_response.log`: `2eed7e1a3cb64e9f0d346c25b2493c99695c621578e33f98fd07fdfafb941534` (exit 0)
- `cpu-nearest_view_uninterrupted.log`: `47529c01d229fb870a16cf93dc3c282f10b6ee7b7e5a9e8acb528c67a8c22880` (exit 0)
- `cpu-physical-build.log`: `dfe68152fca895be0a9cd0f5deb11f4b34e71b6dc80e810710eadde826bf18db` (exit 0)
- `cpu-physical-validator.log`: `891b8642e52dd9d0d7e483418afb617088ac1cef4561f79c087d91e13adc39be` (exit 0)
- `cpu-assignment-static.log`: `5d6a52e3ac3676f689ef42a0d023b341b13484b36161a633bb95587b2217a899` (exit 0)
- `cpu-assignment-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-saved-finalizer-tests.log`: `deed176962d1cb1a4c11165c89fca5e9dfc01e2dff265e7eda9a385abae82902` (exit 0)
- `cpu-preflight-native.log`: `b61ed2ce22cdfe7c7c30eb02b30d3ea499834ea5979b77d576353607d5cec7e6` (exit 0)

## 2026-11-24 source-gated Native adapter and independent audit checkpoint

`case-plan.json` now names the two frozen nearest-view exact cases, the `yield_nearest_view` controlled comparison, the 45-second/20-Hz four-camera plan, the evidence gap and physical risks. This remains a partial plan; other frozen review-context topic descriptions are not asserted covered by these two diagnostic bundles.

`carla_scene_adapter.py` implements a CARLA-lazy scene. It requires reviewed actor/camera extrinsics and a live yield-sign actor or a source-identified static map landmark, sets and reads back synchronous 20 Hz settings, spawns owned actors and sensors, projects original eight-corner body hulls, retains Native raycast results, joins four same-tick camera frames, and applies the observed-response controller. `native_attempt.py` requires eight adjacent SHA-bound original survey files for production and verifies the loaded OpenDRIVE map before ownership. World restoration is checked before release.

`camera_sources.py` verifies that each archived lossless PNG reconstructs the original opaque BGRA bytes via the SHA-256 retained in the sealed original tick. `delivery_audit.py` independently reopens sealed ticks, camera archives, saved measurement, physical traversal and Native owner release. Production requires 900 original frames and exact reviewed construction/site/map hashes. Diagnostic positive and missing-media/stale-report/case/provenance negatives pass. The audit leaves physical acceptance false and legal status unresolved.

Both exact diagnostic constructions embed the adapter, finalizer and audit, and pass pinned offline checks with embedded tests. Synthetic physical-preparation receipts were rebuilt and pass the pinned validator. A source-gated production runner branch is in the bundles, but the export supplies accepted metadata and authored review settings without genuine C158208 OpenDRIVE/sign/stop-line/crosswalk/sidewalk/through-highway/viewpoint or original camera/trace bytes. No site review or physical claim was fabricated.

Proofs (all under this directory):

- `cpu-tests.log`: SHA-256 `06d7d0bac71e2c495f23a556cfe2364ff02fc8473757b0f5835ba1b585a17c1b`; exit 0.
- `cpu-draft-build.log`: SHA-256 `b7f015a78bc7d6331ee51a630df516b4ddd81de327de7b2c8fb0815f54cddbce`; exit 0.
- `cpu-nearest_view_response.log`: SHA-256 `1387465eae4dff80392778deb6369da4807c4787d6198f892ab8371013fdb16a`; exit 0.
- `cpu-nearest_view_uninterrupted.log`: SHA-256 `153dfb00b8a92b98a753bf22690ab3defae5443fa1b5bfc2c6451dcb12f1c014`; exit 0.
- `cpu-physical-build.log`: SHA-256 `dfe68152fca895be0a9cd0f5deb11f4b34e71b6dc80e810710eadde826bf18db`; exit 0.
- `cpu-physical-validator.log`: SHA-256 `d2505ecb3764a7890feecc24917d30abcd6950542fa061affa7a7f8479085f16`; exit 0.
- `cpu-assignment-static.log`: SHA-256 `5d6a52e3ac3676f689ef42a0d023b341b13484b36161a633bb95587b2217a899`; exit 0.
- `cpu-assignment-strict.log`: SHA-256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`; exit 1 (truthful partial).

Focused suite: 55 tests passed. Scoped static assignment gate passes; exact scoped `--complete --require-delivery-ready` remains partial.

Next CPU work: review a genuine C158208 site packet and its eight original source bindings; complete compatible statutory branches and canonical semantic proposals; select an `execution-manifest.json` with measurement contracts and source-hashed recipes; run pinned positive/missing-source compatibility and saved-only processing for each exact case; produce composed-video decode and production delivery/comparison audit proofs; repeat the exact scoped strict gate. Actual CARLA motion, camera content and legal judgment remain later local review.

## 2026-11-24 exact construction identity seal

`source_tick_capture.write_capture_identity` now parses the selected construction before sealing a Native attempt. It rejects a different exact case, law, cell or actor, and original-capture mode rejects `diagnostic_only` constructions. This closes a case-swap path where a valid SHA-256 of the wrong construction could previously be recorded as an exact-case identity. `tests/test_source_tick_capture.py` exercises both refusals; diagnostic fixtures in the other source/camera/owner tests now name their actual case.

The focused suite passed 56 tests (`cpu-tests.log`). Both diagnostic bundles were regenerated from the changed source adapter (`cpu-draft-build.log`); exact pinned offline checks passed for `nearest_view_response` and `nearest_view_uninterrupted` (`cpu-nearest_view_response.log`, `cpu-nearest_view_uninterrupted.log`). Physical-preparation receipts were rebuilt against the new construction hashes and the pinned physical validator passed both (`cpu-physical-build.log`, `cpu-physical-validator.log`). CPU preflight passed (`cpu-preflight-native.log`). The exact assignment static check passed (`cpu-assignment-static.log`); the exact strict check exited 1 on the truthful partial result (`cpu-assignment-strict.log`). `result.json` binds current hashes for these logs. Temporary files used `.runtime-work/c158208-owner-nov24b/`; no Git command was run.

The production construction remains unselected because this export does not contain a genuinely reviewed C158208 site packet and its eight original survey files. The next CPU work is to author canonical semantic proposals and a source-gated production bundle builder, then supply case-specific positive/missing-source compatibility, saved-only processing and independent delivery/comparison receipts. Original CARLA motion, visual quality and legal applicability remain unverified.

## 2026-11-24 source-gated production builder and semantic draft

`build_production_construction.py` now accepts an original reviewed C158208 site packet and eight adjacent SHA-bound survey sources, verifies the loaded-map source hash, nearest-view context, finite station and scene presence, then embeds those sources and the matching geometry in a production construction for either exact case. It refuses overwrite, changed survey bytes, duplicate source names and an output above 2 MiB. The construction remains unselected until actual reviewed inputs are provided and pinned delivery proofs pass. The synthetic builder test runs the materialized bundled runner's `--check` positive path and changes the sign source to confirm a nonzero missing-source result; its packet is explicitly test data, not a site review. The bundled runner now reopens all eight source files at offline check and compares its geometry to the reviewed packet.

`build_semantic_proposals.py` authored nine canonical draft stage outputs in `proposals/` for the exact nearest-view pair: batch/cell relevance, statute template, four unresolved judgment observation contracts, binding and cases. The template quotes NRS 484B.257(1), keeps officer/signal control as a separate exception, and treats proper sign, nearest view, immediate hazard and right of way as judgments requiring original sources. Sweep plans remain explicitly incomplete because no original site or feasible physical range was supplied. The pinned `semantic_delivery.validate` passed these proposals against temporary constructions with the same recording description under `.runtime-work/c158208-owner-nov24b/` (`cpu-semantic-validate.log`); this is stage-schema evidence, not selected delivery readiness.

The focused suite passed 58 tests (`cpu-tests.log`). Both diagnostic bundles were rebuilt (`cpu-draft-build.log`), both exact pinned offline checks passed, both physical-preparation receipts were rebuilt and pinned validator passed. The scoped static assignment check passed; the scoped strict gate still exited 1 on truthful partial status. All current logs are SHA-bound in `result.json`. Next CPU work is a selected production manifest, exact positive/missing-source compatibility, saved-only processing and independent video/delivery/comparison receipts for every expanded statutory branch. The genuine site packet and source files are still absent from this export; no original CARLA motion or legal conclusion has been claimed.

## 2026-11-24 selected source-shaped CPU analysis

Added `analysis.py` to the source-gated production construction. It reopens the sealed original tick packet, hashes the required source set, independently decodes all four archived PNG streams, measures nearest-view history and governing-control observations, and refuses a missing selected source or altered archive. `prepare_derived_media.py` converts verified archived PNG bytes to four FFV1 MKV camera streams in a fresh saved stage without changing the originals. The selected analysis emits four timestamped channel streams, two context channels, trace, frame map, exact camera videos, a Native result and a source-hashed analysis report. No legal verdict or physical completion is inferred.

The pinned `native_output.validate_result` and `batch_pipeline.carla.validate_attempt` both passed on an explicitly synthetic three-frame sealed fixture. The fixture test is software compatibility evidence only; it does not stand in for an original C158208 source, full 900-frame Native capture, or package-level compatibility and saved-processing receipts. The focused suite now passes 63 tests. Canonical semantic proposal sweeps are explicitly marked unexpanded until genuine source-grounded ranges can be set; the pinned semantic stage validator still passes this truthful draft. `result.json` remains partial.

The next source-bound construction work is to supply an original reviewed C158208 Native site packet with eight adjacent SHA-bound sources, expand the full statutory branch cases and sweeps from that source, then build an exact selected manifest with measurement contract, case fixture recipe, alternate candidate, positive/negative package compatibility and saved-processing proofs. Keep temporary fixtures under `.runtime-work/` and do not select the diagnostic draft.

## 2026-11-24 exact diagnostic compatibility and saved processing

`build_diagnostic_manifest.py` binds current selected `analysis.py` and `prepare_derived_media.py` into two exact-case diagnostic constructions, their source-shaped recipes and measurement contracts. `execution-manifest.diagnostic.json` declares capability research and diagnostic-only status; it is not a selected production manifest. The genuine reviewed C158208 site packet, its eight SHA-bound survey sources, source-grounded sweep ranges and full statutory branch expansion are still required for production selection.

For both `nearest_view_response` and `nearest_view_uninterrupted`, the pinned `runtime.py compatibility` command passed selected measurements, missing-source negative, unchanged acquisition, Native attempt validation, Core and isolated Lean decoder, and final video decode. The pinned `runtime.py process-saved` command also passed both exact diagnostic attempts; it reports unchanged original sources, no missing evidence and a decoded three-frame final video. `diagnostic-compatibility-index.json` binds the two receipts and logs by SHA-256. These three-frame generated sources establish only the software path; they are not original site or 900-frame CARLA evidence.

The 64-test focused suite and `prove_selected_analysis.py` both pass. `worker_check.py --assignment testing__C158208__NRS-484B-257-1__motor_vehicle_driver --complete` passes; the same command with `--require-delivery-ready` exits 1 only because this result remains partial. `result.json` binds current test/compatibility/saved-processing receipts. Temporary attempts, video, decoder and fixtures are under `.runtime-work/c158208-owner-nov24b/`. No original CARLA motion, physical completion or legal judgment is claimed.

## 2026-11-24 statutory expansion and production selection gate

`build_statutory_matrix.py` reopens the frozen full law and candidate-cell catalog, then writes `statutory-matrix.draft.json`. Seven controlled branches cover all 11 case IDs in the accepted demo-test snapshot: nearest-view hierarchy, stop-line and two crosswalk forms, yield slowing or stopping, occupied or approaching through traffic, and across-or-within time history. Three additional control-cell candidates remain separate and unselected: police officer C158170, traffic light C158196, and stop sign C158190. The builder checks their shared layout, maneuver and actor compatibility. Metadata acceptance is not treated as original physical proof.

`build_source_gated_manifest.py` refuses production selection unless the case plan and canonical proposals include every matrix case, source-grounded sweeps are expanded, each case has a genuinely reviewed C158208 site and eight matching original survey bytes, the construction embeds those originals, and offline/physical/compatibility receipts are SHA-bound. It leaves `execution-manifest.json` absent on incomplete input. The focused suite now passes 66 tests, including matrix coverage and negative selection. The exact selected production path remains pending those worker-owned sources and proofs; the diagnostic manifest does not substitute for it.

## 2026-11-24 independent selected delivery audit

`selected_delivery_audit.py` independently reopens the selected saved analysis report, sealed ticks, Native result, exact trace/frame joins, all reported source hashes and all four 20 Hz camera videos. For original capture it also requires 900 frames and full original PNG archive audit. `prove_selected_analysis.py` now runs this audit on both exact generated fixtures and changes a report source digest to confirm rejection. The two positive saved-stage receipts are SHA-bound in `diagnostic-compatibility-index.json`. The existing `delivery_audit.py`, `pair_comparison.py` and `camera_sources.py` already provide source-bound original camera, physical traversal, owner restoration and controlled nearest-view pair checks; those original paths still require genuine reviewed C158208 site and Native acquisition.

Independent law check: the matrix also lists original observations required for sign erection, the stopping-reference hierarchy, actual officer/signal control, through-highway status, occupied/approaching history, ego across-or-within timing, and unresolved immediate-hazard/right-of-way judgments. A missing or invalid sign has no compatible selected case or reviewed source in this assignment and remains an explicit source/binding gap. No numeric engineering threshold has been promoted to a legal definition.

## 2026-11-25 production scene preflight

`build_production_construction.py` now invokes the same Native scene specification validator used by `CarlaSceneAdapter.configure` before writing a nondiagnostic bundle. The validator requires finite actor and camera poses, four named camera extrinsics with physical field of view, and exactly one yield-sign actor or map-landmark source. The builder embeds the current adapter bytes. A source-shaped fixture proves successful bundle checks and rejects missing pose, invalid camera field of view, missing sign source, and a changed original survey. This closes a CPU construction gap where an empty scene could previously be emitted and fail only during Native setup. The fixture remains synthetic and does not establish a real governing sign or physical camera coverage.

The focused suite passes 67 tests (`cpu-nov25-production-scene-tests.log`); exact scoped static exits 0 and exact scoped strict still exits 1 on truthful partial/missing-package acceptance. No selected production manifest has been created. Next CPU actions require a genuinely reviewed C158208 site with original map and eight adjacent SHA-bound survey sources, source-grounded full branch plan/sweeps, then nondiagnostic per-case construction, offline/compatibility/saved/delivery/comparison proofs and semantic/manifest selection. The frozen export supplies only metadata summaries, not those original site bytes or reviewed findings.
