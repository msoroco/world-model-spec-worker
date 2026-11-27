# LVMC-11-52-130-A4 at C200568

Actor: `motor_vehicle_driver`. Frozen cell: `public_access_premises` / `park` / `fire_hydrant`.

Exact statutory source: LVMC 11.52.130(A)(4). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Angle parking permitted: twenty feet. Planned comparison variable: `hydrant_parking_clearance`. Requests: vehicle parks beyond the applicable hydrant clearance; vehicle parks inside the applicable hydrant clearance. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: a fire hydrant is beside the roadway; the subject stops, stands or parks within fifteen feet where parallel parking is permitted, or within twenty feet where angle parking or no parking is permitted.

Timing to retain: judged for every instant at rest inside the band.

Exceptions and numeric alternatives planned: when necessary to avoid conflict with other traffic; in compliance with law; in compliance with the directions of a police officer or a traffic control device; parallel hydrant clearance numeric boundary 15 feet; angle or prohibited hydrant clearance numeric boundary 20 feet.

Unresolved judgment or rule composition: which distance applies turns on what kind of parking is permitted at the place, which is a map or sign fact rather than a hydrant fact; the rule applies whether or not the curb is painted or a sign posted, so a rule keyed to curb colour alone misses it. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU hydrant geometry source diagnostic

Added `native/hydrant_measure.py` and `native/prove_hydrant_measure.py`. The diagnostic requires source statements for parking permission, hydrant position, and distance uncertainty, plus 600 joined stopped frames at 20 Hz with four pinned camera identities and vehicle footprints. It measures the closest hydrant-to-footprint distance and retains a bracket. Parallel-permitted parking uses the source law's 15-foot threshold; angle-permitted and no-parking locations use 20 feet. Paint and sign fields are recorded but never used to select the threshold. Exception facts remain declarations requiring original evidence and independent review, not geometry-derived verdicts.

The proof builds all fourteen planned source shapes under `.runtime-work/`: two clearance witnesses, six exception-context declarations, and six 14.5/15/15.5 and 19.5/20/20.5 foot boundary examples. A separate no-parking regime check confirms the twenty-foot branch. Five missing-source mutations reject missing permission, missing hydrant, truncated frames, camera loss and missing footprint. These are `synthetic_native_sample` geometry diagnostics, not Native motion, pixels or legal compliance.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_hydrant_measure.py > native/hydrant-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C200568__LVMC-11-52-130-A4__motor_vehicle_driver --complete > native/current-static-check.log 2>&1`

SHA-256: measurement code `28def6169e319fed8dd06d4750eae60b4877f3843208b660dd60ce3784d76fa3`; proof script `ce9694e13e59150e708df578f6903fa798b89972c414a03547c8a83e081fec05`; proof result `2098bb4d72a9d0503b23fef2601858050b8937385319dcc68a7f6c6b8a07b069`; preflight log `f79f814cdfe1348436b622f8d3a3aa619e729487f7d63e677a269eead1858541`; scoped checkpoint log `ca8ce2d7d0032b7628764ba182512073bbe58c350d418dc2b7dc766f9a8b1cc5`.

Next CPU work: construct the exact public-access premises Native scene, hydrant and parked-vehicle controllers, and source acquisition for permission, traffic conflict and lawful direction. Bind all fourteen cases to an execution manifest with four source camera streams and run pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. Reconcile the full exception grammar against source law before final selection; synthetic context declarations do not prove those exceptions. There is no exact construction bundle yet; keep the assignment partial.
## 2026-11-27 selected Native construction and saved-source checkpoint

Generated fourteen exact case-specific `worker-inline-construction` bundles under `native/` from the frozen fourteen-row plan. Each pins the public-access-premises/park/fire-hydrant cell, the 600-frame 20 Hz four-camera capture, permission regime, requested footprint clearance and exception context. The capture runner requires an original Native premises, parking-permission and hydrant survey; exception truth is not inferred from geometry. The runner has not executed against Native and actual target clearance, parking maneuver, camera pixels and physical outcome remain unverified.

Pinned `runtime.py offline` passed for all fourteen IDs: witness_1, witness_2, exception_1_1, exception_1_2, exception_2_1, exception_2_2, exception_3_1, exception_3_2, numeric_1_0, numeric_1_1, numeric_1_2, numeric_2_0, numeric_2_1, numeric_2_2. Logs are `native/selected-<suffix>-offline.log`; `native/selected-offline-index.json` lists the exact IDs. All materialized offline attempts were under `.runtime-work/`.

`native/saved_hydrant.py` joins the original Native pose trace, video frame map and independent hydrant/permission survey; it measures closest rotated vehicle-footprint distance and uncertainty without using curb paint/sign to choose the 15- or 20-foot branch. `native/test_saved_hydrant.py` exercised all fourteen 600-frame synthetic source shapes and five missing/contradictory-source negatives. This is direct saved-source CPU evidence, not an official `process-saved` receipt or a legal verdict.

SHA-256: selected draft manifest `3c7d22cc4067c41b5c1b1fa080f784e8b47e3859b1e32d5652eda18efe1c40bb`; saved join proof `47fb43620848483630b97232fc2ca4f6904384b65932e9ba1158f5e8fe9c90a2`; offline index `40de1dc832a8ca58bc2badd14c7aa40948aa461f45f725f7939afbde93967c15`.

Current frozen runtime verify and scoped `worker_check.py --complete` exit 0. Exact `--complete --require-delivery-ready` exits 1 with `Preparation acceptance failed: partial/missing packages remain`, consistent with the truthful partial status. Remaining construction: source-bound finalizer and official fixture-recipe public positive/missing-source negative; fallback candidate and official saved replay; semantic, physical/lifecycle, delivery and comparison audits; execution/root binding and final strict gate. The prior 14-shape geometry diagnostic remains intact.
