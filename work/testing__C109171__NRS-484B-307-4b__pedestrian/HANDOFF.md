# testing__C109171__NRS-484B-307-4b__pedestrian

Status: partial source-gated construction with four exact planned cases. No physical recording is claimed.

Exact law: NRS 484B.307(4)(b) — Where the signal is a green turn arrow alone: Pedestrians facing such a signal shall not enter the highway until permitted to proceed by another device as provided in NRS 484B.283 [NRS-484B-283-1d1, NRS-484B-283-1d2, NRS-484B-283-1d3, NRS-484B-283-1d4].
Assigned branch(es): Facing arrow before highway entry.
Cell: C109171 (intersection, enter_road, turn_arrow); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109171__NRS-484B-307-4b__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 source-gated construction checkpoint

No accepted recordings are listed in the frozen evidence inventory. The exact law restricts pedestrian highway entry while facing a sole green turn arrow until a different device permits proceeding. The reference to NRS 484B.283(1)(d)(1)-(4) remains an unresolved permission source, not a permission inferred from the arrow.

`case-plan.json` now has four exact cases: `arrow_wait`, `arrow_early_entry`, `arrow_walk_entry`, `arrow_walk_wait`. It isolates measured entry without other permission, separate-device permission, and the optional choice to wait after permission in three controlled comparisons. The comparison suffixes are under the assignment prefix in the plan. Every case carries the Native site/signal/visibility risk. The case plan has selected requirement dispositions and a source-cited gap because the frozen evidence list is empty.

`native_scene.py` checks SHA-256 of original map, vehicle-head and separate pedestrian-device sources; rejects conflated heads, ungoverned pedestrian devices, routes that start inside or never enter the surveyed highway polygon, non-sole-arrow frames and altered/missing source packets. It measures the first boundary entry and the separate device indication without a legal verdict. `pedestrian_control.py` issues injected CARLA-shaped walker controls for the exact wait and entry cases; it does not treat the arrow as permission. `comparison_audit.py` checks six fixed source/camera/duration conditions, sole-arrow frames and each measured deliberate difference; it returns no physical acceptance or legal verdict. These modules are portable construction drafts, not a pinned Native manifest.

Proofs: CPU preflight passed in `cpu-preflight.log`; 17 tests passed in `cpu-native-tests.log`; assignment `--complete` passed in `cpu-static-check.log`; exact assignment `--complete --require-delivery-ready` failed at the expected `Preparation acceptance failed: partial/missing packages remain` in `cpu-strict-check.log`. `result.json` binds SHA-256 of each log.

Next CPU work: bind a reviewed Native intersection/site/signal packet to all four exact bundles; create semantic stage proposals, executable CARLA capture and frame-map code, source-bound finalizer and diagnostic recipes; run offline and positive/negative compatibility for each case; implement saved-only processing and independent media/delivery audits with rejection tests; bind the canonical manifest and rerun the exact strict gate. Original site, arrow and pedestrian-device existence remain unverified; no available recording or CPU fixture establishes physical visibility.

## 2026-11-24 route progress and sampled-entry proof

The new `RouteFollower` retains waypoint progress across Native ticks, rejects nonfinite route or actor coordinates, and stops after the last waypoint. Waiting cases continue to request zero motion. Use one follower instance per attempt; `apply_case` is a single-step convenience only. `native_scene.measure_attempt` now rejects dropped sampled frames and reports the two consecutive samples bracketing first measured highway entry. The bracket is a sampling fact, not exact continuous crossing time or a legal verdict. All 20 focused CPU tests pass in `cpu-native-tests.log`; pinned runtime preflight passes in `cpu-preflight.log`.

Remaining CPU work is the source-bound Native site and exact bundles, finalization and diagnostic recipes, semantic proposals, saved-only and delivery audits, and their strict-gate proof.

The site verifier also now parses all three hash-bound original packets. It requires the highway polygon, pedestrian route and route ID to match the map source, the official sole-arrow head to match its signal source, and the separate pedestrian device to govern that exact route. Synthetic positive and altered-route, altered-arrow, altered-device rejection tests exercise these joins. These fixtures validate software behavior; no reviewed Native source packet has been supplied for this cell. The focused suite now has 23 passing tests.

## 2026-11-24 sealed saved timeline checkpoint

`saved_measurement.py` reads SHA-bound original Native site and per-frame event packets for all four exact cases. It requires contiguous frames, 20 Hz original simulation timestamps, sole arrow throughout, a separate-device timeline, and case-specific measured entry. The WALK-entry case requires a separate WALK sample strictly before the entry sample and at entry; waiting and no-WALK cases are checked across the full history. The output retains source hashes, the sampled entry bracket, and no legal or physical verdict. Five focused positive/negative tests bring the suite to 28 passing tests. Synthetic packets validate software checks only.

