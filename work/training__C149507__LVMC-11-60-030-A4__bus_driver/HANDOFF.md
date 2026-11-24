# LVMC-11-60-030-A4 at C149507

Actor: `bus_driver`. Frozen cell: `one_way_road` / `load_unload` / `other_vehicle`.

Exact statutory source: LVMC 11.60.030(A)(4). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Other traffic during entry and stopped loading.

Controlled planning variable: `front_wheel_curb_gap_inches`. Proposed requests: bus stops to load with right front wheel within 18 inches and approximately parallel; bus stops to load with right front wheel beyond 18 inches. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: non-tour-bus scope; undue impedance to other traffic; bus stand/loading zone/origin/destination.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/entry.py` requests paired 600-frame / 20 Hz bus entries and stopped loading positions; the longitudinal route, loading duration and other-vehicle target speed are fixed while the right-front-wheel gap request changes from 0.30 m to 0.70 m. The source-shaped entry proof `native/entry-proof.json` (SHA-256 `bbc4a008a0925ba4d4f5ca028c088183f7fdc16d6632a13dec7a70126b967412`) passes both requested targets and rejects moving during loading, the wrong wheel position and a short trace. Requested targets and synthetic observations are not original CARLA motion.

`native/measure_bus.py` and `native/measurement-contract.json` require original wheel contact and calibrated curb-face geometry, 600 Native frame/time joins, four source-camera identities, actual stopped loading, non-tour bus and public-street location sources, plus other-vehicle speed and delay. The source-shaped proof `native/bus-proof.json` (SHA-256 `8bd601e9ccf78d7f6181c365e3b38976ce0d5f8bdad6f090a0970ec6d35a778b`) distinguishes 0.30 m and 0.70 m gaps against the law's 18-inch limit and rejects eight source/frame/activity defects. Fixture source hashes are placeholders; `approximately parallel` and `unduly impede` remain independent judgments without invented numeric cutoffs.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. This package remains `partial`. Next CPU work: wire a CARLA runner and actual four-camera source acquisition, build exact cases and risk-based candidates, add the non-tour scope, traffic-impedance and alternative location branches, then run exact offline, compatibility, saved-only and independent delivery/comparison proofs. Run the assignment-scoped strict ready gate before promotion.

## 2026-11-23 qualifying location and wheel boundary CPU checkpoint

The source-shaped bus proof now exercises each statutory location kind: bus stop, bus stand, passenger loading zone, origin, and destination, all on the same 600-frame trace and without claiming a legal outcome. It also tests the inclusive 18-inch wheel-to-curb boundary (`0.4572 m`) against `0.4573 m`; the first is within the limit and the second is beyond it. A ninth negative rejects an unqualified curb location. Refreshed `native/bus-proof.json` SHA-256 `5b44a2c0b4b92b797e9018a82bc39bef90ca48277ed63f8d0659fd9e8420728f`; proof script SHA-256 `0645afcdaad59fd00906aaf8719f021d126b610bdf0fb53481e5efcf8d980de2`. Command: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c149507-location-output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C149507__LVMC-11-60-030-A4__bus_driver/native/prove_bus.py`. Actual public-street and location sources, wheel geometry, Native capture, approximately-parallel and undue-impedance judgments, selected delivery and audits remain unfinished.
