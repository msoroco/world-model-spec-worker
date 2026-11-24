# LVMC-11-30-140-B at C129273

Actor: `motor_vehicle_driver`. Frozen cell: `mountain_road` / `travel` / `blind_pedestrian`.

Exact statutory source: LVMC 11.30.140(B). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Driver approaching a blind person carrying a white walking stick tipped in red..

Controlled planning variable: `driver_stop_for_blind_person`. Proposed requests: driver fully stops before proceeding near cane-bearing blind pedestrian; driver approaches same person without full stop. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: partial blindness; white cane or white tipped red; assisted-by-person wording; post-stop injury avoidance precautions.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## Current CPU source measurement checkpoint (2026-11-23)

`native/measure_blind_person.py` reads a retained, SHA-256-bound road, blind-person marker, and 600-frame/20-Hz Native-shaped motion source. It joins frame/time/actor identities, verifies speed-to-position continuity, and reports first recognition, deceleration, full stop, post-stop release, longitudinal surface gap/time to conflict, and geometric contact proxy. Source law remains LVMC 11.30.140(B); diagnostic stop epsilon and reaction duration are engineering measurements only, not legal cutoffs. Cane colour, blindness and assistance are synthetic source facts in this proof, not observed CARLA or camera evidence.

`native/prove_blind_person.py` generated five 30-second controlled scenarios under `.runtime-work/`: red-tipped white cane with stop and release after pedestrian clearance; white cane with partial blindness and the same motion; assisted person with the same motion; no stop; and stop followed by early release into the pedestrian's conflict area. The first three measured a full stop at frame 119 and release at 260 without geometric contact. The nonstop and early-release cases measured geometric conflict. Five negative tests rejected altered source bytes, missing frame, actor join, discontinuous motion, and missing marker provenance. This is a software diagnostic, not a physical collision or legal verdict.

Proof: `.venv-cpu/bin/python runtime.py preflight` passed; `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c129273-output .venv-cpu/bin/python work/training__C129273__LVMC-11-30-140-B__motor_vehicle_driver/native/prove_blind_person.py` passed with 5 scenarios and 5 negatives; `.venv-cpu/bin/python worker_check.py --assignment training__C129273__LVMC-11-30-140-B__motor_vehicle_driver --complete` passed static partial-package checks. Proof SHA-256: `9148cfc6a9101c81d42f38340a908af1b6e1232988b953f7e6218d30278356db`; measurement script SHA-256: `d677b62d70a0e9a29d89c84efce1b1c94056a5b55fd8059b83352bfded3408a4`; proof script SHA-256: `da2d3b8808c8561e7e1359c3bb7f9a68018c7a15822ef732172b199435875f4b`.

Status remains `partial`. Next CPU work: construct real Native mountain-road route, pedestrian/cane or assistance props, stop/release controllers and four cameras; bind real source acquisition including body polygons and actor/marker provenance; create exact selected cases, primary and risk-based fallbacks, pinned offline/compatibility/saved-only proofs, result finalizer, and independent audits. Revalidate with the assignment-scoped strict gate before any ready promotion. GPU capture remains a later physical check, not a substitute for those CPU tasks.
