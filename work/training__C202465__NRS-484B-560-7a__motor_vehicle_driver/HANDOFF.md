# NRS-484B-560-7a at C202465

Actor: `motor_vehicle_driver`. Frozen cell: `rail_crossing` / `cross_railway` / `rail_track`.

Exact statutory source: NRS 484B.560(7)(a); with 484B.560(8). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Opposite-side space insufficiency..

Controlled planning variable: `opposite_side_clearance_feet`. Proposed requests: vehicle crosses without stopping and trailing end reaches 15 ft beyond nearest rail; insufficient opposite-side space causes stop before full 15-ft clearance. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: undercarriage-clearance alternative; completely-cross trailing-end definition.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/controller.py` requests paired 600-frame / 20 Hz rail-crossing target stations with one feedback policy. Its source-shaped proof `native/controller-proof.json` (SHA-256 `f7e8f1d3d8d276e3a5369782c964c713808d25884d4433a6dea2679248a9c913`) passes clear and short-stop targets and rejects movement after the stop, the wrong station and short capture. Synthetic positions and speeds are not original CARLA motion.

`native/measure_rail.py` and `native/measurement-contract.json` require original reference-rail geometry, vehicle body/trailing end, pre-entry opposite-side space, stop cause, 600 Native frame/time joins and four source-camera identities. The CPU proof `native/rail-proof.json` (SHA-256 `12ce3baec997b5fce63bbd3c7cfde76082b2bf901a20325ff7471c7765bb927a`) distinguishes trailing-end clearance beyond the law's 15 feet from a stop short of that distance and rejects six rail/source/frame defects. Fixture source hashes and attributed stop cause are placeholders; they do not establish a physical episode or legal outcome. Undercarriage clearance and exact reference-rail selection remain independently reviewed branches.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire CARLA crossing and four-camera capture, construct exact cases and undercarriage alternative, source the opposite-side queue and grade geometry, run exact offline/compatibility/saved-only proofs and independent audits, then run scoped strict ready gate before promotion.

## 2026-11-23 undercarriage and 15-foot threshold checkpoint

The source-shaped `native/measure_rail.py` now accepts an undercarriage-attributed preclear stop only with a source hash and a positive measured clearance deficit between the rail grade demand and minimum vehicle undercarriage clearance. It reports the attributed frame count and deficit separately from opposite-side-space stops. A 1-nm numeric tolerance makes a 15-foot boundary observation stable under floating-point conversion; a position 1 mm short still fails. `native/prove_rail.py` passes clear, space-short, exact-boundary, just-short and undercarriage-deficit fixtures, and rejects eight source/geometry/frame defects including missing undercarriage provenance and a nonpositive deficit. Updated `native/rail-proof.json` SHA-256: `66bd685daa6d8092cd9dbfcd2f01a7eb7f70afdd6869dcc254f3403f14aea4da`.

All fixture hashes, geometry and causal labels are synthetic. No original undercarriage source, Native episode, exact offline candidate, compatibility or saved-process proof has been established. Package remains `partial`.
