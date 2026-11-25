# testing__C150099__LVMC-11-52-130-A2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.52.130(A)(2) — No person shall stop, stand or park a vehicle except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device, in any of the following places: At any place or in any space adjacent to a curb which has been designated and posted as a fire lane pursuant to the City's Fire Code, whether the vehicle is attended or unattended and whether the location is on public or private property.
Assigned branch(es): Parking in a designated and posted curb-adjacent fire lane.
Cell: C150099 (one_way_road, park, fire_lane_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150099__LVMC-11-52-130-A2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 executable fire-lane checkpoint

- The exact law requires a curb-adjacent place or space designated **and posted** as a fire lane pursuant to the City Fire Code. It covers stop, stand and park, attended and unattended vehicles, and public and private property. The introductory exceptions are lawful necessity to avoid other traffic conflict, police direction and traffic-device direction. No numeric statutory boundary or judgment-range entry applies here. The frozen accepted-recording inventory is empty.
- `case-plan.json` now proposes ten exact cases: public/private attended/unattended park, public stop/stand, parking outside the posted extent, and the three source-distinct exceptions. Eight comparisons isolate attendance, activity, posted-extent position or exception source. Public/private cases are both covered but deliberately not paired as a controlled property-only comparison: changing parcel normally changes location and potentially the physical sign. Every case has a physical-risk assessment. No legal outcome is inferred.
- `fire_lane.py` requires City jurisdiction, location-specific Fire Code designation and posting sources, sign identity and appearance, curb and posted extent, property source, one-way approach, vehicle and four-camera source. It creates or looks up a physical sign, reads back presence and identity, creates the ego, commands a curb target and attendance, and cleans owned actors on failure. `measure_original_history` measures body overlap and curb gap only from contiguous original frames at 20 Hz; commanded target never substitutes for observed position. `audit_comparison` checks source identity and undeclared changes.
- `saved_audit.py` independently hashes and decodes a 900-frame original Native history, checks source and frame joins, sign readback, body footprint, attendance, property, exception source and four named camera-frame references. This is a CPU saved-source check, not a full video decode or physical-visibility proof. `tests/test_fire_lane.py` passed eight focused tests, including missing designation/sign/exception source, owned-resource cleanup, timing/source tampering, comparison fixed-condition tampering, and sealed-history camera/hash/timing tampering.
- `.venv-cpu/bin/python runtime.py preflight` passed (`preflight.log`). Exact `worker_check.py --assignment testing__C150099__LVMC-11-52-130-A2__motor_vehicle_driver --complete` passed (`complete-check.log`). Its `--require-delivery-ready` variant failed at `Preparation acceptance failed: partial/missing packages remain` (`strict-check.log`), consistent with the truthful partial result. Test and check log hashes are in `result.json`.
- Next CPU work: create the case-specific Native runner/config/finalizer and 20 Hz four-camera acquisition for each planned case, exact execution manifest and justified tested fallbacks, canonical semantic proposals and index, source-hashed diagnostic recipes, offline and positive/negative compatibility receipts, saved-only `process-saved` path, and full independently decoded delivery audit with negative proof. The actual location-specific Fire Code designation records and physical sign/vehicle visibility must be checked against original capture, not asserted from this fixture. Re-run exact strict check after those CPU deliverables.

## 2026-11-24 four-camera original-frame join checkpoint

The saved independent audit now requires exactly front, rear, left and right camera packets on every original history row. Each packet must carry the same original frame ID as that row and a 64-character SHA256 source digest. Resealed histories with a missing packet or an off-by-one camera frame are rejected. The fixture proves only saved-source consistency, not physical camera visibility.

### Receipts

- `cpu-camera-join-tests.log` exit 0, SHA256 `eafe4f3625d150f485d3feb630338a66b0d5d54506c6595b5a3d2ee53bed7ddd`
- `cpu-camera-join-preflight.log` exit 0, SHA256 `bc69691469b410bc924b5b75e97e3505fdc9ba29a8a7b1aa8d77d8c7f04ebd96`
- `cpu-camera-join-static.log` exit 0, SHA256 `c8823939f74113616bb2aaf5562cb706a8c5835d8616bf81c0b8b4aaf3906246`
- `cpu-camera-join-strict.log` exit 1, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`

- `saved_audit.py` SHA256 `830b145ea57ef2900af2982ebc651a2f91c7d2735d9ee88c88270abf2a7f1874`
- `tests/test_fire_lane.py` SHA256 `7afa5d8ee8eab5406241429b51f4884be4151650a60a22f06ddb0c4e5955fb54`

Eight focused tests, pinned preflight and scoped complete static check pass. Exact scoped strict exits 1 because status remains partial. Next CPU work: per-case Native bundles, diagnostics, positive/negative compatibility, semantic proposals and full independent delivery audit.

## 2026-11-25 source-bound diagnostic proof checkpoint

The prior opening inventory describes an earlier checkpoint. The current package contains ten exact selected constructions and eight controlled comparisons; see `case-plan.json`, `execution-manifest.json`, and `cpu-proof-index.json` for the current identities and source hashes. No official designation, posting, legal exception, physical visibility or legal outcome is inferred from a synthetic fixture.

Pinned CPU proof now passes 10/10 offline constructions, 10/10 positive compatibility receipts, 10/10 missing-source compatibility negatives, 10/10 recorded-only `process-saved` fixtures, and eight diagnostic pair audits. The saved missing-history negative passed with `recorded_only=true`, `native_replay_requested=false`, and `missing_evidence=true`. The independent `delivery_audit.py` checks copied reviewed packet bytes, original history/frame-map joins and all four original PNG archives. Its new saved-channel path independently joins all six emitted channels to original history, trace and frame map; 10 diagnostic positives and one tampered activity-channel rejection passed. These proofs are diagnostic and do not assert physical acceptance.

Direct selected compatibility validation passed. Direct execution validation reports missing physical preparation receipts; candidate validation reports untested fallbacks for declared physical sign/curb risk; semantic validation reports missing `proposals/semantic-index.json`; delivery handoff validation reports missing selected acceptance contracts. These are remaining worker-owned CPU deliverables. Location-specific reviewed City Fire Code designation and posted extent source are absent and remain source-gated for any original attempt or semantic judgment range. Complete static scoped check exits 0; exact scoped strict check exits 1 at truthful partial status. Source hashes and check logs are indexed in `cpu-proof-index.json`.

## 2026-11-25 selected CPU delivery checkpoint

The selected manifest now binds ten exact constructions with a physically distinct slow-approach fallback for curb-target overshoot risk. All 20 primary/fallback offline runs and all 20 positive plus 20 missing-source compatibility checks passed. Ten recorded-only saved processing fixtures, ten saved-channel audits and one tamper rejection passed; all fixtures remain diagnostic.

Canonical seven-stage semantic proposals validate for ten cases. The two judgment sweep specifications are explicitly incomplete and source-gated: conflict necessity and City Fire Code designation/posting have no reviewed location-specific source or measured below/inside/above bounds. No statutory numeric cutoff is invented.

Thirty physical motion fixtures (complete, incomplete, missing evidence) passed. Ten pinned lifecycle tests reject Native owner release before exit, Native exit before encoder/restoration closure, saved-only processing before owner release, and duplicate release; then accept the ordered diagnostic receipt. Direct pinned physical preparation validation passes 10/10. These tests attest synthetic ordering, not actual CARLA owner release.

The selected delivery auditor passed ten diagnostic positives and ten default synthetic-source rejections. It joins six law channels to original history, trace and frame map, verifies ego/sign identities and source-review files, decodes every frame of four camera videos and the composed video, and records decoded pixel hashes. Physical completion stays unverified on the nine-frame synthetic captures. Direct pinned delivery handoff validation passes 10/10. Direct semantic validation returns seven stages and ten cases; compatibility, candidate, physical and delivery validators pass for all ten cases. The scoped complete static check passes. The exact scoped strict check exits 1 at the truthful partial-status gate.

Remaining CPU source work: obtain and bind a reviewed City Fire Code designation/posting packet for the selected curb and complete the conflict-necessity and designation/posting judgment sweep measurements against source-grounded observations. Original capture and legal classification remain unclaimed.

Direct pinned `execution_manifest.validate(repo, assignment_id)` was rerun after the final manifest hash and exited 0. It validates manifest structure and proof references; the two explicitly incomplete source-grounded judgment sweeps remain a readiness gap in the selected CPU package, so `result.json` stays partial.
