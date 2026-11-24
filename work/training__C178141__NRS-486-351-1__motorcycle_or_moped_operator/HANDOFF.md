# NRS-486-351-1 at C178141

Actor: `motorcycle_or_moped_operator`. Frozen cell: `paved_road` / `lane_split` / `other_vehicle`.

Exact statutory source: NRS 486.351(1). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Stationary surrounding vehicles.

Controlled planning variable: `between_adjacent_vehicles`. Proposed requests: motorcycle remains in occupied lane beside adjacent vehicles; motorcycle rides between vehicles occupying adjacent lanes. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: moving or stationary vehicles; police duty exception.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/route.py` requests paired 600-frame / 20 Hz motorcycle trajectories with identical longitudinal progress and speed, changing only lateral position. The route proof `native/route-proof.json` (SHA-256 `2e61678ef5f290d67d9c2abd7427043158a103b95a4e47f424c97bf59f03bae3`) checks the controlled difference and rejects three invalid requests. This is a requested route, not observed CARLA motion.

`native/measure_split.py` and `native/measurement-contract.json` require original Native lane adjacency, both surrounding vehicles' lane occupancy and speeds, the motorcycle footprint, 600 frame/time joins and all four source-camera identities. The source-shaped CPU proof `native/split-proof.json` (SHA-256 `81013609e699c700a19e129b326a548843d87803eda2a111d72c20dbde794f21`) distinguishes beside from between for stationary surrounding vehicles, also checks moving surroundings, and rejects six source/frame/actor defects. Placeholder hashes and synthetic actor paths are not original evidence. The police-duty exception and motorcycle/moped alternatives need source-backed cases. No engineering persistence duration is presented as a legal cutoff.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire CARLA capture, exact constructions and four source cameras; complete moving/stationary and police-duty branches; run exact offline, compatibility, saved-only and independent delivery/comparison audits; run scoped strict ready gate before promotion.
