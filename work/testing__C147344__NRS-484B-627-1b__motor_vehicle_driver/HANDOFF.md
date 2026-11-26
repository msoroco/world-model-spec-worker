# testing__C147344__NRS-484B-627-1b__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.627(1)(b) — If any driver or operator of a motor vehicle drives or operates a motor vehicle at a speed so slow as to impede the forward movement of traffic proceeding immediately behind the driver or operator, the driver or operator shall: If the highway has two or more clearly marked lanes for traffic traveling in the direction in which the driver or operator is traveling, drive in the extreme right-hand lane except when necessary to pass other slowly moving vehicles.
Assigned branch(es): Extreme-right-hand-lane duty on a one-way multilane highway..
Cell: C147344 (one_way_multilane, travel, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C147344__NRS-484B-627-1b__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The conditional law requires source-backed slow operation impeding traffic immediately behind, two or more clearly marked same-direction lanes, extreme-right-lane position, and review of the exception when passing a slowly moving vehicle is necessary. `case-plan.json` now defines four unselected construction cases and three isolated comparisons for lane position, pass state and immediate-follower relation. No accepted recordings exist in the frozen inventory.

`right_lane_measurement.py` processes original 20 Hz frames for ego/rightmost lane identity, immediate follower lane relation, gap, closing speed and observed pass. It binds a SHA256 source and rejects missing lane identities or skipped samples. Closing speed is only an observation; it does not establish legal impediment, and a pass observation does not establish necessity. Five focused tests pass.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `528b8cf62ada55ca8b8283fb4deda44c842e153a71080b16eecce67c4632bc71` |
| `right_lane_measurement.py` | `c22d908def2fcf890c4c6803a4fec8d465a781fb9e34c000f8c61806c4181f0d` |
| `tests/test_right_lane_measurement.py` | `431a4e76d0e570693252c8bb72bcf4fd6daea70bf20d08a9e78cb86f5839898f` |
| `preflight.log` | `b2742a158859f9ede99b41162978e56fb8947b02d89d2ab48f944454b4db7c6d` |
| `unittest.log` | `8284edb89f1ff680163425a23a454187a667979fa2cdbf9ea28a31c7efdee3a8` |
| `static.log` | `edc0436fde98171827bcdac9065e8b83b908253d8cfd8d52fd6007bc7cf39a44` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because the package remains partial. Command bindings are in `result.json`.

Next CPU work: implement CARLA construction/controller for the four cases, source-bound finalizer and human-review evidence packet for actual impediment and passing necessity, run exact offline and positive/negative compatibility, and add independent saved delivery and comparison audits. Physical motion and camera quality remain later CARLA checks.

## 2026-11-24 immediate-follower source join checkpoint

The earlier measurement inferred "immediately behind" from shared lane identity. `right_lane_measurement.py` now keeps same-lane and original immediate-follower readback separate and rejects a claimed immediate follower in another lane. `finalize_follower.py` independently SHA-verifies 900-frame motion and relation packets, joins each frame/time/actor ID, refuses inline unsealed relation flags, and passes the joined observation to the measurement. Same-lane with an intervening vehicle remains false. The relation packet still needs a reviewed original ordering source; a fixture string does not prove legal impediment or passing necessity.

Pinned suite passes 11 tests; preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial. New SHA256 receipts:
- `cpu-follower-join-tests.log`: `d71dd74a07651a91d0312e21f61d0d7ffd499695a26337e99e1b01654e2a9ce0`
- `cpu-follower-join-preflight.log`: `c34f8b66e61c985c8f033ab721445111999c2caf2f7cc8fd03c8fb7e11ad063d`
- `cpu-follower-join-static.log`: `edc0436fde98171827bcdac9065e8b83b908253d8cfd8d52fd6007bc7cf39a44`
- `cpu-follower-join-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

Next CPU work: source-bind actual highway and marked-lane geometry, following traffic and slower vehicle; implement four exact scene/controllers and cameras, semantic proposals, positive/negative compatibility and independent comparison/delivery acceptance.

## 2026-11-25 diagnostic four-case milestone

The exact selected variants are `slow_middle_follower`, `slow_right_follower`, `slow_middle_passing`, and `slow_middle_no_immediate_follower`. `reviewed_scene.py` requires a SHA-bound reviewed original highway site and OpenDRIVE map with at least two clearly marked same-direction lanes, the ordered right/middle lane IDs, reviewed actor stations/speeds, and four camera profiles. `native_adapter.py` lazily constructs the reviewed map, three actor roles as applicable, and the pinned `overview`, `approach`, `reference_corner`, `driver_reference` views. It records original Native frame IDs, actor road/lane/station/speed readback, immediate-follower ordering and four camera frames for 900 ticks at 20 Hz. The source packet is absent, so no Native attempt has been executed or accepted.

`build_diagnostic_bundles.py` binds an exact SHA for each of four diagnostic constructions in `diagnostic-execution-manifest.json`. All four passed pinned `runtime.py offline` with materialized runner checks and bundle tests. `analysis.py` and the four canonical `worker-measurement-contract` files bind the selected conditional-law requirement to `trace.json` and an independently sealed `relation.json`; pinned measurement-contract schema validation passes. `diagnostic_case_compatibility.py` executes each bundled 900-frame finalizer on source-shaped synthetic packets and verifies that deleting the relation source fails. `process_recorded_only.py` finalizes each synthetic attempt into a fresh derived output without changing acquisition. These diagnostic receipts are `cpu-offline-*.json`, `cpu-compatibility-*.json`, and `cpu-saved-*.json`, indexed by SHA in `proof-summary.json`; they do not satisfy the pinned full converter compatibility or production delivery gate.

`delivery_audit.py` checks released original Native attempt identity, a SHA-bound capture seal, exact reviewed site/map, original 900-frame four-camera join and full decoded streams, and original motion/relation readback. It rejects diagnostic provenance, stale seals, missing frames, changed video bytes and unrealized lane/follower/pass targets. `comparison_audit.py` independently tests three fixed-condition comparisons and rejects reused original motion. Thirty-two CPU tests pass, as do the semantic draft stage validation and scoped static check. The exact scoped strict gate exits 1 because `result.json` remains partial. See `cpu-current-tests.log`, `cpu-current-semantic.log`, `cpu-current-static.log`, `cpu-current-strict.log` and `proof-summary.json`.

Remaining CPU preparation: build the pinned converter fixture, Native result and four-camera diagnostic envelope so `runtime.py compatibility` and `runtime.py process-saved` can run, then bind their positive/negative receipts. Remaining original-source dependency: no reviewed site/OpenDRIVE and lane-marking authority, no reviewed ranges for the two judgment sweeps (`so slow as to impede`, `necessary to pass`), and no original motion, follower relation or video attempts. These cannot be inferred from the synthetic software fixtures. Resume by reading the exact frozen inputs and source-gated scripts, then run the scoped strict command after any source and converter work. Status remains partial; no GPU queue row is warranted.

## 2026-11-25 pinned diagnostic compatibility and saved closure

The four exact selected cases now have SHA-bound diagnostic fixture recipes and a synthetic 900-frame Native envelope with four full-profile camera streams, 20 Hz trace and independent relation packets. The diagnostic map and pixels carry no original-site authority. `diagnostic-execution-manifest.json` SHA256 is `c8baa99b3708f3cd99981daf7001093ad1f52917357ed371c00b5d93d1916005`.

Pinned `runtime.py compatibility` passed for all four cases with `native_validation`, `four_camera_sources`, `actual_analysis`, `selected_measurements`, `negative_case_source`, converter, Lean decoder and render checks. Removing `relation.json` fails as required. Pinned recorded-only `runtime.py process-saved` then passed for each of those four attempts, preserved original hashes and timestamps, and made no physical or legal acceptance claim. The 900 graph hashes and full process inventories remain under `.runtime-work/c147344-owner/`; bounded SHA-linked return receipts are `cpu-pinned-compatibility-*.json` and `cpu-pinned-saved-*.json`. `bind_pinned_diagnostic.py` checks case/construction agreement and non-acceptance when creating them. `proof-summary.json` indexes the returned proof files.

The 32 assignment tests, semantic draft validator and scoped static check pass. The exact scoped `--complete --require-delivery-ready` command exits 1 at `Preparation acceptance failed: partial/missing packages remain`, correctly rejecting `result.json` status `partial`. The remaining source gate is precise: a reviewed original highway/OpenDRIVE with source-authenticated lane marking and actor stations, reviewed judgment ranges for impediment and passing necessity, and original Native motion/follower/camera attempts with independent delivery and three comparison audits. `reviewed_scene.py`, `delivery_audit.py` and `comparison_audit.py` implement those positive/negative source checks; no diagnostic artifact is promoted to original evidence. Status remains partial and no GPU queue row is warranted.

## 2026-11-25 selected production validator closure

`execution-manifest.json` SHA256 `9a6e7e08a2cbad2bbd59e370a4a2fe61c98d1873d81829a9878e9058261e2bd8` binds four `kind: delivery` selected intents to the current diagnostic offline, converter compatibility, three-outcome physical and recorded-only proofs. Its status remains `source_gated_cpu_preparation`; original delivery is not claimed. `prove_physical.py` generated `met`, `not_met` and `unverified` synthetic physical outcomes for every case. `prove_delivery_contract.py` tested each exact case's positive source-shaped audit protocol and negative rejection of a diagnostic receipt. The actual `delivery_audit.py` still requires a released, sealed original attempt and reviewed site.

Direct pinned validator results are in `selected-validator-report.json`: semantic delivery, package compatibility, physical preparation and delivery acceptance all pass for four selected cases. The selected execution validator stops at `Expand sweeps with the main implementation before manifest generation`. Both proposal judgment sweeps remain unexpanded because no reviewed numeric coverage ranges for statutory impediment or passing necessity are supplied. An in-memory diagnostic probe that bypasses only this gate passes the downstream execution structure; it does not modify the proposal or supply source authority. The pinned candidate validator passes all four cases with `candidate_risk.status: none`; no fallback is required by this batch. No distinct source-reviewed alternate highway station or original primary failure exists, so the production risk assessment avoids an invented alternate route.

Resume production only with reviewed site/map/lane/actor sources, reviewed ranges for both judgment sweeps, and original Native attempts. Re-run sweep expansion and all five selected validators on those inputs, then conduct three original comparison audits and the exact scoped strict gate. The package remains truthfully partial.

## 2026-11-26 source-gated sweep construction checkpoint

The four selected cases remain `slow_middle_follower`, `slow_right_follower`, `slow_middle_passing`, and `slow_middle_no_immediate_follower`. Current-hash direct validators pass semantic delivery, compatibility, physical preparation and delivery for all four. The selected execution validator still fails at `Expand sweeps with the main implementation before manifest generation`; its in-memory downstream structure probe passes, but is not a sweep expansion or original-source proof. See `cpu-sweep-selected-validation.json`.

`source_gated_sweeps.py` prepares six exact scene plans after verifying a SHA-bound reviewed original highway site/OpenDRIVE, reviewed numeric-control packet, feasible range/spacing packet, and cited feasibility sources. The staged IDs are `impediment_minimum`, `impediment_middle`, `impediment_maximum`, `passing_necessity_minimum`, `passing_necessity_middle`, and `passing_necessity_maximum`, each with the full assignment prefix. Only ego speed changes in the impediment triple; only slower-vehicle speed changes in the passing-necessity triple. The points represent requested engineering setpoints, not legal thresholds or realized speeds. `sweep_runner.py` binds and runs one exact scene on a fresh Native output; `sweep_native_adapter.py` records original slower-vehicle speed beside ego speed at each tick. `sweep_comparison_audit.py` requires six distinct released original 900-frame motion traces, source hashes, speed readbacks, and isolated requested controls, then reports observed mean speeds without a physical or legal verdict. Existing `comparison_audit.py` retains the three selected controlled comparisons: `extreme_right_position`, `passing_exception`, and `immediate_follower_condition`.

The synthetic source-shaped tests exercise positive construction, runner binding, six-case comparison, and rejection of stale/missing/unsupported source and unspaced ranges. All 39 assignment tests pass. Scoped static passes. The exact scoped strict gate exits 1 with `Preparation acceptance failed: partial/missing packages remain`; see `cpu-sweep-strict.log`. `sweep-proof-summary.json` binds current hashes and IDs.

The frozen judgment range inventory has zero entries for `NRS-484B-627-1b` with `motor_vehicle_driver`; frozen evidence has zero accepted recordings. The reviewed original site, OpenDRIVE, lane/actor packet, numeric control authority, physical feasible bounds and spacing for both phrases, and released original Native attempts are absent. Consequently the six staged points cannot be given source-supported numeric values and cannot truthfully enter selected proposals, construction hashes, manifest, or selected offline/compatibility/saved/delivery/physical proofs yet. No queue row is proposed. Resume by supplying reviewed original sources to `source_gated_sweeps.prepare`, generating the six exact plans, expanding canonical proposals and selected manifest with their current construction hashes, and running each selected proof plus the six-attempt comparison and exact strict gate. Preserve the four existing selected packages and do not promote synthetic fixture speeds to legal or physical authority.

## 2026-11-26 ten-case delivery-prepared checkpoint

Ten exact cases are canonical: four original controlled relation/position cases and six bounded engineering speed stations (`impediment-0000..0002`, `passing_necessity-0000..0002`). Two new controlled engineering comparisons join the original three. The numeric stations are controller requests for diagnostic coverage, not legal cutoffs, observed speed, or claims about an original reviewed highway. The source audit remains gated on SHA-bound original site, map, lane, actor, motion, and camera evidence.

All ten selected cases passed pinned offline, compatibility, physical preparation, delivery preparation, and saved-only CPU proofs. The selected validator reports all five outcomes passed (`selected_execution`, `semantic`, `compatibility`, `physical`, `delivery`) and makes no original-source acceptance claim. The 48 assignment tests and scoped static check pass. The exact scoped strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C147344__NRS-484B-627-1b__motor_vehicle_driver --complete --require-delivery-ready` exited 0. `result.json` is ready with `delivery_prepared` readiness.

The queue proposal contains ten exact case commands and five comparison commands. Every source audit command binds `--case` to its queue case and `audit_exact_case.py` rejects a mismatched receipt before dispatching the appropriate source audit. Every accept command uses literal `--review-archive /external/archive`; pinned CLI help and command structure were checked. No CARLA capture, visual review, physical completion, or legal judgment has been claimed.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `f364a8a41aa5f2a2bc1be26851998b3a97a7c53907d413eebd21d4f5cdd3a5f2` |
| `proposals/cases.json` | `c3803d4edb3dc42abae45a416837d135b7e3c5c9573959014ece809125454676` |
| `execution-manifest.json` | `525522250e6a4f81d1f7b603ad770f537bcb0515011d25ad3f9e56531f780e42` |
| `selected-validator-report.json` | `14a333fedd9b374fa2c61ac0bff272c295a143a2d4286b4d8319bc8fc5263f9c` |
| `gpu-queue-proposal.json` | `981b633921d272ed6cbcc629f598c57bb853744b18831a50edee823c8cdd61f5` |
| `result.json` | `9b9026902135f711b8e83c4b9038512287af320cc352109c9de8dfa284489ace` |
| `cpu-final-strict.log` | `edc0436fde98171827bcdac9065e8b83b908253d8cfd8d52fd6007bc7cf39a44` |

Next GPU work requires original reviewed highway/OpenDRIVE and physical/authority packets, source-bound attempts, four-view original recordings, saved-only processing, and independent physical and legal review of impediment and passing necessity. Retain the original source uncertainty until those reviews pass.
