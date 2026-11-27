# C229398 / NRS 484B.600(1)(e) delivery handoff

Status: **ready for local Native delivery** after the exact assignment-scoped CPU strict gate passed. Three selected cases are bound to the current runtime: `probe_01` requests 75 mph, `probe_02` requests 79.5 mph, and `probe_03` requests 85 mph during a driving approach in one road/park/curb recording. Each then attempts curb parking and retains a separately reviewed parked interval. The statute uses a strict greater-than-80-mph boundary; no controller request is treated as achieved speed.

## Exact source and accepted evidence

- Frozen assignment SHA-256 `e0616cb9d29d5fc1ec7b3ec53f92b82513552d2e34e18c93f28e8b64146c9726`; witness SHA-256 `33c9937b8dc3f00c42a8e8ac940569540fa7b8a5bd568d4cc8fb030add936ff8`.
- The three accepted membership IDs in review-context remain **unverified for current-requirement equivalence**. Their exported context records requested approach speeds but no source-hashed original Native velocity, frame, or phase receipts. The new cases address those explicit source gaps. No duplicate-coverage claim is made.
- Original road/curb, driving-to-park phase, actor identity, and four-view visibility are independently source-hash gated by `source_review.py`. The synthetic diagnostic reviews cannot claim original provenance.

## Constructed CPU package

- Three exact inline constructions use the pinned runtime, a 1.8-km OpenDRIVE road with a driving lane and curb parking lane, 600 frames at 20 Hz, and four synchronized canonical cameras. The Native runner records post-tick velocity, actor, road/lane and frame identities. Physical curb completion and achieved speeds remain for actual Native execution.
- Three source-shaped synthetic fixture recipes are each under 2 MiB. The saved measurement joins Native velocity, Core trace, frame map, four camera frames and original review sources, measures only the driving approach, and reports parked frames separately. It makes no legal verdict or physical acceptance claim.
- All three exact pinned offline runs, public positive and missing-source-negative compatibility runs, recorded-only saved runs, and synthetic physical/lifecycle probes passed. The independent delivery auditor has positive inventory and synthetic-rejection selftests for each case. The three-way comparison audit verifies 75.0, 79.5 and 85.0 mph diagnostic velocity contrasts, with only the above-80 case exceeding the statutory threshold in the synthetic source. Exact semantic stage validation passed.
- `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c229398-check TMPDIR=$PWD/.runtime-work/c229398-check .venv-cpu/bin/python -B worker_check.py --assignment training__C229398__NRS-484B-600-1e__motor_vehicle_driver --complete --require-delivery-ready` exited 0. The runtime output is under `.runtime-work/`; all returned package files are under 2 MiB with clean whitespace and no blank EOF.

## Local delivery review

Execute the canonical `first_gpu_delivery_command` in `result.json` on a dedicated Native server. Review original achieved velocity rather than requested speed; confirm the approach-driving phase, actor identity, same road/park/curb recording, four-view visibility, and physical curb completion. Audit the sealed original, Native exit, owner release, saved-only processing, full decoded videos, and legal interpretation before accepting. The CPU fixtures cannot establish any of those original physical facts.
