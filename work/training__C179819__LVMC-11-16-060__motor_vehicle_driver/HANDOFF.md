# LVMC-11-16-060 at C179819

Actor: `motor_vehicle_driver`. Frozen cell: `paved_road` / `travel` / `speed_limit_sign`.

Exact statutory source: LVMC 11.16.060. The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Twenty-five-mile-per-hour prima facie default without a different applicable posted limit..

Controlled planning variable: `speed_mph`. Proposed requests: measured 20 mph within applicable default-limit portion; measured 25 mph within applicable default-limit portion; measured 30 mph within applicable default-limit portion. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: different posted limit governs; prima facie meaning requires review.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/controller.py` requests 20, 25 and 30 mph using one 600-frame / 20 Hz feedback policy. Its source-shaped proof `native/controller-proof.json` (SHA-256 `e7bcd79657c2641d1d93f07e0c6f0e311e02ee7e8f9d2cbebcfca4ce1a0419bf`) passes all three requests and rejects the wrong speed, shortened trace and nonfinite observed speed. Synthetic speeds are not original CARLA velocity.

`native/measure_speed.py` and `native/measurement-contract.json` require original Native velocity and route position, full 600-frame/time and four-camera joins, public-street status, and a source-hashed complete sign survey over the traveled route. The CPU proof `native/speed-proof.json` (SHA-256 `c16b5ad291592b7ac373913257c92b1d093af06f0bb8fec3579f80ccfc5d92ce`) compares 20/25/30 mph under the default and tests a sourced 35 mph posted-governance interval; it rejects five survey, route and camera defects. The fixture sign and speed sources are placeholders. Above-default frames are measured observations; prima facie status and legal outcome require independent review.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire CARLA capture and four source cameras, construct exact cases, add the different-posted-limit branch with original sign authority and governance, run exact offline/compatibility/saved-only proofs and independent audits, then run scoped strict ready gate before promotion.
