# testing__C230223__NRS-484B-270-4__motor_vehicle_driver

Status: partial source-gated CPU package. Four controlled cases and three comparisons are proposed; no original recording is selected.

Exact law: NRS 484B.270(4) — Except as otherwise provided in subsection 3 [NRS-484B-270-3], the driver of a motor vehicle shall not enter or proceed through an intersection while driving within a pathway or lane provided for bicycles, electric bicycles or electric scooters.
Assigned branch(es): Road-route intersection passage within a designated cycle lane.
Cell: C230223 (road, travel, cycle_lane); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C230223__NRS-484B-270-4__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The law prohibits a motor vehicle entering or proceeding through an intersection while driving within a pathway/lane provided for bicycles, electric bicycles or electric scooters, except subsection 3. `case-plan.json` now has four unselected constructions and three isolated comparisons for cycle-lane intersection overlap, lane designation and subsection 3 review. No accepted recordings exist in the frozen inventory.

`cycle_lane_intersection.py` binds original source SHA256, validates motor-vehicle, intersection and designated-cycle-lane identities, and tests simultaneous 20 Hz body occupation of the intersection and designated cycle lane. It preserves subsection 3 status separately. Five synthetic CPU tests cover true overlap, lane ending before intersection, ordinary-lane passage, missing designation and unresolved exception. A paint mark alone does not establish source designation.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `15b169236ed034de5b23db2d6782f90350e7a493c2da5bcbaf982bf164ca0e38` |
| `cycle_lane_intersection.py` | `e368f272b2a751eac9f509f80c23d0454da19f68d70af6cc272e92b1cec70dc5` |
| `tests/test_cycle_lane_intersection.py` | `0da909e5efbd56f45809bfd65ae106e1be03cfb557d15e6e349245ae9179119f` |
| `preflight.log` | `7ee5fe7578467aa00d469f61b6bfabced089d97ceb7113d5f24c6f5ea5411342` |
| `unittest.log` | `cd1b2d5a7f2bc27c072900612e667a49275861c786b0817c1f862f2e64768e16` |
| `static.log` | `ca883a18ff02814b24d102da8ee269a293ecc2e9a87dad0e273ee93031551a41` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct/read back actual designated cycle-lane and intersection polygons and source vehicle occupation; review subsection 3; implement saved finalizer, exact positive/negative compatibility and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.

## 2026-11-23 route construction and receipt repair

`cycle_lane_site.py` now selects a named route against source-bound intersection and designated cycle-lane polygons. It partitions each route segment at polygon boundaries, so an overlap may be established between waypoints. It rejects routes that miss the intersection or contradict the requested overlap. Six focused geometry tests include a lane ending before the intersection, an ordinary road route and a route with no interior waypoint. These fixtures exercise construction logic only; no actual source map or recording is claimed. The eleven combined CPU tests pass.

`result.json.tests` contains only successful preflight, unit and scoped-static receipts with package-relative logs, exact commands, exit code 0 and verified SHA256. The exact scoped strict check remains exit 1 on truthful partial status and is recorded only in this handoff and `strict.log`.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `d939f357ecc57665e512c9845b8eb060c316d706613062c9b74b209ec74c0a5f` |
| `cycle_lane_site.py` | `96c7e3dd03beba7a22c7027921cbce7aa92fe6262d4f98b41d8bbab73d2a14e9` |
| `tests/test_cycle_lane_site.py` | `1a5499986017b51f6b0c0c05f7430531f6b9c0d0d9bd291a9e6a2b19f0a7450c` |
| `preflight.log` | `e1bf784607ef5dad85eebb0af01619625e84b1be637bc243d58ccd1ac83b5cf7` |
| `unittest.log` | `e95ba2d69907576ecbaf34df8e5e7a00baa61b91e0ec409a71107da67b74337d` |
| `static.log` | `ca883a18ff02814b24d102da8ee269a293ecc2e9a87dad0e273ee93031551a41` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |
| `result.json` | `ec3f5a55fcf1d26181131ab827c92ffed91a59da0354c9199ea0b6e85d5f1134` |

