# C230241 / NRS 484B.360(1) handoff

Status: **ready for delivery preparation**. Exact assignment strict CPU gate passed. Accepted original Native recordings and memberships: 0. Frozen `road/travel/ice_cream_truck` cell and `school_bus_driver` actor are unchanged.

## Selected construction and source law

- Two selected exact cases request 52 and 58 mph, respectively, with distinct primary and route-spawn fallback1 candidates. The same 30-second, 20 Hz, 600-frame four-camera policy, school bus, school-trip review requirement and separate ice cream truck control apply to both cases. Candidate selection is triggered by actor spawn or route-progress failure, never by desired speed or legal outcome.
- The source text caps a school bus at 55 mph while transporting pupils to and from school. `native/measure_speed.py` measures every saved original post-tick velocity and reports maximum mph plus each frame above 55. `native/finalize.py` requires camera-bound independent pupil, bus-class and trip-purpose review and returns no legal verdict. No synthetic pupil or trip assertion is accepted as original evidence.
- The Native runner resolves one exact school-bus and ice-cream-truck blueprint or fails explicitly. Their presence, viable route, physical speed, original pupil occupancy and school trip purpose remain pending original CARLA capture and independent source review. No accepted evidence or equivalence reuse is claimed.

## Exact CPU proofs

- All four exact primary/fallback constructions pass `runtime.py offline`. All four public compatibility positives and missing-`bus_motion.jsonl` negatives pass. The diagnostic saved speed pair measures 54 and 56 mph; these are synthetic source fixtures, not original observations. All four recorded-only `process-saved` paths pass with `missing_evidence=false`, `originals_preserved=true` and no physical or legal claim.
- Physical complete/incomplete/missing-evidence triads pass for both cases. Semantic stage validation, independent delivery positives and missing original capture-seal negatives, and fixed-condition comparison audit pass. The top-level 4-test Native contract suite passes.
- Exact gate: `.venv-cpu/bin/python worker_check.py --assignment training__C230241__NRS-484B-360-1__school_bus_driver --complete --require-delivery-ready`; exit 0, `static_checks_passed=true`. `strict-assignment.log` SHA-256 `a010233674ffe668de9183ad0e26d75207039f7c5b74085f69cb9d3cef968935`.
- `execution-manifest.json` SHA-256 `6a11a6d368e50908cae68cba2ed5a6719f8ff6e4e6372aaa3f727c3241c3a968`; `proposals/semantic-index.json` SHA-256 `13d3ca65f34621a0a3600043ca8e1d5e2ef0b4d661dab285da91aa8be1a0ce38`; `comparison-main-audit.json` SHA-256 `ba18a122dd2a6118355ae29dab5f90e29ba7e373edcc06f684061deaaebb885d`; `result.json` SHA-256 `fd64ca3f0146d5e891d8ca0e2d4f5c20ed2922a6bd34d920ace3c9aae3ed5f7e`.

## First original capture

Use the `first_gpu_delivery_command` in `result.json` with an authorized CARLA host and sealed original job. Independently review exact actor identities, pupils aboard, trip-purpose source, all camera pixels, joined motion and physical completion before any legal or acceptance judgment.