Still needed: reviewed actual Native map/head/device packet, executable exact capture and four-camera frame map, canonical bundles/manifest and semantic proposals, saved-only runtime processing/compatibility, media delivery audit, and physical review. The cited NRS 484B.283 permission alternatives remain for legal review; an observed WALK string alone is not asserted statutory permission.

## 2026-11-24 synchronized Native capture and media proof

`native_capture.py` provides a source-gated Native adapter writer for all four exact cases. It requires the original site packet and map/head/device hashes, 600 contiguous 20 Hz event frames, and four matching original camera callbacks (`front`, `left`, `right`, `rear`) on each frame. It writes an exact event source, frame map and 2,400 PNGs under an attempt directory outside returned work, then reruns `measure_saved`. `audit_frame_map` independently reopens every PNG, checks SHA-256, frame/time joins and 20 Hz drift. The adapter must supply simulator events, camera bytes and resource cleanup; the writer does not call a CARLA world itself or attest provenance.

Focused CPU tests now pass 34/34, including a full 600-frame/2,400-camera fixture and negative event drift, callback drift, tampered pixel and diagnostic-site cases. This is a software proof using synthetic source-shaped packets, not a physical recording. Scoped `--complete` passes. Scoped strict still fails because the package remains partial.

Next CPU work: connect this adapter protocol to an actual CARLA world and surveyed C109171 map/head/device packet; author canonical semantic proposals, exact inline bundles, source-bound diagnostic recipes and positive/negative compatibility receipts; bind saved-only runtime processing and delivery manifest; add physical camera visibility audit and final independent statutory review. Continue to keep legal permission under NRS 484B.283 unresolved pending reviewed source facts.

## 2026-11-24 lazy CARLA adapter checkpoint

`carla_adapter.py` now connects the Native writer to a borrowed synchronous CARLA world, pedestrian actor, four camera sensors, and an injected original-state reader. It checks 20 Hz world settings, consecutive world ticks, each camera callback's world frame, raw BGRA byte count and PNG conversion. The retained route follower applies measured-route controls; every exit stops sensor listeners and requests a zero-speed walker control. The original-state reader must come from verified signal/device sources and is never inferred from case labels. Five fake-world CPU tests cover normal motion, waiting, missing camera, camera frame drift, and asynchronous-world rejection. The focused suite now passes 39/39. This is still a software interface proof; no actual C109171 Native site, official head, pedestrian device, visibility or statutory permission has been verified.

Scoped static `--complete` passes; exact scoped strict remains an expected failure because `result.json` truthfully stays partial.

## 2026-11-24 Native pedestrian source join checkpoint

`carla_adapter.py` now reads the post-tick world snapshot and actual pedestrian actor position. It requires the injected original-state packet's world frame, simulation time and pedestrian XY to agree with those Native sources before retaining the event. This closes a CPU-solvable gap where a source reader could return an invented crossing position or timestamp while all camera callbacks were valid. Three new fake-world rejection tests cover altered position, altered time and snapshot-frame drift. The full focused suite passes 42 tests. The injected reader still must supply actual official signal and separate pedestrian-device observations from verified sources; this code does not infer permission from a WALK string or establish physical visibility. Canonical per-case bundles, proposals, positive/negative compatibility, saved-only processing and delivery audit receipts remain unfinished CPU work.

## 2026-11-23 saved-only pedestrian process checkpoint

`saved_process.py:process` now runs the exact case source-bound entry and separate-WALK measurement together with `native_capture.audit_frame_map`, reopening every original camera PNG and checking the 20 Hz event/frame/source joins before writing one receipt. It retains site, event and frame-map SHA256, the sampled entry bracket, camera audit and an unresolved statutory permission field. A changed camera original prevents output; a prior receipt is never overwritten. Diagnostic CPU fixtures establish software behavior only, and WALK remains an observation rather than inferred legal permission.

Forty-four focused tests pass in `cpu-saved-process-tests.log` (SHA256 `f8e8fce2a2dc3cabb3c7373aba5e96303d8e2eef57934e3cb8e8d246a86bbcba`). Pinned CPU preflight exits 0 (`cpu-saved-process-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Scoped static exits 0 (`cpu-saved-process-static.log`, SHA256 `2c4e093e0f1887e9048e23e9569eb9ef8191c0ef171690075be4dbc5944a4e3b`). Exact scoped strict exits 1 on truthful partial status (`cpu-saved-process-strict.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Next CPU work: verified original official head and pedestrian-device reader for the exact surveyed site, four canonical inline bundles and semantic proposals, positive/negative compatibility, exact manifest and independent delivery receipt. No Native physical camera visibility or NRS 484B.283 permission alternative has been accepted.
