# LVMC-11-12-070-B at C111294

## 2026-11-23 CPU construction checkpoint

The original text conditions the through-highway driver's duty on the entering driver having first yielded and being about to enter or cross. The paired planned cases retain the same entrant trajectory and through-vehicle history through frame 141, then vary only the requested through response. This is a controlled diagnostic design, not a legal verdict or observed CARLA motion. The assignment has no accepted recordings to reuse.

`build-primary.py` now bundles both exact 600-frame, 20 Hz unselected proposals in `draft-primary/` and `draft-controlled/`. Their current pinned offline commands passed with exit 0:

- `.venv-cpu/bin/python runtime.py offline --manifest work/training__C111294__LVMC-11-12-070-B__motor_vehicle_driver/draft-primary-manifest.json --case training__C111294__LVMC-11-12-070-B__motor_vehicle_driver__probe_1 --output .runtime-work/c111294-probe-1-offline` (`draft-probe-1-offline.log`, SHA-256 `d8996c88f128739f766615ffd2666cc685e9ffe4c87a3170c0dfa93fc36abe52`).
- The same command with `probe_2` and `.runtime-work/c111294-probe-2-offline` passed (`draft-probe-2-offline.log`, SHA-256 `8a271f044a580a2285842decf7e693788395108a15805a7094cc93d808b71650`).

The manifest SHA-256 is `3d1d65320471251f6fd71f9a7945f13750b4f27942af56d7cf228066316a4c4d`; construction SHA-256 values are `df40ab4a4153410568087dc02ff6a309175aa10b5535625aa35b620ed02b8dac` and `c761ecc8986cb514cc52fa265992e7d2983e9d5950b38facdce034f2013eabd2`. `prove-yield-sequence.py` generated only under `.runtime-work/` and exercised `native/measure_yield.py` on both full 600-frame source traces. Both positives and six negatives passed (missing, unbound alteration, shortened source, wrong frame join, wrong road role, wrong case). The entrant source is fixed for all 600 frames, and through history is fixed before intervention. `yield-sequence-proof.json` SHA-256 `0882ee0349b1a01474ab4f0583a4550511f911b333d4c7f30287d9d9e923c0a1` and log SHA-256 `1a8f87c1c65e4857b0683d94e3055964be8bc57d2eb79ffffeab3453c7765cd0`.

`runtime.py preflight` passed. Assignment-scoped `worker_check.py --complete` passed; `--complete --require-delivery-ready` failed as expected on truthful partial status. The current runner still has no Native capture loop, controller deployment, camera synchronization or source video. Current-runtime compatibility and actual `process-saved`, selected primary/fallbacks, independent delivery/comparison audit, and complete statutory review remain worker-owned CPU work. The geometry's legal through-highway designation and the entrant's lawful prior yield require original-source review; fixture coordinates and engineering speed tolerances do not establish either fact. No physical acceptance is claimed.

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `travel` / `other_vehicle`.

Exact statutory source: LVMC 11.12.070(B). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Approaching through-highway driver's yielding duty..

Controlled planning variable: `through_driver_yield_to_entering_vehicle`. Proposed requests: through-road driver yields after other driver has yielded and is about to enter; through-road driver fails to yield to same entrant. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: other driver first yielded; entrant about to enter or cross.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.