Next CPU work: bind a real source map and designation authority to exact route candidates, inspect subsection 3's authoritative exception, implement original saved acquisition and finalizer, prove each exact bundle positive and negative compatibility, then run saved-only processing and delivery/comparison audits. Actual motion and camera quality remain later GPU checks.

## 2026-11-25 source-gated Native and saved audit checkpoint

Added `cycle_lane_native.py` for independently hash-checked public-intersection, cycle-lane designation, subsection 3 and motor-vehicle packets, exact route selection, fixed 45-second four-camera profile and deterministic steering control. The route controller is CPU tested; no Native world/camera capture was run or claimed.

Added `cycle_lane_original.py` for 900 consecutive 20 Hz original-frame, actor and body-polygon joins against the reviewed intersection and designated cycle-lane polygons. `cycle_lane_delivery.py` checks SHA-256 custody and full 900-frame decode for each of four camera views. `cycle_lane_comparison.py` independently re-audits the four original attempts, requires the same site, vehicle, camera policy and authoritative exception clause across each of the three planned pairs, and checks the exact deliberate overlap or exception-status difference. `cycle_lane_finalize.py` exposes a saved-only production CLI using externally supplied reviewed hashes. No legal or physical acceptance verdict is generated.

Draft canonical semantic proposals under `proposals/` bind all four cases and three comparisons while explicitly retaining source review gaps. The synthetic software suite passed 29 tests, including full four-case saved finalization with 900-frame videos, missing-source and corrupted-media negatives, polygon/flag mismatch and comparison-isolation negatives. The source fixtures are synthetic and stay under `.runtime-work/`. Updated preflight and scoped static pass. Exact scoped strict exits 1 because the truthful package status is `partial`.

Exact remaining prerequisites: a reviewed source map with a genuine public intersection, designated cycle-lane polygon and authority, four route candidates, authoritative subsection 3 clause and case-specific applicability, and reviewed motor-vehicle/driver packet. These must supply independently reviewed SHA-256 values to the source-gated construction/finalizer. Remaining CPU implementation after that source binding: materialize the exact Native runner and canonical runtime construction bundles, selected execution manifest, positive/negative pinned compatibility and recorded-only process-saved, physical-risk candidate proofs, and selected delivery/comparison receipt bindings. No source or legal cutoff has been fabricated.

Production saved CLI: `.venv-cpu/bin/python work/testing__C230223__NRS-484B-270-4__motor_vehicle_driver/cycle_lane_finalize.py --review /external/reviewed-cycle-lane-attempts.json --output .runtime-work/c230223-original-finalized.json`. The review JSON must contain `attempts` and `reviews` maps keyed by all four case IDs; each review entry has independent `site`, `subsection_3`, and `vehicle` SHA-256 values.

