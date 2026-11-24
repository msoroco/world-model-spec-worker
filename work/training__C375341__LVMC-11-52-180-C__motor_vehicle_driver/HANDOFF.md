# LVMC-11-52-180-C at C375341

Actor: `motor_vehicle_driver`. Frozen cell: `alley` / `park` / `alley_entrance`.

Exact statutory source: LVMC 11.52.180(C). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: alley parking duration.

Controlled planning variable: `parked_minutes_in_rolling_hour`. Proposed requests: otherwise lawful alley parking for 25 minutes in one hour; otherwise lawful alley parking for 35 minutes in same hour. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: rolling one-hour period; otherwise lawful prerequisite.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU gap: Native runner and original one-hour ledger acquisition, current-runtime exact offline/compatibility/process-saved proofs, fallbacks, and independent audits remain unfinished. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 source-shaped construction and rolling-hour checkpoint

`.venv-cpu/bin/python runtime.py preflight` passed (`cpu_preflight_passed: true`, no simulation). The exact law measures more than thirty minutes of parking within any one-hour period, conditioned on otherwise lawful alley parking. A 30-second capture cannot alone establish that history. The two existing probes remain `planned_only`; 25 and 35 minutes are requests, not observations or verdicts.

`measure_alley_parking.py` SHA-256 `cb66e1feeef70ce9688e14b3206bce58b26d96b2b2f0b6167641fab156594fcb` joins 600 original-source-shaped Native frames to four cameras and a separately hashed parking ledger covering at least one hour. It integrates nonoverlapping parking intervals over every source-covered rolling hour, including split stays; moving within the alley does not reset prior parked time. It requires source hashes for map, alley boundary, vehicle identity, parking ledger, civil-time join, and independent otherwise-lawful review. `alley-measurement-contract.json` SHA-256 `5fdf536d69893b83dbd135231e39dac55bbddafb8bbbf85b1ad890f40ad8bd24` maps all six source observation terms. The original ledger and review remain to be acquired and independently audited.

`alley_scene.py` SHA-256 `38fdcb957fd39a3b3cd44788df0b130de8be54652d087a1e7a5633ab3d2336eb` specifies a narrow OpenDRIVE alley road, parked vehicle and hold policy, wall/curb props, and four source-camera requests. Both probes use the same scene; only the requested total parked seconds in the separate hour ledger differs. It does not assert actual surveyed alley status or an hour-long recording.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_alley_parking.py` passed 25-minute, 35-minute, exact 30-minute, and split 20-plus-15-minute numeric/source-shaped positives and nine negative source, timing, identity, and capture checks. `alley-parking-proof.json` SHA-256 `ea284cd04eaafb9b38ba30296183c10827b6ac6f8eb724098ea88cae9c969f67`.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python prove_alley_scene.py` passed two authored-scene positives and five negative checks. `alley-scene-proof.json` SHA-256 `b085dd457bea7cc2c4807e1bdee9e6da15dcca0c2ed45c68e5744804debd0966`.

Next CPU work: wire an exact Native runner and source ledger with retained civil/Native time provenance, select the first case, and pass pinned-runtime offline, positive/negative compatibility, and actual process-saved. Then test fallbacks and independent audits. Keep partial until assignment-scoped strict acceptance passes.
