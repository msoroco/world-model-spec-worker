# LVMC-11-52-305-A at C135709

Actor: `heavy_vehicle_driver`. Frozen cell: `narrow_road` / `park` / `parking_restriction_device`.

Exact statutory source: LVMC 11.52.305(A); with 11.52.305(B). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Covered commercial vehicle parked beside a public park.

Controlled planning variable: `covered_vehicle_parking_adjacency`. Proposed requests: covered commercial vehicle parks away from protected adjacency; same covered vehicle parks beside public park. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: posted sign permission; residence district 300-foot definition; public school; loading/delivery exception; essential local service exception; 24-foot length or 8000-pound weight.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/controller.py` now gives both park-frontage probes the same 600-frame / 20 Hz feedback policy, changing only the requested station. Its source-shaped CPU proof, `native/controller-proof.json` (SHA-256 `a7396c10bee0f2d59ccbc35435a0056c0b4ab83c7e80743e069e8d15fd469fe0`), passes two positive targets and rejects movement during the hold, the wrong frontage station and a shortened trace. The synthetic trajectory only tests controller and validation logic; it is not original CARLA motion.

`native/measure_parking.py` and `native/measurement-contract.json` define the saved-source join for original Native frame identities, four source-camera identities, observed speed and footprint, the surveyed street/park boundary, external public-park status and commercial vehicle specifications. The 600-frame CPU proof, `native/parking-proof.json` (SHA-256 `1e9659def0715092961e269f17b3df4e927a640c213fe7671a85f3d2177dd795`), distinguishes parking away from versus beside the park frontage and rejects eight source/frame/geometry defects. Fixture source hashes are placeholders and do not establish original provenance, actual park status, physical adjacency or any legal outcome.

Pinned `.venv-cpu/bin/python runtime.py preflight` and assignment-scoped `.venv-cpu/bin/python worker_check.py --assignment training__C135709__LVMC-11-52-305-A__heavy_vehicle_driver --complete` both pass as partial-package checks. Next CPU work: build the actual CARLA capture runner and exact four-camera constructions, source the public-park and commercial-vehicle facts, add posted-permission/loading/service exception cases and measurements, then run exact offline, compatibility, saved-only and independent delivery/comparison proofs. The package remains `partial`.
