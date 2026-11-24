# LVMC-11-27-010-A at C143691

Actor: `motor_vehicle_driver`. Frozen cell: `nonmotorized_trail` / `travel` / `barrier`.

Exact statutory source: LVMC 11.27.010(A); with 11.27.010(B). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Conjunctive trail prerequisites, subject to all Subsection (B) exceptions.

Controlled planning variable: `motorized_trail_occupancy`. Proposed requests: ordinary motor vehicle stays outside posted dedicated designated trail right-of-way; same vehicle enters trail right-of-way. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: three conjunctive trail prerequisites; emergency vehicle; maintenance vehicle; mobility device.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/route.py` now requests paired 600-frame / 20 Hz trajectories with one controlled lateral difference: staying outside versus traveling within the planned trail right-of-way. The route proof `native/route-proof.json` (SHA-256 `5515e4dbd894d43d2ab6629529f030fdea014d558b76b39bd1c3a058a0931559`) checks the same forward speed/position, a traversable barrier-gap request and three negative scene mutations. This is an engineering route proposal, not observed CARLA motion or a determination that the actual barrier is passable.

`native/measure_trail.py` and `native/measurement-contract.json` require original Native footprint, frame/time and four source-camera identities plus independent designation, dedication, posted-sign, vehicle-identity and map sources. The source-shaped CPU proof `native/trail-proof.json` (SHA-256 `7d7b64f1bca080d93aa3b2319244d417a90a44d8f7db0709aad249e06ad25656`) distinguishes zero versus positive trail occupancy and rejects nine source, barrier and frame defects. The fixture uses placeholder hashes and cannot establish the administrative facts, physical entry, sign appropriateness, exception status or legal outcome.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire a CARLA runner to the route and four cameras; build exact cases and risk-based candidates; source and measure emergency, maintenance and mobility-device exceptions; run exact offline, compatibility, saved-only and independent delivery/comparison proofs. Then run the assignment-scoped strict ready gate before any promotion.
