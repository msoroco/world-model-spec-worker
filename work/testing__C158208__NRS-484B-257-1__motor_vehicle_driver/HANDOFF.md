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