| File | SHA256 |
| --- | --- |
| `cycle_lane_native.py` | `eb895c37667195b8a9d5a68bf8a009dcb2dc52d43a400bdef206199477182125` |
| `cycle_lane_original.py` | `bd5b60bc98413da0c588fea38405fe4ce3ffe63b70da0309608b465c481a2d98` |
| `cycle_lane_delivery.py` | `735b95382ba769d9606808ca7bd4711c7f13aa55d6312426caf493db53978a5e` |
| `cycle_lane_comparison.py` | `6da750b4edb53a550e1417c0016956fdf9ff00b91af833089d82606347aaf778` |
| `cycle_lane_finalize.py` | `a9c0ee48510e8b80788aa4d647548f958f9c6cc75e9f47e032082fedfd735d14` |
| `tests/test_cycle_lane_native.py` | `7b524eb35e66a2d189164835339be60ba7c41a9c4707247a6a37b48358df5619` |
| `tests/test_cycle_lane_original.py` | `e20999cbd26f58951861bf97176472f0deeacec4840de1ce991be3e01342812f` |
| `tests/test_cycle_lane_delivery.py` | `fb1aaf7e660a5bc8e236ab35bee0ed24ab8f72bc3b18b873f028048a46cc9cb6` |
| `tests/test_cycle_lane_comparison.py` | `4767f1f7a3859014c4a083b803da97edc23dd801e52a11c88e578971c51fa558` |
| `proposals/semantic-index.json` | `d26427253a36730713cbe457fa2284e50e997ca8c3a0d54a22523828a493a76b` |
| `cpu-preflight-20261125.log` | `828f94b81ba3dfbdcf5e2a0a1981736667ecc31010f72e746bb652a6fdcfd1e9` |
| `cpu-tests-20261125.log` | `a4614c36140d623eb0ca93b1a438ff87c3e8467bfd591cfde5cb744f9c6c5eee` |
| `cpu-static-20261125.log` | `ca883a18ff02814b24d102da8ee269a293ecc2e9a87dad0e273ee93031551a41` |
| `cpu-strict-20261125.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

The package-local `physical-risk-draft.json` records per-case route/lane failure modes and one shared measurable fallback policy. Its candidate remains unselected and unproved; the draft is not a physical-risk acceptance receipt. SHA256: `514c933f301c46dfcc348df7eca0d2a0e389affac447150f192ac77f4cb27aba`.
## 2026-11-25 selected CPU proof closure

The selected `execution-manifest.json` SHA256 is `887ab6b006c812f1df4c8cfc3826219d97a4b8d04a99066deddd738bf0832235`. Four exact source-gated Native constructions have finalizers, 900-frame four-camera diagnostic recipes, per-case measurement contracts and missing-site negative tests. All four pinned `runtime.py offline`, `runtime.py compatibility` and recorded-only `runtime.py process-saved` commands exit 0. Compatibility exercises the actual case analysis, Native converter, full Core decoder, four-view render/decode and a source-specific negative. The diagnostic fixtures are synthetic; no original-source or physical acceptance claim follows. Each case also has three measured physical checker outcomes (met, not met, unverified), a synthetic lifecycle proof and positive/negative delivery protocol proof. The 30 assignment CPU tests pass.

Direct pinned selected validators pass for execution (4 cases), semantic (5 stages, 4 selected cases), physical (4), delivery (4) and compatibility receipts (4). The repeatable validator command is `.venv-cpu/bin/python work/testing__C230223__NRS-484B-270-4__motor_vehicle_driver/validate_selected.py` with `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`; its final log is `selected-validator-results.log`. The Native adapter now writes the converter's evidence, graph, frame-index and manifest files for an original capture. Its attempt seal binds the actual spawned actor ID to all 900 source body rows and separately binds the reviewed vehicle blueprint/driver packet; a pre-spawn source packet cannot know the simulator actor ID. The production `cycle_lane_finalize.py` still requires independent review hashes and four distinct original attempts before the three fixed-source comparison audits.

Remaining original-source dependency: an independently reviewed genuine public intersection/OpenDRIVE map, designated cycle-lane geometry and authority, four route candidates, authoritative subsection 3 clause with case-specific applicability, and a reviewed motor-vehicle blueprint/driver identity packet. No such packets are present in the frozen assignment or this work directory. Their exact SHA256 values must be supplied through `C230223_REVIEWED_PACKET`; the saved finalizer independently requires the three reviewed hashes for each case. Original Native capture, pixels, physical completion and legal interpretation remain unclaimed.

The scoped `worker_check.py --assignment testing__C230223__NRS-484B-270-4__motor_vehicle_driver --complete` passes. The exact `--complete --require-delivery-ready` gate exits 1 at truthful partial/missing-package acceptance. No transient ready status was staged. All scratch and generated videos stayed under `.runtime-work/`; returned diagnostic specs are under 2 MiB.
