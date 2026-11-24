# testing__C111329__NRS-484B-287-1e__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.287(1)(e) — Except as provided in NRS 484B.290 [LVMC-11-30-140-B]: When authorized to cross diagonally, pedestrians shall cross only in accordance with the official traffic-control devices pertaining to such crossing movements.
Assigned branch(es): Authorized crossing during pedestrian travel.
Cell: C111329 (intersection, travel, traffic_control_device); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1e__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint — 2026-11-23

Exact cases in `case-plan.json`: `__permissive_whole_crossing`, `__prohibitive_whole_crossing`, and `__instruction_changes_during_crossing` (each prefixed by this assignment ID). Two comparisons keep the measured opposite-corner route and official pedestrian-diagonal device fixed while varying its observed instruction. NRS 484B.290 remains an unresolved referenced exception; no legal label or numeric clearance threshold is inferred. The frozen evidence inventory has zero accepted recordings and the conditional witness is not a physical receipt.

`diagonal_crossing.py` validates source hashes for map, corner survey, authorization, device inventory and exception review; requires an opposite-corner route and pedestrian-diagonal governing device; lazily spawns the walker and applies route control with readback/cleanup. `crossing_audit.py` checks original contiguous walker and device frames, actor identity, crossing footprint, synchronized device identity/governance/instruction and fixed-condition comparison isolation. The source packet is an interface, not a claim that the frozen cell already supplies the required site. Physical risk: map route reachability and device provenance are unverified; no fallback is claimed without an exact tested construction.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-287-1e__pedestrian/tests -v` passed 3 tests; see `cpu-tests.log` and `result.json` SHA. `.venv-cpu/bin/python worker_check.py --assignment testing__C111329__NRS-484B-287-1e__pedestrian --complete --require-delivery-ready` returned exit 1 with the expected partial/missing package acceptance error; see `strict-check.log` and its SHA in `result.json`.

Next CPU work: bind a real source-surveyed diagonal site and official pedestrian-governing device; make each exact case a runnable construction bundle with source packets, finalizer, diagnostic recipe, semantic proposals, four-camera capture and manifest; run offline and positive/negative compatibility for every case; test saved-only processing and an independent full delivery audit. Only then rerun the exact strict gate and mark ready if it passes. Actual Native motion and video visibility remain later physical checks.

## Saved-attempt measurement checkpoint — 2026-11-24

`saved_crossing.py` consumes an exact-case `acquisition.json` and SHA-sealed site, walker, governing-device, four-camera original-frame and crossing-footprint sources. It confines attempt-relative source paths; joins contiguous original frames and 20 Hz timestamps; requires every camera to read back each original frame; binds every device readback to the site device-inventory hash; applies the existing crossing audit; and enforces the permissive, prohibitive or phase-change instruction pattern for the requested case. Its output explicitly leaves full video decode, physical completion and legal judgment unverified. Diagnostic attempts are rejected unless the test-only `allow_diagnostic=True` is passed. No site, official status or physical capture is asserted by the synthetic test.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111329__NRS-484B-287-1e__pedestrian/tests -v` passed 7 tests in `cpu-tests.log`, including source/path, frame/time, camera, device and case negatives. The scoped `--complete` check passed in `static-check.log`; exact scoped `--complete --require-delivery-ready` exited 1 in `strict-check.log` because this package remains partial. Hashes are in `result.json`.

Next CPU work: source-review a real site and its official diagonal pedestrian device and NRS 484B.290 exception; bind those sources to each exact construction, add original capture and four-camera media with full decode, author semantic proposals, finalizer and delivery audit, run per-case offline/compatibility and process-saved proofs, then rerun strict.

`audit_saved_comparison` accepts only the two declared reference/variant pairs and rejects diagnostic measurements in delivery mode. It checks the same sealed site, 20 Hz/four-camera contract, device inventory and ID, exception-review state and original crossing frames while requiring the observed instruction contrast. It does not require identical simulator actor IDs across separate captures. The negative test changes site hash, camera contract and crossing frames. The focused suite now passes 8 tests; all three log hashes in `result.json` were refreshed after the scoped checks.

## Original diagonal acquisition and local source binding, 2026-11-24

`native_capture.py` now captures exactly 900 synchronous 20 Hz original Native frames from walker, official diagonal-device and four camera identity readers. It rejects frame/time drift, changed device or inventory identity, missing views and non-Native readbacks before sealing the saved walker/device/frame-map packet. Reviewed map, corner, authorization, device-inventory and exception-review bytes are copied into the attempt and source-bound. The local site uses attempt-relative references so identical sites have stable hashes across separate exact captures; `diagonal_crossing.validate_site` resolves those refs against the sealed attempt root. The bridge runs saved-only measurement before retaining its acquisition receipt. Unattested capture defaults to diagnostic and cannot publish non-diagnostic evidence. Original camera media and physical/legal findings remain unverified.

Pinned preflight, 11 focused tests and scoped static passed. Exact scoped strict exited 1 on truthful partial. New SHA-bound logs:

- `cpu-native-preflight.log` SHA256 `c91a159dd6a3195d541e40ffb98b512a80485d1384d674a898634dab5d87ab7b` exit 0.
- `cpu-native-tests.log` SHA256 `16b687dbe9bbed204193dcbcfe198cc5ae88a1748fc9b4d858f84b36e2e30712` exit 0.
- `cpu-native-static.log` SHA256 `eb23bd8689dc8a4f3633aa409b7e3f48122673352264b6aad3782b4eab2f5d15` exit 0.
- `cpu-native-strict.log` SHA256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` exit 1.

Remaining CPU work: source-surveyed official diagonal device and NRS 484B.290 review, original camera media/full decode, exact runnable construction bundles and finalizers, canonical semantic proposals/manifest, offline and positive/negative compatibility, saved independent delivery and comparison receipts.
