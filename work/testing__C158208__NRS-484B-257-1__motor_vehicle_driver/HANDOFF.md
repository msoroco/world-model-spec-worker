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

`case-plan.json` now names the two frozen nearest-view exact cases, the `yield_nearest_view` controlled comparison, the 45-second/20-Hz four-camera plan, the evidence gap and physical risks. This remains a partial plan; eight other frozen review-context topic descriptions are not asserted covered by these two diagnostic bundles.

`carla_scene_adapter.py` adds an executable CARLA-lazy scene implementation. It requires a reviewed `native_scene` with ego/through blueprint IDs and transforms, four camera extrinsics and FOVs, and a live yield-sign actor ID. It sets and reads back synchronous 20 Hz settings, spawns owned actors/sensors, reads original eight-corner body hulls and velocity, casts the original visibility ray, joins four same-tick camera frames and applies the observed-response controller. `native_attempt.py` now checks eight adjacent SHA-bound original survey files for production, compares loaded OpenDRIVE, and restores the world after ownership. Diagnostic tests use explicit synthetic provenance.

`camera_sources.py` now verifies that each archived lossless PNG reconstructs the original opaque BGRA bytes via the hash retained in the sealed original tick. `delivery_audit.py` independently reopens the sealed ticks, four camera archives, saved report, physical traversal and Native owner-release receipt; production mode requires the exact reviewed construction/site/map hashes and 900 original frames. Its result explicitly leaves physical acceptance false and legal status unresolved. The current 3-frame diagnostic audit positive and missing-media/stale-report/case/provenance negatives pass. Production composed-video decode and visual review still need implementation and evidence.

Both exact diagnostic constructions embed the adapter, saved finalizer and independent audit and pass pinned `runtime.py offline` with three embedded tests each. The synthetic physical-preparation receipts were rebuilt for the changed constructions and pass the pinned validator. The source-gated production runner branch is present in each bundle, but the frozen export supplies only accepted metadata and authored review settings, no genuine C158208 OpenDRIVE/sign/stop-line/crosswalk/sidewalk/through-highway/viewpoint source bytes or camera/trace bytes. No source review or physical claim was fabricated.

Proofs (all under this directory):

- `cpu-tests.log`: SHA-256 `8b4a90fbdf91544f2b639dad542bf3f58f2790b5459966a0d467488286ea2604`; exit 0.
- `cpu-draft-build.log`: SHA-256 `b7f015a78bc7d6331ee51a630df516b4ddd81de327de7b2c8fb0815f54cddbce`; exit 0.
- `cpu-nearest_view_response.log`: SHA-256 `0cfb6dbb85079ecc90dfd88fec42c5ac0c21ea28cb17db92a7993c907de8077d`; exit 0.
- `cpu-nearest_view_uninterrupted.log`: SHA-256 `4c5192377f3250352e0b75ac4c988467a39a646ef2922a2c4eb649b9f282793a`; exit 0.
- `cpu-physical-build.log`: SHA-256 `dfe68152fca895be0a9cd0f5deb11f4b34e71b6dc80e810710eadde826bf18db`; exit 0.
- `cpu-physical-validator.log`: SHA-256 `d2505ecb3764a7890feecc24917d30abcd6950542fa061affa7a7f8479085f16`; exit 0.
- `cpu-assignment-static.log`: SHA-256 `5d6a52e3ac3676f689ef42a0d023b341b13484b36161a633bb95587b2217a899`; exit 0.
- `cpu-assignment-strict.log`: SHA-256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`; exit 1 (truthful partial).

Exact scoped static command: `.venv-cpu/bin/python worker_check.py --assignment testing__C158208__NRS-484B-257-1__motor_vehicle_driver --complete` (exit 0). Exact scoped delivery-ready command with `--require-delivery-ready` exits 1 because the result is still partial.

Next CPU actions: obtain/review a genuine C158208 site packet and its eight original source bindings; construct and test the remaining compatible statutory branches and canonical semantic proposals; convert these diagnostic bundles into a selected `execution-manifest.json` with case-specific measurement contracts and source-hashed recipes; run pinned positive/missing-source compatibility and saved-only processing for each exact case; add composed-video decode and production delivery/comparison audit proofs; repeat the exact scoped strict gate. Physical CARLA motion, actual pixels and legal judgment remain later local review.
